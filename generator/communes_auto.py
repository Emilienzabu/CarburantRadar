"""Communes françaises découvertes automatiquement dans le flux officiel (en plus de villes.json).

Principe : on regroupe les stations du flux par commune (nom normalisé + département). Une commune devient une page si elle
compte assez de stations avec un prix. Rien n'est inventé : nom, département, coordonnées (moyenne des stations) et
chiffres viennent tous du jeu de données.

Règles de stabilité des URLs :
  - les villes de villes.json gardent leur URL et leur contenu (une commune déjà présente est ignorée ici) ;
  - un nom de commune présent dans plusieurs départements est TOUJOURS suffixé par le code département
    (ex. /saint-denis-93/), quel que soit le seuil, pour que l'URL ne change pas quand une homonyme apparaît ;
  - une page déjà publiée est conservée tant qu'elle garde AUTO_KEEP_STATIONS stations (évite les 404 sur un petit écart).
"""
import re
from collections import Counter, defaultdict

import stats_fr as S
from geo import haversine, norm_name, slugify

AUTO_MIN_STATIONS = 6    # stations avec au moins un prix dans la commune pour créer une nouvelle page
AUTO_KEEP_STATIONS = 4   # seuil pour conserver une page déjà publiée
AUTO_MIN_FUELS = 2       # carburants différents relevés dans la commune
MATCH_KM = 30            # une commune du flux de même nom qu'une ville de villes.json, à moins de 30 km, est la même

_ARR_NORM = re.compile(r"\s+\d{1,2}\s?(ER|E|EME|EM)?$")                 # "MARSEILLE 6EME" -> "MARSEILLE" (nom normalisé)
_ARR_RAW = re.compile(r"\s+\d{1,2}\s?(?:er|e|eme|ème|em)?$", re.I)      # idem sur le libellé brut


def _key(ville):
    return _ARR_NORM.sub("", norm_name(ville))


def display_name(raw):
    """Libellé d'affichage d'une commune à partir du flux (souvent en MAJUSCULES)."""
    name = S.pretty(_ARR_RAW.sub("", raw.strip()))
    # élisions en milieu de nom en minuscules : Villeneuve-d'Ascq, L'Isle-d'Abeau
    return re.sub(r"(?<=[\s-])([DL])'", lambda m: m.group(1).lower() + "'", name)


def previous_slugs(manifest_paths):
    """Slugs des pages villes déjà publiées (d'après generated_pages.json)."""
    out = set()
    for p in manifest_paths or []:
        parts = [x for x in p.strip("/").split("/") if x]
        if len(parts) == 3 and parts[0] == "france" and parts[1] == "prix-carburant":
            out.add(parts[2])
    return out


def discover(stations, fr_villes, prev_slugs=None):
    """Renvoie la liste des nouvelles « villes » (même forme que villes.json + clés `auto` et `_members`)."""
    prev_slugs = prev_slugs or set()
    groups = defaultdict(list)        # (clé, département) -> toutes les stations
    for s in stations:
        if s["ville"] and s["dep_code"]:
            k = _key(s["ville"])
            if k:
                groups[(k, s["dep_code"])].append(s)
    deps_by_key = defaultdict(set)
    for (k, dep) in groups:
        deps_by_key[k].add(dep)

    existing = [(norm_name(v["nom"]), v) for v in fr_villes]
    used = {v["slug"] for v in fr_villes}
    out = []
    for (k, dep), lst in sorted(groups.items()):
        priced = [s for s in lst if s["p"]]
        fuels = {f for s in priced for f in s["p"]}
        if len(fuels) < AUTO_MIN_FUELS:
            continue
        lat = round(sum(s["lat"] for s in lst) / len(lst), 4)
        lon = round(sum(s["lon"] for s in lst) / len(lst), 4)
        # déjà couverte par une ville de villes.json ?
        same = [v for n, v in existing if n == k]
        if any(haversine(lat, lon, v["lat"], v["lon"]) <= MATCH_KM for v in same):
            continue
        raw = Counter(s["ville"] for s in lst).most_common(1)[0][0]
        base = display_name(raw)
        base_slug = slugify(base)
        if not base_slug:
            continue
        ambiguous = len(deps_by_key[k]) > 1 or bool(same)
        slug = f"{base_slug}-{dep.lower()}" if ambiguous else base_slug
        nom = f"{base} ({dep})" if ambiguous else base
        if slug in used:                      # collision (ex. slug manuel identique) : on suffixe par le département
            slug = f"{base_slug}-{dep.lower()}"
            nom = f"{base} ({dep})"
            if slug in used:
                continue
        need = AUTO_KEEP_STATIONS if slug in prev_slugs else AUTO_MIN_STATIONS
        if len(priced) < need:
            continue
        used.add(slug)
        out.append({"pays": "france", "slug": slug, "nom": nom, "lat": lat, "lon": lon, "auto": True, "_members": lst})
    return out


def build_city(v, stations):
    """Même structure que stats_fr.build_city, mais la commune est définie par ses stations (pas par le nom)."""
    lat, lon = v["lat"], v["lon"]
    near = []
    for s in S._box(stations, lat, lon, S.RADIUS_KM):
        d = haversine(lat, lon, s["lat"], s["lon"])
        if d <= S.RADIUS_KM:
            near.append((d, s))
    commune_items = [(haversine(lat, lon, s["lat"], s["lon"]), s) for s in v["_members"]]
    near.sort(key=lambda t: (t[0], t[1]["id"]))
    commune_items.sort(key=lambda t: (t[0], t[1]["id"]))
    dep = Counter(s["dep_code"] for _, s in commune_items if s["dep_code"]).most_common(1)
    reg = Counter(s["reg_code"] for _, s in commune_items if s["reg_code"]).most_common(1)
    dep = dep[0][0] if dep else None
    reg = reg[0][0] if reg else None
    use_commune = len(commune_items) >= S.MIN_COMMUNE_SCOPE
    items = commune_items if use_commune else near
    fuels = {}
    for f in S.FUELS:
        st = S.fuel_stats(items, f)
        if st:
            fuels[f] = st
    return {"v": v, "slug": v["slug"], "nom": v["nom"], "near": near, "n_rad": len(near),
            "n_commune": len(commune_items), "scope": "commune" if use_commune else "radius", "n_scope": len(items),
            "dep_code": dep, "reg_code": reg, "fuels": fuels}
