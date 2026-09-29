"""Calculs de statistiques à partir des stations (aucune donnée inventée : tout vient du jeu officiel)."""
import math
import re
from collections import Counter, defaultdict

from geo import haversine, norm_name, same_commune, slugify
from data_fr import FUELS

RADIUS_KM = 12          # même rayon que le bloc « en direct » de la page (dist=12 côté Worker)
COMMUNE_KM = 15         # garde-fou contre les homonymes lointains
NEIGHBOR_KM = 60
NEIGHBOR_MAX = 8
MIN_COMMUNE_SCOPE = 3
MIN_STATIONS_INDEX = 3
MIN_FUELS_INDEX = 2
MIN_SCORE_INDEX = 45
MIN_DEP_STATIONS = 15   # page département : minimum de stations dans le jeu de données
MIN_FUEL_PAGE = 8       # page ville+carburant : minimum de stations avec un prix pour ce carburant
MIN_DEP_COMPARE = 10    # comparaison départementale : minimum de prix pour ce carburant
SMALL = {"du", "de", "des", "la", "le", "les", "sur", "sous", "en", "et", "au", "aux", "d", "l", "a"}


def pretty(s):
    """Met en forme un libellé du flux (souvent en MAJUSCULES) sans changer son contenu."""
    if not s:
        return ""
    if not s.isupper():
        return s
    out = []
    for i, w in enumerate(re.split(r"(\s+)", s.title())):
        base = w.lower()
        out.append(base if i > 0 and base in SMALL else w)
    res = "".join(out)
    res = re.sub(r"-(En|De|Sur|Sous|La|Le|Les|Du|Des|Et|Au|Aux|Lès|Lez)(?=-)", lambda m: "-" + m.group(1).lower(), res)
    res = re.sub(r"\b([Xx][Ii]{0,2}|[Ii]{1,3}|[Ii][Vv]|[Vv][Ii]{0,3}|[Ii][Xx])\b", lambda m: m.group(1).upper(), res)
    return re.sub(r"\b(D|L)'([a-z])", lambda m: m.group(1).lower() + "'" + m.group(2).upper(), res)


def label(s):
    """Libellé d'une station : le flux ne fournit ni nom ni enseigne, on affiche donc l'adresse."""
    adr = pretty(s["adr"]) or "Adresse non renseignée"
    loc = " ".join(x for x in (s["cp"], pretty(s["ville"])) if x)
    return f"{adr}, {loc}" if loc else adr


def fuel_stats(items, fuel, topk=10):
    """items = [(distance_km, station)]. Renvoie None si aucun prix pour ce carburant."""
    rows = [(s["p"][fuel], d, s["id"], s) for d, s in items if fuel in s["p"]]
    if not rows:
        return None
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    prices = [r[0] for r in rows]
    return {"n": len(rows), "min": prices[0], "max": prices[-1],
            "avg": round(sum(prices) / len(prices), 3),
            "cheapest": [(p, d, s) for p, d, _, s in rows[:topk]],
            "priciest": (rows[-1][0], rows[-1][1], rows[-1][3])}


def _box(stations, lat, lon, km):
    dlat = km / 110.0
    dlon = km / (110.0 * max(math.cos(math.radians(lat)), 0.2))
    return [s for s in stations if abs(s["lat"] - lat) <= dlat and abs(s["lon"] - lon) <= dlon]


def national(stations):
    out = {}
    for f in FUELS:
        p = [s["p"][f] for s in stations if f in s["p"]]
        if p:
            out[f] = {"n": len(p), "avg": round(sum(p) / len(p), 3), "min": min(p)}
    return out


def group_stats(stations):
    """Statistiques d'un ensemble de stations (département, région)."""
    items = [(0.0, s) for s in stations]
    fs = {}
    for f in FUELS:
        st = fuel_stats(items, f, topk=5)
        if st:
            fs[f] = st
    return {"n": len(stations), "fuels": fs}


def build_geo(stations):
    """Départements et régions à partir des champs du jeu de données."""
    deps, regs = defaultdict(list), defaultdict(list)
    for s in stations:
        if s["dep_code"] and s["dep"]:
            deps[s["dep_code"]].append(s)
        if s["reg_code"] and s["reg"]:
            regs[s["reg_code"]].append(s)
    dep_info, reg_info = {}, {}
    for code, lst in deps.items():
        name = Counter(s["dep"] for s in lst).most_common(1)[0][0]
        rc = Counter(s["reg_code"] for s in lst).most_common(1)[0][0]
        dep_info[code] = {"code": code, "name": pretty(name), "reg_code": rc, "stations": lst}
    for code, lst in regs.items():
        name = Counter(s["reg"] for s in lst).most_common(1)[0][0]
        reg_info[code] = {"code": code, "name": pretty(name), "stations": lst}
    # slugs (collision département/région, ex. Guyane -> région suffixée)
    used = set()
    for code in sorted(dep_info):
        slug = slugify(dep_info[code]["name"]) or f"departement-{code}"
        if slug in ("prix-carburant",):
            slug += "-departement"
        dep_info[code]["slug"] = slug
        used.add(slug)
    for code in sorted(reg_info):
        slug = slugify(reg_info[code]["name"]) or f"region-{code}"
        if slug in used or slug == "prix-carburant":
            slug += "-region"
        reg_info[code]["slug"] = slug
        used.add(slug)
    for info in list(dep_info.values()) + list(reg_info.values()):
        info["stats"] = group_stats(info["stations"])
    return dep_info, reg_info


def commune_ranking(stations, fuel, min_n=3, top=5):
    """Communes (nom du flux) classées par prix moyen du carburant. Communes avec >= min_n stations."""
    g = defaultdict(list)
    for s in stations:
        if fuel in s["p"] and s["ville"]:
            g[norm_name(s["ville"])].append(s)
    rows = []
    for k, lst in g.items():
        if len(lst) >= min_n:
            avg = round(sum(x["p"][fuel] for x in lst) / len(lst), 3)
            name = Counter(x["ville"] for x in lst).most_common(1)[0][0]
            rows.append((avg, k, pretty(name), len(lst)))
    rows.sort()
    return rows[:top]


def build_city(v, stations):
    """Portée des statistiques : la commune si elle compte au moins 3 stations dans le flux (chaque ville a alors
    ses propres chiffres), sinon un rayon de RADIUS_KM autour du centre (comme le bloc « en direct »)."""
    lat, lon = v["lat"], v["lon"]
    cand = _box(stations, lat, lon, max(RADIUS_KM, COMMUNE_KM))
    near, commune_items = [], []
    cn = norm_name(v["nom"])
    for s in cand:
        d = haversine(lat, lon, s["lat"], s["lon"])
        if d <= RADIUS_KM:
            near.append((d, s))
        if d <= COMMUNE_KM and same_commune(norm_name(s["ville"]), cn):
            commune_items.append((d, s))
    near.sort(key=lambda t: (t[0], t[1]["id"]))
    commune_items.sort(key=lambda t: (t[0], t[1]["id"]))
    dep = reg = None
    if commune_items:
        dep = Counter((s["dep_code"], s["dep"]) for _, s in commune_items if s["dep_code"]).most_common(1)
        reg = Counter((s["reg_code"], s["reg"]) for _, s in commune_items if s["reg_code"]).most_common(1)
        dep = dep[0][0][0] if dep else None
        reg = reg[0][0][0] if reg else None
    use_commune = len(commune_items) >= MIN_COMMUNE_SCOPE
    items = commune_items if use_commune else near
    fuels = {}
    for f in FUELS:
        st = fuel_stats(items, f)
        if st:
            fuels[f] = st
    return {"v": v, "slug": v["slug"], "nom": v["nom"], "near": near, "n_rad": len(near),
            "n_commune": len(commune_items), "scope": "commune" if use_commune else "radius", "n_scope": len(items),
            "dep_code": dep, "reg_code": reg, "fuels": fuels}


def score_city(c, dep_info, nat):
    """Score interne de richesse (0-100) : détermine si la page est indexable."""
    pts = min(c["n_scope"], 40) + 5 * len(c["fuels"])
    if c["dep_code"] in dep_info:
        pts += 10
    if len(c.get("neighbors", [])) >= 2:
        pts += 10
    if c.get("compare_dep"):
        pts += 10
    c["score"] = pts
    c["indexable"] = (c["n_scope"] >= MIN_STATIONS_INDEX and len(c["fuels"]) >= MIN_FUELS_INDEX and pts >= MIN_SCORE_INDEX)
    return pts


def neighbor_candidates(cities):
    """Villes proches (même pays), classées par distance ; les liens seront filtrés sur les pages indexables."""
    res = {}
    for c in cities:
        v = c["v"]
        lst = []
        for o in cities:
            if o["slug"] == c["slug"]:
                continue
            d = haversine(v["lat"], v["lon"], o["v"]["lat"], o["v"]["lon"])
            if d <= NEIGHBOR_KM:
                lst.append((round(d, 1), o["slug"]))
        lst.sort()
        res[c["slug"]] = lst
    return res
