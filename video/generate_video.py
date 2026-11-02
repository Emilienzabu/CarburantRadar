#!/usr/bin/env python3
"""Vidéo du jour CarburantRadar : prix réels -> vidéo 9:16 avec voix, musique -> publication YouTube + Instagram.

Exemples :
  python video/generate_video.py --demo                      # essai sans réseau (données factices, voix si dispo)
  python video/generate_video.py                             # ville/carburant du jour, génère video/sortie/video-du-jour.mp4
  python video/generate_video.py --ville marseille --carburant gazole
  python video/generate_video.py --publier                   # envoie au Worker (clé dans VIDEO_API_KEY)
"""
import argparse
import datetime as dt
import json
import os
import sys
import tempfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio  # noqa: E402
import donnees  # noqa: E402
import rendu  # noqa: E402

WORKER_URL = "https://video-automation.emilienzabukovec09.workers.dev/api/upload"
POLICES = ["Poppins-Bold.ttf", "Poppins-SemiBold.ttf", "Poppins-Medium.ttf"]
POLICES_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/"


def log(msg):
    print(msg, flush=True)


def assurer_polices(dossier):
    os.makedirs(dossier, exist_ok=True)
    for nom in POLICES:
        chemin = os.path.join(dossier, nom)
        if os.path.isfile(chemin):
            continue
        try:
            r = requests.get(POLICES_URL + nom, timeout=60)
            r.raise_for_status()
            with open(chemin, "wb") as f:
                f.write(r.content)
        except Exception as e:
            log(f"Police {nom} non téléchargée ({e}), police de secours utilisée.")


def trouver_info(args):
    if args.demo:
        return donnees.info_demo()
    for ville, carburant in donnees.choisir(dt.date.today(), args.ville, args.carburant)[:8]:
        try:
            stations = donnees.recuperer_stations(ville, carburant)
        except Exception as e:
            log(f"{ville['nom']} : récupération impossible ({e})")
            continue
        info = donnees.construire_info(ville, carburant, stations)
        if info:
            log(f"{ville['nom']} / {carburant} : {info['n_stations']} stations, "
                f"min {info['prix_min']:.3f} € moy {info['prix_moy']:.3f} € max {info['prix_max']:.3f} €")
            return info
        log(f"{ville['nom']} : pas assez de stations avec un prix récent, ville suivante.")
    raise SystemExit("Aucune ville exploitable aujourd'hui : rien n'est publié.")


def publier(chemin, info, cle):
    titre, description, legende = donnees.textes_publication(info)
    log(f"Envoi au Worker : « {titre} »")
    with open(chemin, "rb") as f:
        r = requests.post(
            WORKER_URL,
            headers={"Authorization": f"Bearer {cle}"},
            data={"profile": "carburant", "title": titre, "description": description, "caption": legende},
            files={"video": ("video-du-jour.mp4", f, "video/mp4")},
            timeout=900,
        )
    try:
        res = r.json()
    except Exception:
        log(f"Réponse inattendue ({r.status_code}) : {r.text[:500]}")
        return False
    yt = res.get("youtube", {}) or {}
    ig = res.get("instagram", {}) or {}
    log("YouTube : " + (yt.get("url") or json.dumps(yt, ensure_ascii=False)[:400]))
    log("Instagram : " + ("publié" if ig.get("success") else json.dumps(ig, ensure_ascii=False)[:400]))
    if not res.get("youtube") and res.get("error"):
        log(res["error"])
    return bool(yt.get("success") or ig.get("success"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="données factices (aucun accès réseau pour les prix)")
    p.add_argument("--ville")
    p.add_argument("--carburant", choices=list(donnees.CARBURANTS))
    p.add_argument("--publier", action="store_true")
    p.add_argument("--sortie", default=os.path.join(HERE, "sortie", "video-du-jour.mp4"))
    p.add_argument("--voix", default=audio.VOIX_DEFAUT)
    p.add_argument("--png", help="temps en secondes séparés par des virgules : enregistre des images de contrôle")
    args = p.parse_args()

    polices = os.path.join(HERE, "fonts")
    assurer_polices(polices)
    icone = os.path.join(HERE, "..", "icons", "icon-512.png")
    if not os.path.isfile(icone):
        icone = os.path.join(HERE, "icon-512.png")

    info = trouver_info(args)
    jour = dt.date.today().toordinal()

    scenes_def = donnees.scenes_texte(info)
    with tempfile.TemporaryDirectory() as tmp:
        clips = audio.synth_clips(scenes_def, tmp, args.voix, log)
        scenes = audio.planifier(scenes_def, clips)
        total = scenes[-1]["start"] + scenes[-1]["dur"]
        detail = ", ".join("%s %.1fs" % (s["id"], s["dur"]) for s in scenes)
        log(f"Durée : {total:.1f} s ({detail})")

        wav = os.path.join(tmp, "audio.wav")
        audio.ecrire_wav(wav, audio.mixer(scenes, clips, seed=jour))

        rend = rendu.Renderer(info, scenes, polices, icone)
        if args.png:
            os.makedirs(os.path.dirname(args.sortie), exist_ok=True)
            for t in args.png.split(","):
                out = os.path.join(os.path.dirname(args.sortie), f"image_{float(t):05.1f}.png")
                rend.save_png(float(t), out)
                log(f"Image : {out}")
            return

        os.makedirs(os.path.dirname(args.sortie), exist_ok=True)
        rend.encode(wav, args.sortie, log)

    taille = os.path.getsize(args.sortie) / 1e6
    log(f"Vidéo prête : {args.sortie} ({taille:.1f} Mo)")

    if args.publier:
        cle = os.environ.get("VIDEO_API_KEY")
        if not cle:
            raise SystemExit("VIDEO_API_KEY manquante : impossible de publier.")
        if not publier(args.sortie, info, cle):
            raise SystemExit("La publication a échoué sur les deux plateformes.")


if __name__ == "__main__":
    main()
