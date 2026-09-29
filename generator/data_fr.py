"""Récupération et normalisation des prix officiels (data.economie.gouv.fr, flux instantané v2)."""
import gzip
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

URL = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/exports/json")

FUELS = ["gazole", "sp95", "sp98", "e10", "e85", "gplc"]
FUEL_LABEL = {"gazole": "Gazole", "sp95": "SP95", "sp98": "SP98", "e10": "E10", "e85": "E85", "gplc": "GPL"}
FUEL_SLUG = {"gazole": "gazole", "sp95": "sp95", "sp98": "sp98", "e10": "e10", "e85": "e85", "gplc": "gpl"}
SLUG_FUEL = {v: k for k, v in FUEL_SLUG.items()}
# Bornes de cohérence : une valeur hors bornes est ignorée (erreur de saisie probable), jamais corrigée.
RANGE = {"gazole": (0.8, 4.0), "sp95": (0.8, 4.0), "sp98": (0.8, 4.0), "e10": (0.8, 4.0),
         "e85": (0.3, 2.5), "gplc": (0.3, 2.5)}
# Un prix dont la dernière mise à jour remonte à plus de MAX_AGE_DAYS jours (par rapport à la mise à jour la plus récente
# du jeu de données) est ignoré : il fausserait les classements (le jeu contient des prix vieux de plus d'un an).
MAX_AGE_DAYS = 30
DISPO_KEY = {"gazole": "gazole", "sp95": "sp95", "sp98": "sp98", "e10": "e10", "e85": "e85", "gplc": "gplc", "gpl": "gplc"}


def fetch(url=URL, tries=3, timeout=180):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CarburantRadar-SEO-generator/2.0",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            if body[:2] == b"\x1f\x8b":  # réponse compressée en gzip (l'export officiel peut l'être)
                body = gzip.decompress(body)
            return json.loads(body.decode("utf-8"))
        except Exception as e:  # réseau, JSON... : on retente puis on échoue proprement
            last = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"Téléchargement impossible ({last})")


def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _coords(rec):
    geom = rec.get("geom")
    if isinstance(geom, dict) and _num(geom.get("lat")) is not None and _num(geom.get("lon")) is not None:
        return _num(geom["lat"]), _num(geom["lon"])
    lat, lon = _num(rec.get("latitude")), _num(rec.get("longitude"))
    if lat is None or lon is None:
        return None, None
    if abs(lat) > 90 or abs(lon) > 180:  # format brut du flux : degrés x 100000
        lat, lon = lat / 1e5, lon / 1e5
    if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0):
        return None, None
    return lat, lon


def parse_ts(s):
    if not s or not isinstance(s, str):
        return None
    try:
        d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def _dispo(v):
    if v is None:
        return set()
    items = v if isinstance(v, list) else str(v).replace(",", ";").split(";")
    out = set()
    for it in items:
        k = DISPO_KEY.get(str(it).strip().lower())
        if k:
            out.add(k)
    return out


def normalize(raw):
    """Liste brute -> liste de stations compactes + horodatage de référence des données."""
    latest = None
    for r in raw:  # passe 1 : mise à jour la plus récente (référence pour juger l'ancienneté des prix)
        for f in FUELS:
            p = _num(r.get(f"{f}_prix"))
            lo, hi = RANGE[f]
            if p is not None and lo <= p <= hi:
                d = parse_ts(r.get(f"{f}_maj"))
                if d and (latest is None or d > latest):
                    latest = d
    limit = latest - timedelta(days=MAX_AGE_DAYS) if latest else None
    stations = []
    for r in raw:
        lat, lon = _coords(r)
        if lat is None:
            continue
        prices, maj = {}, {}
        for f in FUELS:
            p = _num(r.get(f"{f}_prix"))
            lo, hi = RANGE[f]
            if p is not None and lo <= p <= hi:
                m = r.get(f"{f}_maj")
                d = parse_ts(m)
                if d and limit and d < limit:
                    continue  # prix trop ancien : ignoré
                prices[f] = round(p, 3)
                maj[f] = m if isinstance(m, str) else None
        auto = str(r.get("horaires_automate_24_24") or "").strip().lower() in ("oui", "true", "1", "yes")
        stations.append({
            "id": str(r.get("id") or "").replace(" ", ""),
            "lat": round(lat, 6), "lon": round(lon, 6),
            "cp": str(r.get("cp") or "").strip(),
            "adr": str(r.get("adresse") or "").strip(),
            "ville": str(r.get("ville") or "").strip(),
            "dep": str(r.get("departement") or "").strip(),
            "dep_code": str(r.get("code_departement") or "").strip(),
            "reg": str(r.get("region") or "").strip(),
            "reg_code": str(r.get("code_region") or "").strip(),
            "p": prices, "m": maj, "a24": auto,
            "dispo": sorted(_dispo(r.get("carburants_disponibles"))),
        })
    stations.sort(key=lambda s: (s["id"], s["lat"], s["lon"]))  # ordre stable => génération déterministe
    return stations, latest


def load(path=None):
    raw = json.load(open(path, encoding="utf-8")) if path else fetch()
    if not isinstance(raw, list) or len(raw) < 100:
        raise RuntimeError(f"Jeu de données inattendu ({type(raw).__name__}, {len(raw) if hasattr(raw, '__len__') else '?'} éléments)")
    stations, latest = normalize(raw)
    if len(stations) < 100 or latest is None:
        raise RuntimeError("Trop peu de stations exploitables ou aucune date de mise à jour trouvée")
    return stations, latest
