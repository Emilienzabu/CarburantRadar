"""Planification éditoriale indépendante du workflow de publication."""
from collections import Counter
from dataclasses import dataclass
from datetime import date

LOCALES = {"ville_du_jour": 1, "ville_avant_maintenant": 1, "ville_contre_ville": 2}
CATEGORIES = LOCALES.keys() | {"astuce", "fonctionnement", "avantage"}
CARBURANTS = ("gazole", "e10", "sp98", "e85", "gplc", "sp95")
SCENARIOS_APP = {
    "rayon": ("fonctionnement", "Comment élargir le rayon dans Radar",
              "Change le rayon sous le choix du carburant pour chercher plus loin autour de toi."),
    "analyse": ("fonctionnement", "Comment lire l’évolution des prix dans Analyse",
                "Ouvre Analyse, déplie la moyenne de ta zone et choisis la période du graphique."),
    "carte": ("fonctionnement", "Comment repérer les prix sur la carte",
              "Ouvre Carte et repère les prix affichés au niveau des stations."),
    "detour": ("avantage", "Une station moins chère vaut-elle le détour ?",
               "Compare le coût estimé de ton trajet avec et sans détour à la station."),
}


@dataclass(frozen=True)
class Sujet:
    categorie: str
    villes: tuple[str, ...] = ()
    carburant: str | None = None
    sujet: str | None = None


def choisir(jour: date, candidats, historique):
    """Renvoie jusqu'à deux sujets supplémentaires. L'ordre des candidats tranche les égalités."""
    historique = list(historique)
    mois = Counter(s.categorie for d, s in historique if (d.year, d.month) == (jour.year, jour.month))
    villes = {ville for _, s in historique for ville in s.villes}
    sujets = {(s.categorie, s.sujet) for _, s in historique if s.sujet}
    carburants = Counter((s.categorie, s.carburant) for _, s in historique if s.carburant)
    retenus = []
    selection_du_jour = [s for d, s in historique if d == jour]
    candidats = list(candidats)
    for _ in range(max(0, 2 - sum(d == jour for d, _ in historique))):
        eligibles = [s for s in candidats if s.categorie in CATEGORIES
                     and len(s.villes) == LOCALES.get(s.categorie, 0)
                     and len(set(s.villes)) == len(s.villes)
                     and all(v and v not in villes for v in s.villes)
                     and (s.carburant in CARBURANTS if s.villes else s.carburant in (*CARBURANTS, None))
                     and (s.categorie == "ville_du_jour" or mois[s.categorie] < 2)
                     and (s.categorie in LOCALES or (s.sujet and (s.categorie, s.sujet) not in sujets))]
        if not eligibles:
            break
        derniere = selection_du_jour[-1].categorie if selection_du_jour else None
        categorie = next((s.categorie for s in eligibles if s.categorie != derniere), eligibles[0].categorie)
        s = min((s for s in eligibles if s.categorie == categorie),
                key=lambda s: carburants[s.categorie, s.carburant])
        retenus.append(s)
        selection_du_jour.append(s)
        villes.update(s.villes)
        sujets.add((s.categorie, s.sujet))
        mois[s.categorie] += 1
        carburants[s.categorie, s.carburant] += 1
    return retenus
