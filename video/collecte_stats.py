"""Collecte à J+7 des compteurs publics via les comptes autorisés, en lecture seule."""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from performance import AGE_MAX_H, AGE_MIN_H, instant


def compteurs(plateforme, video, token, appeler=requests.request, version_meta=None):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", video):
        raise ValueError("Identifiant vidéo invalide")
    options = dict(headers={"Authorization": f"Bearer {token}"}, timeout=25)

    def json_api(methode, url, **params):
        try:
            reponse = appeler(methode, url, **options, **params)
            reponse.raise_for_status()
            return reponse.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError(f"Lecture {plateforme} impossible pour {video}") from None

    if plateforme == "youtube":
        data = json_api("GET", "https://www.googleapis.com/youtube/v3/videos",
                        params={"part": "statistics", "id": video})
        item = next((v for v in data["items"] if v["id"] == video), {})
        stats = item.get("statistics", {})
        champs = {"vues": "viewCount", "likes": "likeCount", "commentaires": "commentCount"}
    elif plateforme == "tiktok":
        data = json_api("POST", "https://open.tiktokapis.com/v2/video/query/",
                        params={"fields": "id,view_count,like_count,comment_count,share_count"},
                        json={"filters": {"video_ids": [video]}})
        if data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"Lecture TikTok refusée pour {video}")
        stats = next((v for v in data["data"]["videos"] if v["id"] == video), {})
        champs = {"vues": "view_count", "likes": "like_count",
                  "commentaires": "comment_count", "partages": "share_count"}
    elif plateforme == "instagram":
        if not version_meta or not re.fullmatch(r"v\d+\.\d+", version_meta):
            raise ValueError("Version Graph Instagram obligatoire, ex. v25.0")
        data = json_api("GET", f"https://graph.instagram.com/{version_meta}/{video}/insights",
                        params={"metric": "views,likes,comments,shares"})
        stats = {m["name"]: m["values"][0]["value"] for m in data["data"] if m.get("values")}
        champs = {"vues": "views", "likes": "likes", "commentaires": "comments", "partages": "shares"}
    else:
        raise ValueError(f"Plateforme inconnue : {plateforme}")
    if champs["vues"] not in stats:
        raise RuntimeError(f"Compteur de vues indisponible sur {plateforme}/{video}")
    return {nom: int(stats[cle]) for nom, cle in champs.items() if isinstance(stats.get(cle), (str, int))}


def collecter(publications, mesures, jetons, maintenant, version_meta=None, lire=compteurs):
    connus = {(m["plateforme"], m["video_id"]) for m in mesures}
    erreurs = []
    for pub in publications:
        cle = pub["plateforme"], pub["video_id"]
        age = (maintenant - instant(pub["publie_le"])).total_seconds() / 3600
        if cle in connus or not AGE_MIN_H <= age < AGE_MAX_H:
            continue
        try:
            stats = lire(*cle, jetons[cle[0]], version_meta=version_meta)
        except (RuntimeError, ValueError, KeyError) as e:
            erreurs.append(f"{cle[0]}/{cle[1]} : {e}")
            continue
        mesures.append({**pub, **stats, "mesure_le": maintenant.isoformat()})
        connus.add(cle)
    return erreurs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("publications", type=Path, help="Registre JSON des vidéos et de leurs identifiants")
    parser.add_argument("mesures", type=Path, help="Sortie JSONL, un seul collecteur à la fois")
    args = parser.parse_args()
    mesures = []
    if args.mesures.exists():
        mesures = [json.loads(l) for l in args.mesures.read_text(encoding="utf-8").splitlines() if l.strip()]
    avant = len(mesures)
    jetons = {p: os.environ[f"CR_{p.upper()}_TOKEN"] for p in ("youtube", "instagram", "tiktok")
              if f"CR_{p.upper()}_TOKEN" in os.environ}
    erreurs = collecter(json.loads(args.publications.read_text(encoding="utf-8")), mesures, jetons,
                       datetime.now(timezone.utc), os.environ.get("CR_INSTAGRAM_VERSION"))
    if len(mesures) > avant:
        with args.mesures.open("a", encoding="utf-8") as f:
            for m in mesures[avant:]:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
    if erreurs:
        raise SystemExit("\n".join(erreurs))


if __name__ == "__main__":
    main()
