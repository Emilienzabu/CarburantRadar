"""Prix officiels espagnols : API REST « Precios Carburantes » du Ministerio para la Transición Ecológica.

Sortie : mêmes stations compactes que data_fr (clés de carburants internes identiques : gazole, sp95, e10, sp98, e85, gplc),
pour réutiliser les calculs de stats_fr. Aucune valeur inventée : un champ absent ou hors bornes est ignoré.
"""
import json
import os
import re
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone

from data_fr import RANGE

URL = "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/"
FIELD = {  # clé interne -> champ de l'API (comparé sans accents, casse ni ponctuation)
    "gazole": "precio gasoleo a",
    "sp95": "precio gasolina 95 e5",
    "e10": "precio gasolina 95 e10",
    "sp98": "precio gasolina 98 e5",
    "e85": "precio bioetanol",
    "gplc": "precio gases licuados del petroleo",
}
CCAA = {"01": "Andalucía", "02": "Aragón", "03": "Asturias", "04": "Illes Balears", "05": "Canarias", "06": "Cantabria",
        "07": "Castilla y León", "08": "Castilla-La Mancha", "09": "Cataluña", "10": "Comunidad Valenciana",
        "11": "Extremadura", "12": "Galicia", "13": "Comunidad de Madrid", "14": "Región de Murcia",
        "15": "Navarra", "16": "País Vasco", "17": "La Rioja", "18": "Ceuta", "19": "Melilla"}
SMALL = {"de", "del", "la", "las", "el", "los", "y", "i", "e", "en", "o", "a", "d", "l"}
ARTICLE = re.compile(r"^(.*?)\s*\((El|La|Los|Las|A|O|Os|As|L'|Els|Les|Illes|Ses|Sa|Es)\)$", re.I)
DIAG = {}
MIN_STATIONS = int(os.environ.get("CR_ES_MIN", "3000"))   # seuil de plausibilité (abaissé uniquement pour les tests)


def _k(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _num(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return None


def fix_article(name):
    """« Coruña (A) » -> « A Coruña » ; « Hospitalet de Llobregat (L') » -> « L'Hospitalet de Llobregat »."""
    m = ARTICLE.match(name.strip())
    if not m:
        return name.strip()
    base, art = m.group(1).strip(), m.group(2)
    return f"{art}{base}" if art.endswith("'") else f"{art} {base}"


def title_es(s):
    """Libellé en MAJUSCULES -> casse de titre espagnole ; un libellé déjà en casse mixte est conservé."""
    s = fix_article(s)
    if not s or not s.isupper():
        return s
    out = []
    for i, w in enumerate(re.split(r"(\s+|-|/)", s.lower())):
        out.append(w if (i > 0 and w in SMALL) else w[:1].upper() + w[1:])
    return "".join(out)


def _brand(s):
    return s.upper() if len(s) <= 3 else title_es(s)


def fetch(url=URL, tries=3, timeout=180):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CarburantRadar-SEO-generator/2.0)",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            try:
                return json.loads(body.decode("utf-8-sig"))
            except UnicodeDecodeError:
                return json.loads(body.decode("latin-1"))
        except Exception as e:  # réseau, JSON... : on retente puis on échoue proprement
            last = e
            time.sleep(8 * (i + 1))
    raise RuntimeError(f"Téléchargement impossible ({last})")


def _fecha(s):
    try:
        d = datetime.strptime(str(s).strip(), "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None
    try:
        from zoneinfo import ZoneInfo
        return d.replace(tzinfo=ZoneInfo("Europe/Madrid")).astimezone(timezone.utc)
    except Exception:
        return d.replace(tzinfo=timezone.utc)


def normalize(raw, known=()):
    """`known` : noms normalisés (norm_name) des villes de villes.json, pour choisir entre « Donostia/San Sebastián » et « Donostia »."""
    if isinstance(raw, dict):
        lst = raw.get("ListaEESSPrecio")
        if lst is None:
            raise RuntimeError("Réponse inattendue : clés " + ", ".join(sorted(raw)[:12]))
        latest = _fecha(raw.get("Fecha"))
    else:
        lst, latest = raw, None
    if latest is None:
        latest = datetime.now(timezone.utc)
    DIAG["records"] = len(lst)
    if lst:
        DIAG["keys"] = sorted(lst[0].keys())[:40]
    from geo import norm_name
    stations = []
    for r in lst:
        d = {_k(k): v for k, v in r.items()}
        if str(d.get("tipo venta", "P")).strip().upper() == "R":   # vente restreinte (coopératives, flottes) : exclue
            continue
        lat, lon = _num(d.get("latitud")), _num(d.get("longitud wgs84"))
        if lat is None or lon is None or not (26.0 < lat < 44.5 and -19.5 < lon < 5.5):
            continue
        prices = {}
        for f, key in FIELD.items():
            p = _num(d.get(key))
            lo, hi = RANGE[f]
            if p is not None and lo <= p <= hi:
                prices[f] = round(p, 3)
        mun = fix_article(str(d.get("municipio") or d.get("localidad") or ""))
        if "/" in mun and norm_name(mun) not in known:
            mun = mun.split("/")[0].strip()
        ccaa = str(d.get("idccaa") or "").strip()
        horario = str(d.get("horario") or "")
        stations.append({
            "id": "ES" + str(d.get("ideess") or "").strip(),
            "lat": round(lat, 6), "lon": round(lon, 6),
            "cp": str(d.get("c p") or "").strip(),
            "pop": "",
            "adr": title_es(str(d.get("direccion") or "").strip()),
            "ville": title_es(mun),
            "dep": title_es(str(d.get("provincia") or "").split("/")[0].strip()),
            "dep_code": str(d.get("idprovincia") or "").strip(),
            "reg": CCAA.get(ccaa, ""), "reg_code": ccaa,
            "p": prices, "m": {}, "a24": "24H" in horario.upper().replace(" ", ""),
            "dispo": sorted(prices), "brand": _brand(str(d.get("rotulo") or "").strip()),
        })
    stations.sort(key=lambda s: (s["id"], s["lat"], s["lon"]))
    return stations, latest


def load(path=None, known=()):
    raw = json.load(open(path, encoding="utf-8")) if path else fetch()
    stations, latest = normalize(raw, known)
    DIAG["stations"] = len(stations)
    if len(stations) < MIN_STATIONS:
        raise RuntimeError(f"Trop peu de stations exploitables ({len(stations)} sur {DIAG.get('records')}) ; champs vus : {DIAG.get('keys')}")
    return stations, latest
