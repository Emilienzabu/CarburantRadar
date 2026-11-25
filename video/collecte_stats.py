"""Collecte des performances jusqu'à J+30, en lecture seule."""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import requests

from metadonnees_video import extraire_hashtags
from performance import PLATEFORMES, PLATEFORMES_ACTIVES, horizon_mesure


def compteurs(plateforme, video, token, appeler=requests.request, version_meta=None):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", video):
        raise ValueError("Identifiant vidéo invalide")
    options = dict(headers={"Authorization": f"Bearer {token}"}, timeout=25)
    textes = ()

    def json_api(methode, url, **params):
        try:
            reponse = appeler(methode, url, **options, **params)
            reponse.raise_for_status()
            return reponse.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError(f"Lecture {plateforme} impossible pour {video}") from None

    if plateforme == "youtube":
        data = json_api("GET", "https://www.googleapis.com/youtube/v3/videos",
                        params={"part": "statistics,snippet", "id": video})
        item = next((v for v in data["items"] if v["id"] == video), {})
        stats = item.get("statistics", {})
        snippet = item.get("snippet")
        if isinstance(snippet, dict):
            textes = (snippet.get("title"), snippet.get("description"))
        champs = {"vues": "viewCount", "likes": "likeCount", "commentaires": "commentCount"}
    elif plateforme == "tiktok":
        data = json_api("POST", "https://open.tiktokapis.com/v2/video/query/",
                        params={"fields": "id,view_count,like_count,comment_count,share_count,video_description"},
                        json={"filters": {"video_ids": [video]}})
        if data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"Lecture TikTok refusée pour {video}")
        stats = next((v for v in data["data"]["videos"] if v["id"] == video), {})
        textes = (stats.get("video_description"),)
        champs = {"vues": "view_count", "likes": "like_count",
                  "commentaires": "comment_count", "partages": "share_count"}
    elif plateforme == "instagram":
        if not version_meta or not re.fullmatch(r"v\d+\.\d+", version_meta):
            raise ValueError("Version Graph Instagram obligatoire, ex. v25.0")
        media_url = f"https://graph.instagram.com/{version_meta}/{video}"
        data = json_api("GET", f"{media_url}/insights",
                        params={"metric": "views,likes,comments,shares"})
        stats = {m["name"]: m["values"][0]["value"] for m in data["data"] if m.get("values")}
        champs = {"vues": "views", "likes": "likes", "commentaires": "comments", "partages": "shares"}
    else:
        raise ValueError(f"Plateforme inconnue : {plateforme}")
    if champs["vues"] not in stats:
        raise RuntimeError(f"Compteur de vues indisponible sur {plateforme}/{video}")
    normalises = {nom: int(stats[cle]) for nom, cle in champs.items()
                  if isinstance(stats.get(cle), (str, int))}
    if plateforme == "instagram":
        try:
            media = json_api("GET", media_url, params={"fields": "caption"})
        except RuntimeError:
            media = None
        if isinstance(media, dict):
            textes = (media.get("caption"),)

    textes = [texte for texte in textes if isinstance(texte, str)]
    if textes:
        normalises.update(hashtags=extraire_hashtags(*textes), hashtags_source="plateforme")
    return normalises


def collecter(publications, mesures, jetons, maintenant, version_meta=None, lire=compteurs, *,
              plateformes=PLATEFORMES_ACTIVES):
    connus = {(m["plateforme"], m["video_id"], horizon_mesure(m["publie_le"], m["mesure_le"]))
              for m in mesures if m["plateforme"] in plateformes}
    erreurs = []
    mesure_le = maintenant.isoformat()
    for pub in publications:
        plateforme, video = pub["plateforme"], pub["video_id"]
        if plateforme not in plateformes:
            continue
        horizon = horizon_mesure(pub["publie_le"], mesure_le)
        cle = plateforme, video, horizon
        if horizon is None or cle in connus:
            continue
        try:
            stats = lire(plateforme, video, jetons[plateforme], version_meta=version_meta)
        except (RuntimeError, ValueError, KeyError) as e:
            erreurs.append(f"{plateforme}/{video} (J+{horizon}) : {e}")
            continue
        mesures.append({**pub, **stats, "mesure_le": mesure_le, "horizon_jours": horizon})
        connus.add(cle)
    return erreurs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("publications", type=Path, help="Registre JSON des vidéos et de leurs identifiants")
    parser.add_argument("mesures", type=Path, help="Sortie JSONL, un seul collecteur à la fois")
    parser.add_argument("--plateformes", nargs="+", choices=sorted(PLATEFORMES),
                        default=PLATEFORMES_ACTIVES, help="Par défaut : YouTube et Instagram")
    args = parser.parse_args()
    mesures = []
    if args.mesures.exists():
        mesures = [json.loads(l) for l in args.mesures.read_text(encoding="utf-8").splitlines() if l.strip()]
    avant = len(mesures)
    jetons = {p: os.environ[f"CR_{p.upper()}_TOKEN"] for p in args.plateformes
              if f"CR_{p.upper()}_TOKEN" in os.environ}
    erreurs = collecter(json.loads(args.publications.read_text(encoding="utf-8")), mesures, jetons,
                       datetime.now(timezone.utc), os.environ.get("CR_INSTAGRAM_VERSION"),
                       plateformes=args.plateformes)
    if len(mesures) > avant:
        # Conserver un JSONL lisible si le processus s'interrompt pendant l'écriture.
        with TemporaryDirectory(dir=args.mesures.parent) as dossier:
            temporaire = Path(dossier) / args.mesures.name
            with temporaire.open("w", encoding="utf-8") as f:
                for m in mesures:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
            temporaire.replace(args.mesures)
    if erreurs:
        raise SystemExit("\n".join(erreurs))


if __name__ == "__main__":
    main()
