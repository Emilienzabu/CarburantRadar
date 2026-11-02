"""Données de la vidéo : prix officiels (data.economie.gouv.fr), calculs et textes.

Règle : aucun chiffre inventé. Tout ce qui est affiché ou dit vient du flux officiel du jour.
"""
import datetime as dt
import statistics

import requests

API = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/records")

LITRES = 50
MIN_STATIONS = 8        # en dessous, la comparaison n'a pas de sens : on passe à la ville suivante
MAX_AGE_JOURS = 5       # prix plus vieux que ça = ignoré
PRIX_MIN_OK, PRIX_MAX_OK = 0.8, 3.5

VILLES = [
    {"nom": "Marseille", "slug": "marseille", "lat": 43.2965, "lon": 5.3698, "rayon": 9000},
    {"nom": "Paris", "slug": "paris", "lat": 48.8566, "lon": 2.3522, "rayon": 6500},
    {"nom": "Lyon", "slug": "lyon", "lat": 45.7640, "lon": 4.8357, "rayon": 8000},
    {"nom": "Toulouse", "slug": "toulouse", "lat": 43.6047, "lon": 1.4442, "rayon": 8000},
    {"nom": "Nice", "slug": "nice", "lat": 43.7102, "lon": 7.2620, "rayon": 7000},
    {"nom": "Nantes", "slug": "nantes", "lat": 47.2184, "lon": -1.5536, "rayon": 8000},
    {"nom": "Montpellier", "slug": "montpellier", "lat": 43.6108, "lon": 3.8767, "rayon": 8000},
    {"nom": "Strasbourg", "slug": "strasbourg", "lat": 48.5734, "lon": 7.7521, "rayon": 8000},
    {"nom": "Bordeaux", "slug": "bordeaux", "lat": 44.8378, "lon": -0.5792, "rayon": 8000},
    {"nom": "Lille", "slug": "lille", "lat": 50.6292, "lon": 3.0573, "rayon": 8000},
    {"nom": "Rennes", "slug": "rennes", "lat": 48.1173, "lon": -1.6778, "rayon": 8000},
    {"nom": "Aix-en-Provence", "slug": "aix-en-provence", "lat": 43.5297, "lon": 5.4474, "rayon": 8000},
    {"nom": "Toulon", "slug": "toulon", "lat": 43.1242, "lon": 5.9280, "rayon": 8000},
    {"nom": "Aubagne", "slug": "aubagne", "lat": 43.2927, "lon": 5.5708, "rayon": 7000},
    {"nom": "Grenoble", "slug": "grenoble", "lat": 45.1885, "lon": 5.7245, "rayon": 8000},
    {"nom": "Dijon", "slug": "dijon", "lat": 47.3220, "lon": 5.0415, "rayon": 8000},
]

# clé -> (champ prix, champ date, libellé affiché, libellé prononcé, hashtag)
CARBURANTS = {
    "gazole": ("gazole_prix", "gazole_maj", "Gazole", "gazole", "gazole"),
    "e10": ("e10_prix", "e10_maj", "SP95-E10", "sans plomb 95 E10", "sp95"),
    "sp98": ("sp98_prix", "sp98_maj", "SP98", "sans plomb 98", "sp98"),
}
ORDRE_CARBURANTS = ["gazole", "e10", "sp98"]


# ---------- formats français ----------

def fr_prix3(p):
    return f"{p:.3f}".replace(".", ",")


def fr_eur(x):
    return f"{x:.2f}".replace(".", ",")


def voix_prix(p):
    """1,689 -> '1 euro 69' (lecture naturelle pour la voix)."""
    total = int(round(p * 100))
    e, c = divmod(total, 100)
    mot = "euro" if e <= 1 else "euros"
    return f"{e} {mot}" if c == 0 else f"{e} {mot} {c}"


def voix_montant(x):
    total = int(round(x * 100))
    e, c = divmod(total, 100)
    mot = "euro" if e <= 1 else "euros"
    return f"{e} {mot}" if c == 0 else f"{e} {mot} {c}"


# ---------- choix du jour ----------

def choisir(jour=None, ville=None, carburant=None):
    """Renvoie la liste ordonnée des (ville, carburant) à essayer (rotation déterministe sur le jour)."""
    jour = jour or dt.date.today()
    n = jour.toordinal()
    if ville:
        villes = [v for v in VILLES if v["slug"] == ville]
        if not villes:
            raise SystemExit(f"Ville inconnue : {ville}. Possibles : {', '.join(v['slug'] for v in VILLES)}")
    else:
        start = n % len(VILLES)
        villes = [VILLES[(start + k) % len(VILLES)] for k in range(len(VILLES))]
    fuel = carburant or ORDRE_CARBURANTS[n % len(ORDRE_CARBURANTS)]
    if fuel not in CARBURANTS:
        raise SystemExit(f"Carburant inconnu : {fuel}. Possibles : {', '.join(CARBURANTS)}")
    return [(v, fuel) for v in villes]


# ---------- récupération ----------

def _parse_date(s):
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def recuperer_stations(ville, carburant):
    champ_prix, champ_maj, *_ = CARBURANTS[carburant]
    stations, offset = [], 0
    while offset < 1500:
        params = {
            "where": f"{champ_prix} is not null",
            "geofilter.distance": f"{ville['lat']},{ville['lon']},{ville['rayon']}",
            "limit": 100,
            "offset": offset,
        }
        r = requests.get(API, params=params, timeout=40)
        r.raise_for_status()
        res = r.json().get("results", [])
        stations.extend(res)
        if len(res) < 100:
            break
        offset += 100

    now = dt.datetime.now(dt.timezone.utc)
    ok = []
    for s in stations:
        p = s.get(champ_prix)
        if not isinstance(p, (int, float)) or not (PRIX_MIN_OK < p < PRIX_MAX_OK):
            continue
        maj = _parse_date(s.get(champ_maj) or "")
        if maj is None or (now - maj).days > MAX_AGE_JOURS:
            continue
        adresse = (s.get("adresse") or "").strip().title()
        v = (s.get("ville") or ville["nom"]).strip().title()
        ok.append({"prix": float(p), "adresse": f"{adresse}, {v}" if adresse else v})
    return ok


def construire_info(ville, carburant, stations):
    """Calcule toutes les valeurs affichées. Renvoie None si pas assez de stations."""
    if len(stations) < MIN_STATIONS:
        return None
    stations = sorted(stations, key=lambda s: s["prix"])
    # une seule entrée par adresse (le flux contient parfois des doublons)
    vues, uniques = set(), []
    for s in stations:
        if s["adresse"] in vues:
            continue
        vues.add(s["adresse"])
        uniques.append(s)
    if len(uniques) < MIN_STATIONS:
        return None
    prix = [s["prix"] for s in uniques]
    moy = statistics.mean(prix)
    mini, maxi = prix[0], prix[-1]
    _, _, label, voix, tag = CARBURANTS[carburant]
    return {
        "ville": ville["nom"], "slug": ville["slug"], "carburant": carburant,
        "carburant_label": label, "carburant_voix": voix, "carburant_tag": tag,
        "n_stations": len(uniques),
        "prix_min": mini, "prix_moy": moy, "prix_max": maxi,
        "top3": uniques[:3],
        "litres": LITRES,
        "ecart_plein": (maxi - mini) * LITRES,
        "cout_min": mini * LITRES, "cout_moy": moy * LITRES,
        "eco_plein": (moy - mini) * LITRES,
    }


def info_demo():
    stations = [
        {"prix": 1.689, "adresse": "12 Avenue Du Prado, Marseille"},
        {"prix": 1.709, "adresse": "Rue De Rome, Marseille"},
        {"prix": 1.719, "adresse": "Boulevard Michelet, Marseille"},
    ] + [{"prix": 1.74 + i * 0.016, "adresse": f"Adresse {i}, Marseille"} for i in range(9)]
    ville = {"nom": "Marseille", "slug": "marseille"}
    return construire_info(ville, "gazole", stations)


# ---------- textes ----------

def scenes_texte(info):
    """Les 4 scènes : identifiant, durée minimale, texte dit (et affiché en sous-titre)."""
    p = [voix_prix(s["prix"]) for s in info["top3"]]
    v, f = info["ville"], info["carburant_voix"]
    return [
        {"id": "hook", "min": 4.6,
         "texte": f"À {v}, le {f} peut varier de {voix_montant(info['ecart_plein'])} "
                  f"sur un plein de {info['litres']} litres.",
         "caption": f"À {v}, le {f} peut varier de {fr_eur(info['ecart_plein'])} € "
                    f"sur un plein de {info['litres']} litres."},
        {"id": "top3", "min": 8.0,
         "texte": f"Aujourd'hui, la station la moins chère affiche {p[0]} le litre. "
                  f"Juste derrière, {p[1]}, puis {p[2]}.",
         "caption": f"Aujourd'hui, la moins chère affiche {fr_prix3(info['top3'][0]['prix'])} €. "
                    f"Puis {fr_prix3(info['top3'][1]['prix'])} € et {fr_prix3(info['top3'][2]['prix'])} €."},
        {"id": "eco", "min": 5.6,
         "texte": f"Bien choisir sa station, c'est {voix_montant(info['eco_plein'])} d'économie par plein, "
                  f"par rapport à une station moyenne.",
         "caption": f"Bien choisir sa station : {fr_eur(info['eco_plein'])} € d'économie par plein, "
                    f"par rapport à une station moyenne."},
        {"id": "cta", "min": 5.6,
         "texte": "Compare les prix près de chez toi, gratuitement, sur carburant radar point F R.",
         "caption": "Compare les prix près de chez toi, gratuitement, sur carburantradar.fr"},
    ]


def textes_publication(info):
    ville, label, tag = info["ville"], info["carburant_label"], info["carburant_tag"]
    mini, maxi = fr_prix3(info["prix_min"]), fr_prix3(info["prix_max"])
    hashtag_ville = info["slug"].replace("-", "")
    titre = f"{label} à {ville} : {mini} € le moins cher aujourd'hui"
    description = (
        f"{label} à {ville} aujourd'hui : de {mini} € à {maxi} € le litre selon la station "
        f"({info['n_stations']} stations comparées). Compare les prix près de chez toi, "
        f"gratuitement et sans compte : https://carburantradar.fr\n"
        f"Données officielles (data.economie.gouv.fr).\n"
        f"#Shorts #carburant #{tag} #{hashtag_ville} #prixcarburant #economies"
    )
    legende = (
        f"{label} à {ville} : de {mini} € à {maxi} € le litre selon la station. "
        f"Compare les prix près de chez toi sur carburantradar.fr (lien en bio) "
        f"#carburant #{tag} #{hashtag_ville} #prixcarburant #economies"
    )
    return titre[:100], description[:600], legende[:600]
