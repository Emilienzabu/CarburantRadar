"""Fiches de création et références des publications confirmées."""
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from controle_publication import sha256_fichier, sonder


def extraire_hashtags(*textes):
    tags = {}
    for texte in textes:
        for tag in re.findall(r"(?<![\w#])#(\w+)", unicodedata.normalize("NFC", texte or "")):
            tags.setdefault("#" + tag.casefold(), None)
    return list(tags)


def mesures_rendu(chemin):
    return {"duree_s": float(sonder(chemin)["format"]["duration"]),
            "sha256": sha256_fichier(chemin)}


def ecrire_fiche(chemin, **fiche):
    chemin = Path(chemin)
    chemin.with_suffix(".creation.json").write_text(
        json.dumps({**fiche, **mesures_rendu(chemin)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def identifiant_publication(plateforme, resultat):
    if plateforme == "instagram":
        media_id = resultat.get("mediaId")
        if type(media_id) in (str, int) and re.fullmatch(r"[0-9]+", str(media_id)):
            return str(media_id)
        return None

    video_id = resultat.get("videoId")
    if not video_id:
        lien = resultat.get("url")
        if not isinstance(lien, str):
            return None
        try:
            url = urlparse(lien)
        except ValueError:
            return None
        if url.hostname == "youtu.be":
            video_id = url.path.strip("/")
        elif url.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
            if url.path.startswith("/shorts/"):
                video_id = url.path.removeprefix("/shorts/").strip("/")
            elif url.path == "/watch":
                video_id = parse_qs(url.query).get("v", [""])[0]
    return video_id if isinstance(video_id, str) and re.fullmatch(r"[\w-]{11}", video_id, re.ASCII) else None


def references_confirmees(titre, description, legende, youtube, instagram):
    resultats = {}
    for plateforme, retour, textes in (
        ("youtube", youtube, (titre, description)),
        ("instagram", instagram, (legende,)),
    ):
        if retour.get("success"):
            resultats[plateforme] = {
                "video_id": identifiant_publication(plateforme, retour),
                "hashtags": extraire_hashtags(*textes),
                "hashtags_source": "texte_envoye",
            }
    return resultats


def ecrire_recu(chemin, fiche, references, confirme_le):
    lignes = [
        {**fiche, **reference, "plateforme": plateforme, "publie_le": confirme_le.isoformat(),
         "publication_source": "confirmation_worker", "organique": True}
        for plateforme, reference in references.items()
        if reference["video_id"]
    ]
    if lignes:
        Path(chemin).with_suffix(".publications.json").write_text(
            json.dumps(lignes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
    return [p for p, r in references.items() if not r["video_id"]]
