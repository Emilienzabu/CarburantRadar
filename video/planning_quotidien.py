"""Prépare deux sujets vérifiables pour les créneaux de la journée."""
import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from generator import data_fr
from generator.geo import haversine, norm_name, same_commune, slugify

from comparaisons import comparer
from donnees import ASTUCES, MAX_AGE_JOURS
from planning_editorial import CARBURANTS, SCENARIOS_APP, Sujet, choisir

RAYON_HOMONYMES_KM = 15
PROJETS_APP = tuple(Sujet(fiche[0], sujet=nom) for nom, fiche in SCENARIOS_APP.items())
CRENEAUX = ("matin", "soir")


def fiches_communes(villes, stations, maintenant):
    """Garde les prix récents disponibles dans la commune et l'adresse de la station."""
    groupes = defaultdict(list)
    for station in stations:
        if station["adr"] and station["ville"]:
            groupes[norm_name(station["ville"])].append(station)
    debut = maintenant - timedelta(days=MAX_AGE_JOURS)
    fin = maintenant + timedelta(hours=1)
    for ville in villes:
        nom = norm_name(ville["nom"])
        prix = defaultdict(dict)
        for commune, membres in groupes.items():
            if not same_commune(commune, nom):
                continue
            for s in membres:
                distance = haversine(ville["lat"], ville["lon"], s["lat"], s["lon"])
                if not distance <= RAYON_HOMONYMES_KM:
                    continue
                adresse = f"{s['adr']}, {s['cp']} {s['ville']}".strip()
                for carburant in s["dispo"]:
                    valeur = s["p"].get(carburant)
                    maj = data_fr.parse_ts(s["m"].get(carburant))
                    if valeur is None or maj is None or not debut <= maj <= fin:
                        continue
                    cle = s["id"] or adresse.casefold()
                    precedent = prix[carburant].get(cle)
                    if precedent is None or maj > precedent[0]:
                        prix[carburant][cle] = (maj, valeur, adresse)
        for carburant in CARBURANTS:
            stations_valides = prix[carburant].values()
            if len(stations_valides) >= 2:
                maj, valeur, adresse = min(stations_valides, key=lambda ligne: (ligne[1], ligne[2]))
                sujet = Sujet("ville_du_jour", (ville["slug"],), carburant)
                yield sujet, {"commune": ville["nom"], "adresse": adresse, "prix_litre": valeur,
                              "stations": len(stations_valides), "prix_releve_le": maj.isoformat(),
                              "verifie_le": maintenant.isoformat()}


def fiches_comparaisons(historique, jour, villes_utilisees):
    dates = sorted(d for d in historique["days"] if d <= jour.isoformat())
    if not dates:
        return
    derniere = dates[-1]
    precedente = next((d for d in reversed(dates[:-1])
                      if (date.fromisoformat(derniere) - date.fromisoformat(d)).days >= 7), None)
    jours = historique["days"]
    for carburant in CARBURANTS:
        villes = sorted(v for v, donnees in jours[derniere].items()
                        if v not in villes_utilisees and carburant in donnees
                        and donnees[carburant][0] == "c" and donnees[carburant][1] >= 2)
        paires = [((a, derniere), (b, derniere)) for a, b in zip(villes, villes[1:])]
        if precedente:
            paires += [((ville, precedente), (ville, derniere)) for ville in villes]
        for gauche, droite in paires:
            try:
                fiche = comparer(historique, carburant, gauche, droite)
            except ValueError:
                continue
            v = tuple(dict.fromkeys((gauche[0], droite[0])))
            yield Sujet(fiche["categorie"], v, carburant), fiche


def planifier(jour, villes, stations, historique_prix, publications, maintenant):
    """Renvoie uniquement les sujets encore disponibles pour ce jour."""
    publications = list(publications)
    villes_utilisees = {v for _, sujet in publications for v in sujet.villes}
    communes = fiches_communes((v for v in villes if v["slug"] not in villes_utilisees), stations, maintenant)
    sujets = dict(communes)
    sujets.update((Sujet("astuce", sujet=a["titre"]), a) for a in ASTUCES if not a.get("app_uniquement"))
    sujets.update((s, {"scenario": s.sujet}) for s in PROJETS_APP)
    sujets.update(fiches_comparaisons(historique_prix, jour, villes_utilisees))
    choix = choisir(jour, sujets, publications)
    return [{**asdict(s), "donnees": sujets[s]} for s in choix]


def historique_editorial(lignes, jour):
    """Un même créneau peut arriver des deux plateformes."""
    historiques, vus, occupes = [], {}, set()
    for ligne in lignes:
        cle = ligne.get("id_video", "")
        date_slot, _, creneau = cle.partition(":") if isinstance(cle, str) else ("", "", "")
        if creneau not in CRENEAUX:
            date_slot, creneau = ligne.get("jour"), ligne.get("creneau")
        date_publication = date.fromisoformat(date_slot)
        if date_publication > jour:
            continue
        categorie = ligne["categorie"]
        villes = tuple(ligne.get("villes") or ())
        if categorie == "ville":
            categorie = "ville_du_jour"
            if not villes and ligne.get("ville"):
                villes = (slugify(ligne["ville"]),)
        sujet = Sujet(categorie, villes, ligne.get("carburant"), ligne.get("sujet"))
        if creneau in CRENEAUX:
            identite = (date_publication, creneau)
            if identite in vus:
                if vus[identite] != sujet:
                    raise ValueError(f"Sujets contradictoires pour {date_publication} {creneau}")
                continue
            vus[identite] = sujet
            if date_publication == jour:
                occupes.add(creneau)
        elif date_publication == jour:
            raise ValueError("Le créneau d’une publication du jour est requis")
        historiques.append((date_publication, sujet))
    return historiques, occupes


def preparer(jour, lignes, maintenant, historique_prix=RACINE / "france/prix-carburant/history.json", stations=None):
    publications, occupes = historique_editorial(lignes, jour)
    if len(occupes) == len(CRENEAUX):
        return []
    villes = json.loads((RACINE / "generator/villes.json").read_text(encoding="utf-8"))["villes"]
    villes = (v for v in villes if v["pays"] == "france")
    historique = json.loads(historique_prix.read_text(encoding="utf-8"))
    releves, _ = data_fr.load(stations)
    plan = planifier(jour, villes, releves, historique, publications, maintenant)
    for creneau, sujet in zip((c for c in CRENEAUX if c not in occupes), plan):
        sujet["creneau"] = creneau
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jour", type=date.fromisoformat)
    parser.add_argument("--historique-prix", type=Path, default=RACINE / "france/prix-carburant/history.json")
    parser.add_argument("--historique-publications", type=Path,
                        help="Reçus du registre Cloudflare ou sujets déjà publiés avec jour et créneau")
    parser.add_argument("--stations", type=Path, help="Export officiel JSON local pour préparer un aperçu")
    args = parser.parse_args()
    maintenant = datetime.now(timezone.utc)
    jour = args.jour or maintenant.astimezone(ZoneInfo("Europe/Paris")).date()
    lignes = (json.loads(args.historique_publications.read_text(encoding="utf-8"))
              if args.historique_publications else [])
    plan = preparer(jour, lignes, maintenant, args.historique_prix, args.stations)
    print(json.dumps({"jour": jour.isoformat(), "sujets": plan}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
