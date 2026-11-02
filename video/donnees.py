"""Données de la vidéo : prix officiels (data.economie.gouv.fr), choix du contenu, calculs et textes.

Règle : aucun chiffre inventé. Tout ce qui est affiché ou dit vient du flux officiel du jour
(les "astuces" sont des conseils généraux, sans chiffres).
"""
import datetime as dt
import random
import statistics

import requests

API = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/records")

LITRES = 50
MIN_STATIONS = 8        # en dessous, la comparaison n'a pas de sens : on passe à la ville suivante
MAX_AGE_JOURS = 5       # prix plus vieux que ça = ignoré
PRIX_MIN_OK, PRIX_MAX_OK = 0.8, 3.5


def _v(nom, slug, lat, lon, rayon, poids):
    return {"nom": nom, "slug": slug, "lat": lat, "lon": lon, "rayon": rayon, "poids": poids}


# poids = fréquence relative : les grandes villes reviennent le plus souvent
VILLES = [
    _v("Paris", "paris", 48.8566, 2.3522, 6500, 6),
    _v("Marseille", "marseille", 43.2965, 5.3698, 9000, 6),
    _v("Lyon", "lyon", 45.7640, 4.8357, 8000, 5),
    _v("Toulouse", "toulouse", 43.6047, 1.4442, 8000, 5),
    _v("Nice", "nice", 43.7102, 7.2620, 7000, 4),
    _v("Bordeaux", "bordeaux", 44.8378, -0.5792, 8000, 4),
    _v("Nantes", "nantes", 47.2184, -1.5536, 8000, 4),
    _v("Montpellier", "montpellier", 43.6108, 3.8767, 8000, 4),
    _v("Lille", "lille", 50.6292, 3.0573, 8000, 4),
    _v("Strasbourg", "strasbourg", 48.5734, 7.7521, 8000, 4),
    _v("Rennes", "rennes", 48.1173, -1.6778, 8000, 3),
    _v("Toulon", "toulon", 43.1242, 5.9280, 8000, 3),
    _v("Aix-en-Provence", "aix-en-provence", 43.5297, 5.4474, 8000, 3),
    _v("Grenoble", "grenoble", 45.1885, 5.7245, 8000, 3),
    _v("Dijon", "dijon", 47.3220, 5.0415, 8000, 2),
    _v("Reims", "reims", 49.2583, 4.0317, 8000, 2),
    _v("Saint-Étienne", "saint-etienne", 45.4397, 4.3872, 8000, 2),
    _v("Le Havre", "le-havre", 49.4944, 0.1079, 8000, 2),
    _v("Angers", "angers", 47.4784, -0.5632, 8000, 2),
    _v("Nîmes", "nimes", 43.8367, 4.3601, 8000, 2),
    _v("Clermont-Ferrand", "clermont-ferrand", 45.7772, 3.0870, 8000, 2),
    _v("Brest", "brest", 48.3904, -4.4861, 8000, 2),
    _v("Tours", "tours", 47.3941, 0.6848, 8000, 2),
    _v("Perpignan", "perpignan", 42.6887, 2.8948, 8000, 2),
    _v("Metz", "metz", 49.1193, 6.1757, 8000, 2),
    _v("Rouen", "rouen", 49.4432, 1.0999, 8000, 2),
    _v("Aubagne", "aubagne", 43.2927, 5.5708, 7000, 2),
    _v("Le Mans", "le-mans", 48.0061, 0.1996, 8000, 1),
    _v("Amiens", "amiens", 49.8941, 2.2958, 8000, 1),
    _v("Limoges", "limoges", 45.8336, 1.2611, 8000, 1),
    _v("Besançon", "besancon", 47.2378, 6.0241, 8000, 1),
    _v("Orléans", "orleans", 47.9029, 1.9093, 8000, 1),
    _v("Caen", "caen", 49.1829, -0.3707, 8000, 1),
    _v("Nancy", "nancy", 48.6921, 6.1844, 8000, 1),
]
VILLES_PAR_SLUG = {v["slug"]: v for v in VILLES}
VILLES_POIDS = {v["slug"]: v["poids"] for v in VILLES}
GRANDES_VILLES = ["paris", "marseille", "lyon", "toulouse", "nice", "bordeaux",
                  "nantes", "montpellier", "lille", "strasbourg", "rennes"]

# clé -> (champ prix, champ date, libellé affiché, libellé prononcé, hashtag)
CARBURANTS = {
    "gazole": ("gazole_prix", "gazole_maj", "Gazole", "gazole", "gazole"),
    "e10": ("e10_prix", "e10_maj", "SP95-E10", "sans plomb 95 E10", "sp95"),
    "sp98": ("sp98_prix", "sp98_maj", "SP98", "sans plomb 98", "sp98"),
    "e85": ("e85_prix", "e85_maj", "E85", "éthanol E 85", "e85"),
    "gplc": ("gplc_prix", "gplc_maj", "GPL", "G P L", "gpl"),
}
ARTICLE_VOIX = {"gazole": "le gazole", "e10": "le sans plomb 95 E10", "sp98": "le sans plomb 98",
                "e85": "l'éthanol E 85", "gplc": "le G P L"}
ARTICLE_TXT = {"gazole": "le gazole", "e10": "le SP95-E10", "sp98": "le SP98", "e85": "l'E85", "gplc": "le GPL"}
# les carburants les plus utilisés reviennent souvent, les autres très rarement
CARBURANTS_POIDS = {"gazole": 17, "e10": 15, "sp98": 5, "e85": 2, "gplc": 1}
CARBURANTS_CLASSEMENT = {"gazole": 17, "e10": 15, "sp98": 3}
FORMATS_POIDS = {"ville": 5, "classement": 3, "astuce": 2}


# ---------- formats français ----------

def fr_prix3(p):
    return f"{p:.3f}".replace(".", ",")


def fr_eur(x):
    return f"{x:.2f}".replace(".", ",")


def voix_montant(x):
    """8,95 -> '8 euros 95' (lecture naturelle pour la voix)."""
    total = int(round(x * 100))
    e, c = divmod(total, 100)
    mot = "euro" if e <= 1 else "euros"
    return f"{e} {mot}" if c == 0 else f"{e} {mot} {c}"


voix_prix = voix_montant


# ---------- choix du contenu (déterministe) ----------

def pioche(nom, poids, k):
    """k-ième élément d'une suite qui respecte les poids (paquet mélangé, rejoué en boucle).

    Pas de hasard "pur" : chaque élément revient en proportion de son poids, sans trop de répétitions.
    """
    paquet = [x for x, w in poids.items() for _ in range(w)]
    n = len(paquet)
    cycle, idx = divmod(k, n)
    random.Random(f"{nom}-{cycle}").shuffle(paquet)
    for i in range(1, n):  # évite deux éléments identiques d'affilée
        if paquet[i] == paquet[i - 1]:
            for j in range(i + 1, n):
                if paquet[j] != paquet[i]:
                    paquet[i], paquet[j] = paquet[j], paquet[i]
                    break
    return paquet[idx]


def plan_du_jour(k, format=None, ville=None, carburant=None):
    """Décide quoi publier pour la k-ième publication (2 par jour)."""
    fmt = format or pioche("format", FORMATS_POIDS, k)
    if fmt == "astuce":
        i = pioche("astuce", {i: 1 for i in range(len(ASTUCES))}, k)
        return {"format": "astuce", "astuce": ASTUCES[i]}
    if fmt == "classement":
        fuel = carburant or pioche("classement", CARBURANTS_CLASSEMENT, k)
        return {"format": "classement", "carburant": fuel}
    fuel = carburant or pioche("carburant", CARBURANTS_POIDS, k)
    if ville:
        if ville not in VILLES_PAR_SLUG:
            raise SystemExit(f"Ville inconnue : {ville}. Possibles : {', '.join(VILLES_PAR_SLUG)}")
        candidats = [VILLES_PAR_SLUG[ville]]
    else:
        slugs = []
        for d in range(0, 40):
            s = pioche("ville", VILLES_POIDS, k + d)
            if s not in slugs:
                slugs.append(s)
        candidats = [VILLES_PAR_SLUG[s] for s in slugs[:8]]
    return {"format": "ville", "carburant": fuel, "villes": candidats}


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


def _uniques(stations):
    """Trie par prix et garde une seule entrée par adresse (le flux contient parfois des doublons)."""
    vues, res = set(), []
    for s in sorted(stations, key=lambda s: s["prix"]):
        if s["adresse"] in vues:
            continue
        vues.add(s["adresse"])
        res.append(s)
    return res


def construire_ville(ville, carburant, stations):
    """Format "ville" : 4 scènes. Renvoie None s'il n'y a pas assez de stations."""
    uniques = _uniques(stations)
    if len(uniques) < MIN_STATIONS:
        return None
    prix = [s["prix"] for s in uniques]
    moy = statistics.mean(prix)
    mini, maxi = prix[0], prix[-1]
    _, _, label, voix, tag = CARBURANTS[carburant]
    return {
        "format": "ville",
        "ville": ville["nom"], "slug": ville["slug"], "carburant": carburant,
        "carburant_label": label, "carburant_voix": voix, "carburant_tag": tag,
        "art_voix": ARTICLE_VOIX[carburant], "art_txt": ARTICLE_TXT[carburant],
        "n_stations": len(uniques),
        "prix_min": mini, "prix_moy": moy, "prix_max": maxi,
        "top3": uniques[:3],
        "litres": LITRES,
        "ecart_plein": (maxi - mini) * LITRES,
        "cout_min": mini * LITRES, "cout_moy": moy * LITRES,
        "eco_plein": (moy - mini) * LITRES,
        "hook_pill": f"{label.upper()} · {ville['nom'].upper()}",
        "hook_l2": "selon la station",
    }


def construire_classement(carburant, villes_prix):
    """Format "classement" : villes_prix = [(nom, slug, prix moyen)], renvoie None si trop peu de villes."""
    if len(villes_prix) < 5:
        return None
    villes_prix = sorted(villes_prix, key=lambda x: x[2])
    _, _, label, voix, tag = CARBURANTS[carburant]
    top5 = [{"nom": n, "slug": s, "prix_moy": p} for n, s, p in villes_prix[:5]]
    mini, maxi = villes_prix[0][2], villes_prix[-1][2]
    n = len(villes_prix)
    return {
        "format": "classement",
        "slug": "classement", "carburant": carburant,
        "carburant_label": label, "carburant_voix": voix, "carburant_tag": tag,
        "art_voix": ARTICLE_VOIX[carburant], "art_txt": ARTICLE_TXT[carburant],
        "n_villes": n, "villes": top5,
        "prix_min": mini, "prix_max": maxi,
        "litres": LITRES,
        "ecart_plein": (maxi - mini) * LITRES,
        "hook_pill": f"{label.upper()} · {n} GRANDES VILLES",
        "hook_l2": "entre deux grandes villes",
    }


def recuperer_classement(carburant, log=print):
    villes_prix = []
    for slug in GRANDES_VILLES:
        v = VILLES_PAR_SLUG[slug]
        try:
            uniques = _uniques(recuperer_stations(v, carburant))
        except Exception as e:
            log(f"  {v['nom']} : récupération impossible ({e})")
            continue
        if len(uniques) < MIN_STATIONS:
            continue
        villes_prix.append((v["nom"], slug, statistics.mean(s["prix"] for s in uniques)))
    return construire_classement(carburant, villes_prix)


# ---------- astuces (conseils généraux, sans chiffres) ----------

ASTUCES = [
    {"titre": "3 erreurs qui font payer ton plein plus cher",
     "points": ["Remplir sur l'autoroute, sauf urgence",
                "Chercher une station quand la jauge est dans le rouge",
                "Ne pas comparer les prix avant de partir"]},
    {"titre": "3 réflexes pour payer moins cher ton carburant",
     "points": ["Compare plusieurs stations autour de toi",
                "Prépare ton plein avant de partir",
                "Regarde le prix au litre, pas la marque"]},
    {"titre": "Pourquoi les prix changent d'une station à l'autre",
     "points": ["La concurrence locale tire les prix vers le bas",
                "Chaque enseigne choisit sa marge",
                "Autoroute et centre-ville ont des coûts plus élevés"]},
    {"titre": "E10 ou SP98 : comment choisir ?",
     "points": ["Vérifie ce que ton moteur accepte dans le carnet d'entretien",
                "Compare le prix au litre des deux carburants",
                "Si ton moteur accepte l'E10, compare avant de payer plus cher"]},
    {"titre": "3 gestes qui font baisser ta consommation",
     "points": ["Garde tes pneus bien gonflés",
                "Roule en souplesse, sans à-coups",
                "Retire le porte-bagages quand tu ne t'en sers pas"]},
    {"titre": "Faire un long trajet sans mauvaise surprise",
     "points": ["Repère une station avant de partir",
                "Fais le plein avant l'autoroute",
                "Utilise le mode Trajet de CarburantRadar"]},
    {"titre": "Utiliser CarburantRadar au quotidien",
     "points": ["Active les alertes de prix pour ta zone",
                "Enregistre tes lieux favoris : maison, travail",
                "Compare avant chaque plein, ça prend quelques secondes"]},
]


def construire_astuce(astuce):
    return {
        "format": "astuce", "slug": "astuce",
        "titre": astuce["titre"], "points": astuce["points"],
        "hook_pill": "ASTUCE",
    }


# ---------- démos (sans réseau) ----------

def info_demo(format="ville"):
    if format == "astuce":
        return construire_astuce(ASTUCES[0])
    if format == "classement":
        vp = [("Marseille", "marseille", 1.712), ("Toulouse", "toulouse", 1.731), ("Lyon", "lyon", 1.744),
              ("Nantes", "nantes", 1.752), ("Bordeaux", "bordeaux", 1.759), ("Paris", "paris", 1.801),
              ("Nice", "nice", 1.826)]
        return construire_classement("gazole", vp)
    stations = [
        {"prix": 1.689, "adresse": "12 Avenue Du Prado, Marseille"},
        {"prix": 1.709, "adresse": "Rue De Rome, Marseille"},
        {"prix": 1.719, "adresse": "Boulevard Michelet, Marseille"},
    ] + [{"prix": 1.74 + i * 0.016, "adresse": f"Adresse {i}, Marseille"} for i in range(9)]
    return construire_ville({"nom": "Marseille", "slug": "marseille"}, "gazole", stations)


# ---------- scènes : texte dit + sous-titre ----------

CTA_TEXTE = "Compare les prix près de chez toi, gratuitement, sur carburant radar point F R."
CTA_CAPTION = "Compare les prix près de chez toi, gratuitement, sur carburantradar.fr"


def scenes_texte(info):
    fmt = info["format"]
    av, at = info.get("art_voix", ""), info.get("art_txt", "")
    litres = info.get("litres", LITRES)
    cta = {"id": "cta", "min": 5.4, "texte": CTA_TEXTE, "caption": CTA_CAPTION}

    if fmt == "ville":
        v = info["ville"]
        p = [voix_prix(s["prix"]) for s in info["top3"]]
        return [
            {"id": "hook", "min": 4.4,
             "texte": f"À {v}, {av} peut varier de {voix_montant(info['ecart_plein'])} "
                      f"sur un plein de {litres} litres.",
             "caption": f"À {v}, {at} peut varier de {fr_eur(info['ecart_plein'])} € "
                        f"sur un plein de {litres} litres."},
            {"id": "top3", "min": 7.6,
             "texte": f"Aujourd'hui, la station la moins chère affiche {p[0]} le litre. "
                      f"Juste derrière, {p[1]}, puis {p[2]}.",
             "caption": f"Aujourd'hui, la moins chère affiche {fr_prix3(info['top3'][0]['prix'])} €. "
                        f"Puis {fr_prix3(info['top3'][1]['prix'])} € et {fr_prix3(info['top3'][2]['prix'])} €."},
            {"id": "eco", "min": 5.4,
             "texte": f"Bien choisir sa station, c'est {voix_montant(info['eco_plein'])} d'économie par plein, "
                      f"par rapport à une station moyenne.",
             "caption": f"Bien choisir sa station : {fr_eur(info['eco_plein'])} € d'économie par plein, "
                        f"par rapport à une station moyenne."},
            cta,
        ]

    if fmt == "classement":
        vs = info["villes"]
        return [
            {"id": "hook", "min": 4.4,
             "texte": f"Entre deux grandes villes, {av} peut coûter {voix_montant(info['ecart_plein'])} "
                      f"de différence sur un plein de {litres} litres.",
             "caption": f"{info['n_villes']} grandes villes comparées : jusqu'à {fr_eur(info['ecart_plein'])} € "
                        f"d'écart sur un plein de {litres} litres."},
            {"id": "rank", "min": 8.0,
             "texte": f"Aujourd'hui, c'est à {vs[0]['nom']} que {av} est le moins cher, "
                      f"à {voix_prix(vs[0]['prix_moy'])} le litre en moyenne. "
                      f"Ensuite, {vs[1]['nom']}, {vs[2]['nom']}, {vs[3]['nom']} et {vs[4]['nom']}.",
             "caption": f"Le moins cher aujourd'hui : {vs[0]['nom']}, "
                        f"{fr_prix3(vs[0]['prix_moy'])} € le litre en moyenne."},
            cta,
        ]

    # astuce : titre, puis les 3 conseils un par un
    pts = info["points"]
    debuts = ["D'abord", "Ensuite", "Enfin"]
    scenes = [{"id": "tiphook", "min": 3.8, "texte": info["titre"] + ".", "caption": None}]
    for i, pt in enumerate(pts):
        scenes.append({"id": "tip", "idx": i, "min": 3.8,
                       "texte": f"{debuts[i]} : {pt[0].lower() + pt[1:]}.", "caption": None})
    scenes.append(cta)
    return scenes


# ---------- textes de publication ----------

def textes_publication(info):
    fmt = info["format"]
    if fmt == "astuce":
        titre = info["titre"]
        liste = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(info["points"]))
        description = (f"{info['titre']}\n{liste}\n\nCompare les prix près de chez toi, gratuitement et sans compte : "
                       f"https://carburantradar.fr\n#Shorts #carburant #astuce #economies #prixcarburant")
        legende = (f"{info['titre']} — compare les prix près de chez toi sur carburantradar.fr (lien en bio) "
                   f"#carburant #astuce #economies #prixcarburant")
        return titre[:100], description[:600], legende[:600]

    label, tag = info["carburant_label"], info["carburant_tag"]
    if fmt == "classement":
        vs = info["villes"]
        titre = f"{label} : {vs[0]['nom']} est la ville la moins chère aujourd'hui ({fr_prix3(vs[0]['prix_moy'])} €)"
        liste = "\n".join(f"{i + 1}. {v['nom']} : {fr_prix3(v['prix_moy'])} €" for i, v in enumerate(vs))
        description = (f"{label} : prix moyen par ville aujourd'hui ({info['n_villes']} grandes villes comparées).\n"
                       f"{liste}\n\nCompare les prix près de chez toi, gratuitement et sans compte : "
                       f"https://carburantradar.fr\nDonnées officielles (data.economie.gouv.fr).\n"
                       f"#Shorts #carburant #{tag} #classement #prixcarburant")
        legende = (f"{label} : {vs[0]['nom']} est la ville la moins chère aujourd'hui ({fr_prix3(vs[0]['prix_moy'])} €), "
                   f"{vs[1]['nom']} et {vs[2]['nom']} suivent. Compare près de chez toi sur carburantradar.fr "
                   f"(lien en bio) #carburant #{tag} #prixcarburant")
        return titre[:100], description[:600], legende[:600]

    ville = info["ville"]
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
