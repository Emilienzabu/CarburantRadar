"""Apprentissage hors ligne à partir d'expériences appariées, par plateforme."""
import argparse
import json
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from math import comb, exp, log1p
from pathlib import Path
from statistics import median

PLATEFORMES = {"youtube", "instagram", "tiktok"}
AGE_MIN_H, AGE_MAX_H = 168, 180
MIN_PAIRES = 30
MIN_GAIN = 0.15


def instant(valeur):
    dt = datetime.fromisoformat(valeur)
    if dt.utcoffset() is None:
        raise ValueError("Horodatage sans fuseau")
    return dt


def mesures_eligibles(lignes):
    vus = set()
    for ligne in lignes:
        plateforme, video = ligne["plateforme"], ligne["video_id"]
        age = (instant(ligne["mesure_le"]) - instant(ligne["publie_le"])).total_seconds() / 3600
        if plateforme not in PLATEFORMES or not AGE_MIN_H <= age < AGE_MAX_H:
            continue
        if ligne.get("organique") is not True:
            continue
        vues = ligne.get("vues")
        if type(vues) is not int or vues < 0:
            continue
        identite = plateforme, video
        if identite in vus:
            raise ValueError(f"Plusieurs mesures éligibles pour {plateforme}/{video}")
        vus.add(identite)
        yield ligne


def decrire(lignes):
    """Les résumés observationnels ne déclenchent aucun changement de rendu."""
    groupes = defaultdict(list)
    for ligne in mesures_eligibles(lignes):
        categorie = ligne.get("categorie")
        if categorie:
            groupes[ligne["plateforme"], categorie].append(ligne["vues"])
    return [dict(plateforme=p, categorie=c, videos=len(v), vues_medianes=median(v))
            for (p, c), v in sorted(groupes.items())]


def analyser(lignes):
    """Un groupe A/B ne contient qu'un résultat par variante et par plateforme."""
    paires = defaultdict(dict)
    for ligne in mesures_eligibles(lignes):
        essai = ligne.get("experience")
        if not essai:
            continue
        cle = (ligne["plateforme"], essai["facteur"], essai["contexte"], essai["temoin"],
               essai["variante"], essai["paire"])
        bras = essai["bras"]
        if bras not in ("temoin", "variante") or bras in paires[cle] or cle[3] == cle[4]:
            raise ValueError("Attribution expérimentale incohérente")
        paires[cle][bras] = ligne["vues"]

    groupes = defaultdict(list)
    for cle, valeurs in paires.items():
        if len(valeurs) == 2:
            groupes[cle[:-1]].append(log1p(valeurs["variante"]) - log1p(valeurs["temoin"]))
    seuil = 0.05 / max(1, len(groupes))
    resultats = []
    for (plateforme, facteur, contexte, temoin, variante), deltas in sorted(groupes.items()):
        n = len(deltas)
        signes = [d for d in deltas if d != 0]
        m = len(signes)
        victoires = sum(d > 0 for d in signes)
        p = min(1.0, 2 * sum(comb(m, i) for i in range(min(victoires, m-victoires)+1)) / 2**m)
        gain = exp(median(deltas)) - 1
        resultats.append(dict(plateforme=plateforme, facteur=facteur, contexte=contexte, temoin=temoin,
                              variante=variante, paires=n, gain=gain, p=p,
                              retenu=m >= MIN_PAIRES and p <= seuil and gain >= MIN_GAIN))
    return resultats


def experience_musique(contexte, temoin, variante, paire, ordre):
    """La paire et l'ordre sont attribués avant de connaître les résultats."""
    inversion = sha256(f"{contexte}/{paire}".encode()).digest()[0] % 2
    bras = "variante" if (ordre - 1) ^ inversion else "temoin"
    return dict(facteur="musique", contexte=contexte, temoin=temoin,
                variante=variante, paire=paire, bras=bras)


def choisir_musique(catalogue, defaut, resultats, identifiant, contexte):
    """Applique une préférence commune, en réservant 20 % des choix au témoin."""
    if int.from_bytes(sha256(identifiant.encode()).digest()[:8], "big") % 5 == 0:
        return defaut
    for piste in catalogue:
        preuves = {r["plateforme"] for r in resultats
                   if r["facteur"] == "musique" and r["contexte"] == contexte and r["temoin"] == defaut
                   and r["variante"] == piste and r["retenu"] and r["paires"] >= MIN_PAIRES
                   and r["gain"] >= MIN_GAIN and r["p"] <= .05}
        if preuves == PLATEFORMES:
            return piste
    return defaut


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesures", type=Path, help="Fichier JSONL des observations")
    args = parser.parse_args()
    lignes = [json.loads(ligne) for ligne in args.mesures.read_text(encoding="utf-8").splitlines() if ligne.strip()]
    print(json.dumps({"categories": decrire(lignes), "experiences": analyser(lignes)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
