"""Exécute le créneau éditorial demandé et garde son sujet en cas d’envoi incertain."""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from comparatifs_beige import CARBURANTS, affichage_date, nom
from generate_video import WORKER_URL, ecrire_resume, publier
from metadonnees_video import ecrire_recu
from performance import (PLATEFORMES_ACTIVES, experience_appariee, garder_temoin,
                         musique_confirmee, plateformes_confirmees)
from planning_editorial import SCENARIOS_APP
from planning_quotidien import CRENEAUX, historique_editorial, preparer
from rendre_planning import rendre
from synchroniser_stats import appel, pages

PARIS = ZoneInfo("Europe/Paris")
URL_EDITORIALE = WORKER_URL.removesuffix("/api/upload") + "/api/editorial/upload"
HASHTAG_VILLE = "#prixcarburant"
FACTEURS_VILLE = {"musique": (3, 8), "hashtag": ("", HASHTAG_VILLE)}


def textes_publication(sujet, identifiant="", decisions=(), experience=None):
    fiche, categorie = sujet["donnees"], sujet["categorie"]
    fuel = sujet["carburant"]
    carburant = CARBURANTS[fuel][0] if fuel else ""
    if categorie == "ville_du_jour":
        prix = f"{fiche['prix_litre']:.3f}".replace(".", ",")
        titre = f"{fiche['commune']} · {carburant} à {prix} €/L"
        detail = f"{fiche['adresse']}. Minimum parmi {fiche['stations']} stations avec un prix récent dans la commune."
    elif categorie == "astuce":
        titre = fiche["titre"]
        detail = " • ".join(fiche["points"])
    elif categorie in ("fonctionnement", "avantage"):
        _, titre, detail = SCENARIOS_APP[fiche["scenario"]]
    else:
        a, b = fiche["valeurs"]
        gauche, droite = nom(a["ville"]), nom(b["ville"])
        titre = (f"{carburant} à {gauche} · avant et maintenant" if gauche == droite
                 else f"{carburant} · {gauche} et {droite}")
        detail = " • ".join(f"{nom(v['ville'])}, {affichage_date(v['date'])} · "
                            f"{v['prix']:.3f} €/L".replace(".", ",") for v in fiche["valeurs"])
    tags = f"#carburant #carburantradar{' #' + fuel if fuel else ''}"
    texte = f"{titre}\n{detail}\ncarburantradar.fr\n{tags}"
    cibles = ()
    if categorie == "ville_du_jour":
        if experience:
            if experience["facteur"] == "hashtag" and experience["bras"] == "variante":
                cibles = PLATEFORMES_ACTIVES
        elif not garder_temoin(identifiant + "/hashtag"):
            cibles = plateformes_confirmees("hashtag", categorie, "", HASHTAG_VILLE, decisions)
    youtube = f"{texte} #Shorts"
    return (titre[:100], f"{youtube} {HASHTAG_VILLE}" if "youtube" in cibles else youtube,
            f"{texte} {HASHTAG_VILLE}" if "instagram" in cibles else texte)


def images_mobiles(dossier):
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True)
    from capture_vitrine import capturer
    capturer(dossier)
    return dossier


def experience_du_jour(sujet, reservations, decisions):
    categorie = sujet["categorie"]
    if categorie != "ville_du_jour":
        return None
    essais = (r.get("experience") or {} for r in reservations)
    comptes = Counter(e.get("facteur") for e in essais if e.get("contexte") == categorie)
    a_terminer = [f for f in FACTEURS_VILLE if comptes[f] % 2]
    if a_terminer:
        facteur = a_terminer[0]
    else:
        ouverts = [f for f, (temoin, variante) in FACTEURS_VILLE.items()
                   if not PLATEFORMES_ACTIVES <= plateformes_confirmees(f, categorie, temoin, variante, decisions)]
        if not ouverts:
            return None
        # Après confirmation, un créneau hors essai sur deux applique les choix validés.
        musique = musique_confirmee((8,), 3, decisions, categorie)
        hashtag = plateformes_confirmees("hashtag", categorie, "", HASHTAG_VILLE, decisions)
        if (musique is not None or hashtag & PLATEFORMES_ACTIVES) and len(reservations) % 2:
            return None
        facteur = min(ouverts, key=lambda f: comptes[f])
    paire, ordre = divmod(comptes[facteur], 2)
    return experience_appariee(facteur, categorie, *FACTEURS_VILLE[facteur],
                               f"quotidien-{paire + 1}", ordre + 1)


def executer(session, cle, jour, creneau, sortie, maintenant):
    """Un créneau déjà connu conserve son sujet, même si le premier envoi est incertain."""
    identifiant = f"{jour}:{creneau}"
    # La route éditoriale vérifie aussi la disponibilité du journal anti-doublon.
    reservations = list(pages(session, "editorial"))
    lignes = reservations + list(pages(session, "publications"))
    _, occupes = historique_editorial(lignes, jour)
    if creneau in occupes:
        print(f"Créneau {identifiant} déjà enregistré.")
        return
    plan = preparer(jour, lignes, maintenant)
    sujet = next((s for s in plan if s["creneau"] == creneau), None)
    if sujet is None:
        raise RuntimeError(f"Aucun sujet éligible pour {identifiant}")

    captures = (images_mobiles(sortie.parent / "captures")
                if sujet["categorie"] in ("fonctionnement", "avantage") else None)
    decisions, experience = (), None
    try:
        decisions = appel(session, "GET", "decisions")["experiences"]
        experience = experience_du_jour(sujet, reservations, decisions)
        textes = textes_publication(sujet, identifiant, decisions, experience)
    except (OSError, RuntimeError, KeyError, TypeError, ValueError):
        decisions, experience = (), None
        textes = textes_publication(sujet)
        print("::warning::Rapport d’apprentissage indisponible. Variantes de référence utilisées.")
    rendre(sujet, identifiant, sortie, captures, decisions=decisions, experience=experience)
    fiche = json.loads(sortie.with_suffix(".creation.json").read_text(encoding="utf-8"))
    reservation = {k: fiche[k] for k in ("id_video", "categorie", "villes", "carburant", "sujet", "sha256")}
    if experience:
        reservation["experience"] = experience
    if not appel(session, "POST", "editorial", json=reservation)["reserve"]:
        print(f"Créneau {identifiant} réservé par une autre exécution.")
        return
    resultat = publier(sortie, None, cle, identifiant, textes=textes, url=URL_EDITORIALE)
    ecrire_resume(identifiant, {"format": sujet["categorie"]}, resultat)
    manquants = ecrire_recu(sortie, fiche, resultat.get("references", {}), datetime.now(timezone.utc))
    for plateforme in manquants:
        print(f"::warning::Identifiant manquant pour {plateforme}")
    fichier = sortie.with_suffix(".publications.json")
    if fichier.exists():
        for recu in json.loads(fichier.read_text(encoding="utf-8")):
            try:
                appel(session, "POST", "recu", json=recu)
            except (OSError, RuntimeError) as err:
                print(f"::warning::Archivage différé vers GitHub Actions ({type(err).__name__})")
    if resultat["etat"] != "complet":
        raise RuntimeError(f"Publication {identifiant} : {resultat['etat']}. Sujet conservé dans le registre.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--creneau", choices=CRENEAUX, required=True)
    parser.add_argument("--declenche-le", required=True, type=datetime.fromisoformat)
    parser.add_argument("--sortie", type=Path, required=True)
    args = parser.parse_args()
    if args.declenche_le.utcoffset() is None:
        parser.error("--declenche-le doit inclure son fuseau horaire.")
    maintenant = datetime.now(PARIS)
    jour = args.declenche_le.astimezone(PARIS).date()
    if jour != maintenant.date():
        print(f"Créneau du {jour} expiré. Jour courant {maintenant.date()}.")
        return
    cle = os.environ["VIDEO_API_KEY"]
    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {cle}"
        executer(session, cle, jour, args.creneau, args.sortie, maintenant)


if __name__ == "__main__":
    main()
