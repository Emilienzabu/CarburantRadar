"""Exécute le créneau éditorial demandé et garde son sujet en cas d’envoi incertain."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from comparatifs_beige import CARBURANTS, affichage_date, nom
from generate_video import WORKER_URL, ecrire_resume, publier
from metadonnees_video import ecrire_recu
from planning_quotidien import CRENEAUX, historique_editorial, preparer
from rendre_planning import rendre
from synchroniser_stats import appel, pages

PARIS = ZoneInfo("Europe/Paris")
URL_EDITORIALE = WORKER_URL.removesuffix("/api/upload") + "/api/editorial/upload"


def textes_publication(sujet):
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
    elif categorie == "fonctionnement":
        titre = "Comment élargir le rayon dans Radar"
        detail = "Appuie sur 10 km sous le choix du carburant pour changer le rayon autour de toi."
    elif categorie == "avantage":
        titre = "Une station moins chère vaut-elle le détour ?"
        detail = "Compare le coût estimé de ton trajet avec et sans détour à la station."
    else:
        a, b = fiche["valeurs"]
        gauche, droite = nom(a["ville"]), nom(b["ville"])
        titre = (f"{carburant} à {gauche} · avant et maintenant" if gauche == droite
                 else f"{carburant} · {gauche} et {droite}")
        detail = " • ".join(f"{nom(v['ville'])}, {affichage_date(v['date'])} · "
                            f"{v['prix']:.3f} €/L".replace(".", ",") for v in fiche["valeurs"])
    tags = f"#carburant #carburantradar{' #' + fuel if fuel else ''}"
    texte = f"{titre}\n{detail}\ncarburantradar.fr\n{tags}"
    return titre[:100], f"{texte} #Shorts", texte


def images_mobiles(dossier):
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True)
    from capture_vitrine import capturer
    capturer(dossier)
    return dossier


def executer(session, cle, jour, creneau, sortie, maintenant):
    """Un créneau déjà connu conserve son sujet, même si le premier envoi est incertain."""
    identifiant = f"{jour}:{creneau}"
    # La route éditoriale vérifie aussi la disponibilité du journal anti-doublon.
    lignes = list(pages(session, "editorial")) + list(pages(session, "publications"))
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
    textes = textes_publication(sujet)
    rendre(sujet, identifiant, sortie, captures)
    fiche = json.loads(sortie.with_suffix(".creation.json").read_text(encoding="utf-8"))
    reservation = {k: fiche[k] for k in ("id_video", "categorie", "villes", "carburant", "sujet", "sha256")}
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
