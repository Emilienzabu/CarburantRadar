"""Prix officiels italiens : deux CSV nationaux quotidiens du MIMIT (prix + anagrafica des stations).

Sortie : mêmes stations compactes que data_fr (clés internes : gazole = Gasolio, sp95 = Benzina, gplc = GPL, e85 = Metano),
pour réutiliser les calculs de stats_fr. Prix self-service quand il existe, sinon prix servito. Aucune valeur inventée.
"""
import csv
import gzip
import io
import os
import re
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone

from data_fr import RANGE

BASES = ["https://www.mimit.gov.it/images/exportCSV/", "https://www.mise.gov.it/images/exportCSV/"]
PRICE_FILE = "prezzo_alle_8.csv"
STATION_FILE = "anagrafica_impianti_attivi.csv"
FUEL = {"benzina": "sp95", "gasolio": "gazole", "gpl": "gplc", "metano": "e85"}   # descCarburante normalisé -> clé interne
MAX_AGE_DAYS = 30
MIN_STATIONS = int(os.environ.get("CR_IT_MIN", "5000"))
DIAG = {}
PROV = {
    "AG": "Agrigento", "AL": "Alessandria", "AN": "Ancona", "AO": "Aosta", "AP": "Ascoli Piceno", "AQ": "L'Aquila", "AR": "Arezzo",
    "AT": "Asti", "AV": "Avellino", "BA": "Bari", "BG": "Bergamo", "BI": "Biella", "BL": "Belluno", "BN": "Benevento", "BO": "Bologna",
    "BR": "Brindisi", "BS": "Brescia", "BT": "Barletta-Andria-Trani", "BZ": "Bolzano", "CA": "Cagliari", "CB": "Campobasso",
    "CE": "Caserta", "CH": "Chieti", "CL": "Caltanissetta", "CN": "Cuneo", "CO": "Como", "CR": "Cremona", "CS": "Cosenza",
    "CT": "Catania", "CZ": "Catanzaro", "EN": "Enna", "FC": "Forlì-Cesena", "FE": "Ferrara", "FG": "Foggia", "FI": "Firenze",
    "FM": "Fermo", "FR": "Frosinone", "GE": "Genova", "GO": "Gorizia", "GR": "Grosseto", "IM": "Imperia", "IS": "Isernia",
    "KR": "Crotone", "LC": "Lecco", "LE": "Lecce", "LI": "Livorno", "LO": "Lodi", "LT": "Latina", "LU": "Lucca",
    "MB": "Monza e Brianza", "MC": "Macerata", "ME": "Messina", "MI": "Milano", "MN": "Mantova", "MO": "Modena",
    "MS": "Massa-Carrara", "MT": "Matera", "NA": "Napoli", "NO": "Novara", "NU": "Nuoro", "OR": "Oristano", "PA": "Palermo",
    "PC": "Piacenza", "PD": "Padova", "PE": "Pescara", "PG": "Perugia", "PI": "Pisa", "PN": "Pordenone", "PO": "Prato",
    "PR": "Parma", "PT": "Pistoia", "PU": "Pesaro e Urbino", "PV": "Pavia", "PZ": "Potenza", "RA": "Ravenna",
    "RC": "Reggio Calabria", "RE": "Reggio Emilia", "RG": "Ragusa", "RI": "Rieti", "RM": "Roma", "RN": "Rimini", "RO": "Rovigo",
    "SA": "Salerno", "SI": "Siena", "SO": "Sondrio", "SP": "La Spezia", "SR": "Siracusa", "SS": "Sassari", "SU": "Sud Sardegna",
    "SV": "Savona", "TA": "Taranto", "TE": "Teramo", "TN": "Trento", "TO": "Torino", "TP": "Trapani", "TR": "Terni",
    "TS": "Trieste", "TV": "Treviso", "UD": "Udine", "VA": "Varese", "VB": "Verbano-Cusio-Ossola", "VC": "Vercelli",
    "VE": "Venezia", "VI": "Vicenza", "VR": "Verona", "VT": "Viterbo", "VV": "Vibo Valentia",
}
SMALL = {"di", "del", "dei", "degli", "della", "delle", "dello", "e", "ed", "in", "su", "sul", "sulla", "sui", "a", "al", "alla", "alle", "ai", "da", "dal", "dalla", "con", "per", "tra", "fra", "nel", "nella"}
ELIDED = {"d", "dell", "dall", "nell", "sull", "all", "un"}


def _k(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _num(v):
    try:
        v = str(v).strip().replace(",", ".")
        return float(v) if v else None
    except ValueError:
        return None


def title_it(s):
    """Libellé en MAJUSCULES -> casse de titre italienne (Reggio nell'Emilia, Castello d'Argile, Sant'Angelo)."""
    s = (s or "").strip()
    if not s or not s.isupper():
        return s
    out = []
    for i, w in enumerate(re.split(r"(\s+|-|/)", s.lower())):
        if "'" in w:
            a, _, b = w.partition("'")
            a = a if (a in ELIDED and i > 0) else a[:1].upper() + a[1:]
            w = a + "'" + b[:1].upper() + b[1:]
        elif i > 0 and w in SMALL:
            pass
        else:
            w = w[:1].upper() + w[1:]
        out.append(w)
    return "".join(out)


def _decode(body):
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError:
        return body.decode("latin-1")


def fetch_text(name, tries=4, timeout=120):
    last = None
    for i in range(tries):
        for base in BASES:
            try:
                req = urllib.request.Request(base + name, headers={"User-Agent": "Mozilla/5.0 (compatible; CarburantRadar-SEO-generator/2.0)",
                                                                   "Accept": "text/csv,*/*", "Accept-Encoding": "gzip", "Connection": "close"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return _decode(r.read())
            except Exception as e:
                last = e
        time.sleep(8 * (i + 1))
    raise RuntimeError(f"Téléchargement impossible de {name} ({last})")


def rows(text, must):
    """Lignes d'un CSV MIMIT (séparateur « ; », première ligne parfois « Estrazione del … ») sous forme de dicts à clés normalisées."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines[:10]) if must in _k(l)), None)
    if start is None:
        raise RuntimeError(f"En-tête introuvable (attendu : {must}) ; début du fichier : {lines[:2]}")
    extract = lines[0] if start else ""
    rd = csv.reader(io.StringIO("\n".join(lines[start:])), delimiter=";", quoting=csv.QUOTE_NONE)
    head = [_k(h) for h in next(rd)]
    DIAG.setdefault("headers", []).append(head)
    DIAG.setdefault("rows_skipped", 0)

    def gen():
        for r in rd:
            if len(r) == len(head) + 1 and not r[-1].strip():
                r = r[:-1]                       # « ; » final superflu
            if len(r) == len(head):              # une ligne mal découpée (séparateur dans un texte) est ignorée, jamais devinée
                yield dict(zip(head, r))
            elif any(x.strip() for x in r):
                DIAG["rows_skipped"] += 1
    return extract, gen()


def _ts(s):
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def normalize(price_text, station_text):
    extract, prows = rows(price_text, "idimpianto")
    best = {}                                    # (id, carburant) -> (self ?, prix, date)
    latest = None
    n_prices = 0
    for r in prows:
        f = FUEL.get(_k(r.get("desccarburante", "")))
        p = _num(r.get("prezzo"))
        if not f or p is None:
            continue
        lo, hi = RANGE[f]
        if not (lo <= p <= hi):
            continue
        d = _ts(r.get("dtcomu", ""))
        n_prices += 1
        if d and (latest is None or d > latest):
            latest = d
        is_self = str(r.get("isself", "")).strip() in ("1", "true", "True")
        key = (str(r.get("idimpianto", "")).strip(), f)
        cur = best.get(key)
        cand = (is_self, p, d)
        # préfère le self-service ; à statut égal, la mise à jour la plus récente
        if cur is None or (cand[0], cand[2] or datetime.min.replace(tzinfo=timezone.utc)) > (cur[0], cur[2] or datetime.min.replace(tzinfo=timezone.utc)):
            best[key] = cand
    DIAG["price_rows"] = n_prices
    if latest is None:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", extract)
        latest = _ts(m.group(1)) if m else datetime.now(timezone.utc)
    limit = latest - timedelta(days=MAX_AGE_DAYS)
    prices = {}
    for (sid, f), (is_self, p, d) in best.items():
        if d and d < limit:
            continue
        prices.setdefault(sid, {})[f] = round(p, 3)
    _, srows = rows(station_text, "idimpianto")
    stations, bad_coords = [], 0
    for r in srows:
        sid = str(r.get("idimpianto", "")).strip()
        if sid not in prices:
            continue
        lat, lon = _num(r.get("latitudine")), _num(r.get("longitudine"))
        if lat is not None and lon is not None and not (35.0 < lat < 47.5 and 6.0 < lon < 19.0) and (35.0 < lon < 47.5 and 6.0 < lat < 19.0):
            lat, lon = lon, lat                  # latitude et longitude inversées
        if lat is None or lon is None or not (35.0 < lat < 47.5 and 6.0 < lon < 19.0):
            bad_coords += 1
            continue
        sigla = str(r.get("provincia", "")).strip().upper()
        brand = str(r.get("bandiera", "")).strip()
        stations.append({
            "id": "IT" + sid, "lat": round(lat, 6), "lon": round(lon, 6), "cp": "",
            "pop": "A" if "autostrad" in _k(r.get("tipo impianto", "")) else "",
            "adr": title_it(str(r.get("indirizzo", "")).strip()),
            "ville": title_it(str(r.get("comune", "")).strip()),
            "dep": PROV.get(sigla, sigla), "dep_code": sigla, "reg": "", "reg_code": "",
            "p": prices[sid], "m": {}, "a24": False, "dispo": sorted(prices[sid]),
            "brand": brand.upper() if len(brand) <= 3 else title_it(brand),
        })
    DIAG["bad_coords"] = bad_coords
    stations.sort(key=lambda s: (s["id"], s["lat"], s["lon"]))
    return stations, latest


def load(path=None):
    """`path` : dossier local contenant les deux CSV (tests) ; sinon téléchargement."""
    if path:
        pt = open(os.path.join(path, PRICE_FILE), encoding="utf-8").read()
        st = open(os.path.join(path, STATION_FILE), encoding="utf-8").read()
    else:
        pt, st = fetch_text(PRICE_FILE), fetch_text(STATION_FILE)
    stations, latest = normalize(pt, st)
    DIAG["stations"] = len(stations)
    if len(stations) < MIN_STATIONS:
        raise RuntimeError(f"Trop peu de stations exploitables ({len(stations)}) ; diagnostic : {DIAG}")
    return stations, latest
