"""Apprentissage hors ligne à partir d'expériences appariées, par plateforme."""
import argparse
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from math import comb, exp, isfinite, log1p
from pathlib import Path
from statistics import median

PLATEFORMES = {"youtube", "instagram", "tiktok"}
PLATEFORMES_ACTIVES = frozenset({"youtube", "instagram"})
AGE_MIN_H, AGE_MAX_H = 168, 180
HORIZONS = {j: (j * 24, j * 24 + 12) for j in (1, 3, 7, 14, 30)}
MIN_PAIRES = 30
MIN_GAIN = 0.15


def instant(valeur):
    dt = valeur if isinstance(valeur, datetime) else datetime.fromisoformat(valeur)
    if dt.utcoffset() is None:
        raise ValueError("Horodatage sans fuseau")
    return dt


def horizon_mesure(publie_le, mesure_le):
    debut = instant(publie_le).astimezone(timezone.utc)
    fin = instant(mesure_le).astimezone(timezone.utc)
    age = (fin - debut).total_seconds() / 3600
    return next((jour for jour, (debut, fin) in HORIZONS.items() if debut <= age < fin), None)


def mesures_eligibles(lignes):
    vus = set()
    for ligne in lignes:
        plateforme, video = ligne["plateforme"], ligne["video_id"]
        if plateforme not in PLATEFORMES:
            continue
        horizon = horizon_mesure(ligne["publie_le"], ligne["mesure_le"])
        if "horizon_jours" in ligne and (
            type(ligne["horizon_jours"]) is not int or ligne["horizon_jours"] != horizon
        ):
            raise ValueError(f"Horizon incompatible avec l'âge pour {plateforme}/{video}")
        if horizon is None:
            continue
        if ligne.get("organique") is not True:
            continue
        vues = ligne.get("vues")
        if type(vues) is not int or vues < 0:
            continue
        identite = plateforme, video, horizon
        if identite in vus:
            raise ValueError(f"Plusieurs mesures éligibles pour {plateforme}/{video} à J+{horizon}")
        vus.add(identite)
        yield dict(ligne, horizon_jours=horizon)


def _descriptif(lignes, variable, valeurs):
    groupes = defaultdict(list)
    for ligne in mesures_eligibles(lignes):
        for valeur in valeurs(ligne):
            groupes[ligne["plateforme"], ligne["horizon_jours"], valeur].append(ligne["vues"])
    return [dict(plateforme=p, horizon_jours=h, videos=len(v), vues_medianes=median(v),
                 **{variable: c}) for (p, h, c), v in sorted(groupes.items())]


def decrire(lignes):
    """Les résumés observationnels ne déclenchent aucun changement de rendu."""
    return _descriptif(lignes, "categorie", lambda l: (l["categorie"],) if l.get("categorie") else ())


def _hashtags(ligne):
    hashtags = ligne.get("hashtags")
    if not isinstance(hashtags, (list, tuple)):
        return ()
    tags = set()
    for valeur in hashtags:
        if isinstance(valeur, str):
            tag = unicodedata.normalize("NFC", valeur.strip().removeprefix("#").casefold())
            if re.fullmatch(r"\w+", tag):
                tags.add(f"#{tag}")
    return tags


def decrire_hashtags(lignes):
    return _descriptif(lignes, "hashtag", _hashtags)


def _duree(ligne):
    secondes = ligne.get("duree_s")
    if type(secondes) not in (int, float) or not isfinite(secondes) or secondes <= 0:
        return ()
    if secondes < 15:
        return ("moins de 15 s",)
    if secondes < 30:
        return ("15 à moins de 30 s",)
    if secondes < 60:
        return ("30 à moins de 60 s",)
    return ("60 s et plus",)


def decrire_durees(lignes):
    return _descriptif(lignes, "tranche_duree", _duree)


def decrire_musiques(lignes):
    return _descriptif(lignes, "musique", lambda l: (str(l["musique"]),)
                       if l.get("musique") is not None else ())


def decrire_carburants(lignes):
    return _descriptif(lignes, "carburant", lambda l: (l["carburant"],) if l.get("carburant") else ())


def analyser(lignes):
    """Un groupe A/B est propre à une plateforme et à un horizon."""
    paires = defaultdict(dict)
    for ligne in mesures_eligibles(lignes):
        essai = ligne.get("experience")
        if not essai:
            continue
        bras = essai["bras"]
        if essai["facteur"] == "hashtag":
            # Une légende modifiée peut invalider le bras initial.
            tag = essai["variante"]
            if not isinstance(ligne.get("hashtags"), list) or (tag in _hashtags(ligne)) != (bras == "variante"):
                continue
        cle = (ligne["plateforme"], ligne["horizon_jours"], essai["facteur"], essai["contexte"],
               essai["temoin"], essai["variante"], essai["paire"])
        if bras not in ("temoin", "variante") or bras in paires[cle] or cle[4] == cle[5]:
            raise ValueError("Attribution expérimentale incohérente")
        paires[cle][bras] = ligne["vues"]

    groupes = defaultdict(list)
    for cle, valeurs in paires.items():
        if len(valeurs) == 2:
            groupes[cle[:-1]].append(log1p(valeurs["variante"]) - log1p(valeurs["temoin"]))
    seuil = 0.05 / max(1, sum(cle[1] == 30 for cle in groupes))
    resultats = []
    for (plateforme, horizon, facteur, contexte, temoin, variante), deltas in sorted(groupes.items()):
        n = len(deltas)
        signes = [d for d in deltas if d != 0]
        m = len(signes)
        victoires = sum(d > 0 for d in signes)
        p = min(1.0, 2 * sum(comb(m, i) for i in range(min(victoires, m-victoires)+1)) / 2**m)
        gain = exp(median(deltas)) - 1
        resultats.append(dict(plateforme=plateforme, horizon_jours=horizon, facteur=facteur,
                              contexte=contexte, temoin=temoin,
                              variante=variante, paires=n, gain=gain, p=p,
                              retenu=horizon == 30 and m >= MIN_PAIRES and p <= seuil and gain >= MIN_GAIN))
    return resultats


def experience_appariee(facteur, contexte, temoin, variante, paire, ordre):
    """La paire et l'ordre sont attribués avant de connaître les résultats."""
    inversion = sha256(f"{contexte}/{paire}".encode()).digest()[0] % 2
    bras = "variante" if (ordre - 1) ^ inversion else "temoin"
    return dict(facteur=facteur, contexte=contexte, temoin=temoin,
                variante=variante, paire=paire, bras=bras)


def experience_musique(contexte, temoin, variante, paire, ordre):
    return experience_appariee("musique", contexte, temoin, variante, paire, ordre)


def plateformes_confirmees(facteur, contexte, temoin, variante, resultats):
    return {r["plateforme"] for r in resultats
            if r.get("horizon_jours") == 30 and r["plateforme"] in PLATEFORMES
            and r["facteur"] == facteur and r["contexte"] == contexte and r["temoin"] == temoin
            and r["variante"] == variante and r["retenu"] and r["paires"] >= MIN_PAIRES
            and r["gain"] >= MIN_GAIN and r["p"] <= .05}


def musique_confirmee(catalogue, defaut, resultats, contexte, plateformes=PLATEFORMES_ACTIVES):
    """Cherche une variante confirmée à J+30 sur toutes les plateformes actives."""
    plateformes = frozenset(plateformes)
    if not plateformes or not plateformes <= PLATEFORMES:
        raise ValueError("Plateformes d'apprentissage invalides")
    for piste in catalogue:
        if plateformes <= plateformes_confirmees("musique", contexte, defaut, piste, resultats):
            return piste
    return None


def garder_temoin(identifiant):
    return int.from_bytes(sha256(identifiant.encode()).digest()[:8], "big") % 5 == 0


def choisir_musique(catalogue, defaut, resultats, identifiant, contexte, *,
                    plateformes=PLATEFORMES_ACTIVES):
    """Applique une préférence commune, en réservant 20 % des choix au témoin."""
    piste = musique_confirmee(catalogue, defaut, resultats, contexte, plateformes)
    if piste is not None and not garder_temoin(identifiant):
        return piste
    return defaut


def rapport(lignes):
    return {"indicateurs": {"categories": decrire(lignes), "hashtags": decrire_hashtags(lignes),
                            "durees": decrire_durees(lignes), "musiques": decrire_musiques(lignes),
                            "carburants": decrire_carburants(lignes)}, "experiences": analyser(lignes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesures", type=Path, help="Fichier JSONL des observations")
    args = parser.parse_args()
    lignes = [json.loads(ligne) for ligne in args.mesures.read_text(encoding="utf-8").splitlines() if ligne.strip()]
    synthese = rapport(lignes)
    print(json.dumps({**synthese["indicateurs"], "experiences": synthese["experiences"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
