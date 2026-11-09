#!/usr/bin/env python3
"""Vidéo du jour CarburantRadar : prix réels -> vidéo 9:16 avec voix d'homme et musique -> YouTube + Instagram.

Deux publications par jour (créneau "matin" et "soir"), trois formats qui alternent :
  ville       prix d'une ville pour un carburant (top 3, économie sur un plein)
  classement  les villes les moins chères parmi les plus grandes
  astuce      conseil général (sans chiffres)

Exemples :
  python video/generate_video.py --demo --format classement   # essai sans réseau pour les prix
  python video/generate_video.py                              # contenu prévu pour ce créneau, sans publier
  python video/generate_video.py --publier                    # idem + envoi au Worker (clé dans VIDEO_API_KEY)
  python video/generate_video.py --format ville --ville marseille --carburant gazole
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unicodedata
from zoneinfo import ZoneInfo

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio  # noqa: E402
import controle_publication  # noqa: E402
import donnees  # noqa: E402
import garde  # noqa: E402
from garde import appliquer_garde_astuce, garde_astuce_active  # noqa: E402,F401
import rendu  # noqa: E402
import vitrine  # noqa: E402

WORKER_URL = "https://video-automation.emilienzabukovec09.workers.dev/api/upload"
POLICES = ["Poppins-Bold.ttf", "Poppins-SemiBold.ttf", "Poppins-Medium.ttf"]
POLICES_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/"


def log(msg):
    print(msg, flush=True)


def normaliser_ville(s):
    """'Aix en Provence' / 'Saint-Étienne' -> 'aix-en-provence' / 'saint-etienne'."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


ALIAS_CARBURANT = {"sp95": "e10", "sp95-e10": "e10", "sans-plomb": "e10", "super": "e10", "diesel": "gazole",
                   "gasoil": "gazole", "gpl": "gplc", "ethanol": "e85"}


def normaliser_carburant(s):
    c = normaliser_ville(s)
    c = ALIAS_CARBURANT.get(c, c)
    if c not in donnees.CARBURANTS:
        raise argparse.ArgumentTypeError(f"carburant inconnu : {s!r}. Possibles : {', '.join(donnees.CARBURANTS)}")
    return c


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


def construire(plan, k, args):
    """Récupère les données du jour et renvoie l'info à mettre en vidéo."""
    if plan["format"] == "vitrine":   # démonstration à partir de captures : aucune donnée du flux officiel
        return vitrine.info_vitrine()
    if args.demo:
        return donnees.info_demo(plan["format"])
    if plan["format"] == "astuce":
        return donnees.construire_astuce(plan["astuce"])
    if plan["format"] == "classement":
        info = donnees.recuperer_classement(plan["carburant"], log)
        if info:
            log(f"Classement {plan['carburant']} : {info['n_villes']} villes, 1er {info['villes'][0]['nom']}")
            return info
        log("Classement impossible (pas assez de villes avec des prix récents) : repli sur une ville.")
        plan = donnees.plan_du_jour(k, "ville", None, plan["carburant"])

    carburants = list(dict.fromkeys([plan["carburant"], "gazole"]))  # carburant rare introuvable -> gazole
    for fuel in carburants:
        for ville in plan["villes"]:
            try:
                stations = donnees.recuperer_stations(ville, fuel)
            except Exception as e:
                log(f"{ville['nom']} : récupération impossible ({e})")
                continue
            info = donnees.construire_ville(ville, fuel, stations)
            if info:
                log(f"{ville['nom']} / {fuel} : {info['n_stations']} stations, "
                    f"min {info['prix_min']:.3f} € moy {info['prix_moy']:.3f} € max {info['prix_max']:.3f} €")
                return info
            log(f"{ville['nom']} / {fuel} : pas assez de stations avec un prix récent.")
    raise SystemExit("Aucune ville exploitable : rien n'est publié.")


def publier(chemin, info, cle):
    """Envoie la vidéo au Worker. Ne réessaie JAMAIS (un envoi dont l'issue est inconnue a pu être publié).

    Renvoie un dict : {"etat": "complet" | "partiel" | "echec" | "incertain", ...}
      complet   YouTube ET Instagram confirment (champ `success` de la réponse du Worker)
      partiel   une seule plateforme confirme : à signaler, JAMAIS à relancer tel quel (doublon sur l'autre)
      echec     le Worker répond clairement que rien n'a été publié
      incertain délai dépassé, erreur réseau ou réponse illisible : la vidéo a peut-être été publiée
    """
    titre, description, legende = donnees.textes_publication(info)
    log(f"Envoi au Worker : « {titre} »")
    try:
        with open(chemin, "rb") as f:
            r = requests.post(
                WORKER_URL,
                headers={"Authorization": f"Bearer {cle}"},
                data={"profile": "carburant", "title": titre, "description": description, "caption": legende},
                files={"video": ("video-du-jour.mp4", f, "video/mp4")},
                timeout=900,
            )
    except requests.exceptions.RequestException as e:
        return {"etat": "incertain", "detail": f"{type(e).__name__} pendant l'envoi"}
    try:
        res = r.json()
        if not isinstance(res, dict):
            raise ValueError("réponse non objet")
    except Exception:
        log(f"Réponse inattendue ({r.status_code}) : {str(r.text)[:500]}")
        return {"etat": "incertain", "detail": f"réponse illisible (HTTP {r.status_code})"}
    yt = res.get("youtube", {}) or {}
    ig = res.get("instagram", {}) or {}
    log("YouTube : " + (yt.get("url") or json.dumps(yt, ensure_ascii=False)[:400]))
    log("Instagram : " + ("publié" if ig.get("success") else json.dumps(ig, ensure_ascii=False)[:400]))
    if not res.get("youtube") and res.get("error"):
        log(res["error"])
    yt_ok, ig_ok = bool(yt.get("success")), bool(ig.get("success"))
    etat = "complet" if (yt_ok and ig_ok) else "partiel" if (yt_ok or ig_ok) else "echec"
    return {"etat": etat, "youtube": yt_ok, "instagram": ig_ok, "youtube_url": yt.get("url")}


def ecrire_resume(slot_id, info, resultat):
    """Résumé lisible dans l'onglet de l'exécution GitHub (variable GITHUB_STEP_SUMMARY, fournie par Actions)."""
    chemin = os.environ.get("GITHUB_STEP_SUMMARY")
    if not chemin:
        return
    lignes = [f"### Publication {slot_id} : **{resultat['etat']}**",
              f"- format : {info.get('format')}", f"- YouTube : {resultat.get('youtube_url') or resultat.get('youtube')}",
              f"- Instagram : {resultat.get('instagram')}"]
    if resultat["etat"] in ("partiel", "incertain", "echec"):
        lignes.append("- **Ne relance pas ce créneau sans avoir vérifié sur YouTube et Instagram : "
                      "une nouvelle publication créerait un doublon.**")
    try:
        with open(chemin, "a", encoding="utf-8") as f:
            f.write("\n".join(lignes) + "\n")
    except OSError:
        pass


def textes_manifeste(info):
    """Titre/description/légende : le format vitrine (jamais publié) a ses propres métadonnées."""
    return vitrine.textes_publication(info) if info.get("format") == "vitrine" else donnees.textes_publication(info)


def controler_video(chemin, rend, info, slot_id):
    """Écrit le manifeste de rendu (à partir de la commande ffmpeg RÉELLEMENT exécutée) puis lance le contrôle technique."""
    manifeste = os.path.splitext(chemin)[0] + ".manifeste.json"
    try:
        m = controle_publication.construire_manifeste(
            chemin, getattr(rend, "derniere_commande", None), slot_id=slot_id, format_video=info.get("format"),
            titre=textes_manifeste(info)[0])
        controle_publication.ecrire_manifeste(manifeste, m)
        return controle_publication.valider_avant_publication(chemin, manifeste, exiger_slot=True)
    except Exception as e:  # noqa: BLE001 - fail closed
        return controle_publication.Resultat(False, (f"controle:exception_{type(e).__name__}",))


def construire_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="données factices (aucun accès réseau pour les prix)")
    p.add_argument("--format", choices=["ville", "classement", "astuce", "vitrine"],
                   help="vide = selon le planning. « vitrine » = démonstration de l'app (captures), jamais publiée")
    p.add_argument("--creneau", choices=["auto", "matin", "soir"], default="auto")
    p.add_argument("--ville", type=normaliser_ville)
    p.add_argument("--carburant", type=normaliser_carburant)
    p.add_argument("--publier", action="store_true")
    p.add_argument("--sortie", default=os.path.join(HERE, "sortie", "video-du-jour.mp4"))
    p.add_argument("--voix", default=audio.VOIX_DEFAUT)
    p.add_argument("--voix-locale", action="store_true",
                   help="voix de TEST hors ligne (espeak-ng) : interdite avec --publier, qualité non représentative")
    p.add_argument("--png", help="temps en secondes séparés par des virgules : enregistre des images de contrôle")
    return p


def main():
    args = construire_parser().parse_args()
    if args.demo and args.publier:
        raise SystemExit("--demo (données factices) ne peut pas être publié : rien n'est publié.")
    if args.publier and args.format == "vitrine":
        raise SystemExit("Format vitrine : démonstration à partir de captures (valeurs non actuelles), jamais publiée "
                         "automatiquement : rien n'est publié.")
    if args.publier and args.voix_locale:
        raise SystemExit("--voix-locale (voix de test) ne peut pas être publiée : rien n'est publié.")
    appliquer_garde_astuce(args, log)

    maintenant = dt.datetime.now(ZoneInfo("Europe/Paris"))
    creneau = args.creneau if args.creneau != "auto" else ("matin" if maintenant.hour < 13 else "soir")
    k = maintenant.date().toordinal() * 2 + (1 if creneau == "soir" else 0)

    polices = os.path.join(HERE, "fonts")
    assurer_polices(polices)
    icone = os.path.join(HERE, "..", "icons", "icon-512.png")
    if not os.path.isfile(icone):
        icone = os.path.join(HERE, "icon-512.png")

    if args.format == "vitrine":
        plan = {"format": "vitrine"}
    else:
        plan = donnees.plan_du_jour(k, args.format, args.ville, args.carburant)
    if plan["format"] == "astuce":   # rotation sans conseil identique deux fois de suite
        plan = garde.plan_astuce(k, donnees.ASTUCES)
    log(f"Créneau {creneau}, publication n°{k}, format {plan['format']}")
    info = construire(plan, k, args)
    if args.publier and garde_astuce_active() and info.get("format") != "astuce":
        raise SystemExit(f"Garde astuce : format {info.get('format')!r} refusé à la publication (rien n'est publié).")

    est_vitrine = info.get("format") == "vitrine"
    scenes_def = vitrine.scenes_texte(info) if est_vitrine else donnees.scenes_texte(info)
    with tempfile.TemporaryDirectory() as tmp:
        if est_vitrine:
            clips, mots = audio.synth_clips_mots(scenes_def, tmp, args.voix, log, moteur="espeak" if args.voix_locale else "edge")
            scenes = audio.planifier(scenes_def, clips, vitrine.DEBUT_SCENE, vitrine.FIN_SCENE)
            vitrine.attacher_mots(scenes, scenes_def, mots)
        else:
            clips = audio.synth_clips(scenes_def, tmp, args.voix, log)
            if args.publier and any(c is None for c in clips):
                raise SystemExit("Voix indisponible : rien n'est publié (une vidéo sans voix ne serait pas au niveau). "
                                 "Relance le workflow un peu plus tard.")
            scenes = audio.planifier(scenes_def, clips)
        total = scenes[-1]["start"] + scenes[-1]["dur"]
        detail = ", ".join("%s %.1fs" % (s["id"], s["dur"]) for s in scenes)
        log(f"Durée : {total:.1f} s ({detail})")

        wav = os.path.join(tmp, "audio.wav")
        audio.ecrire_wav(wav, audio.mixer(scenes, clips, seed=vitrine.SEED_MUSIQUE if est_vitrine else k))

        if est_vitrine:
            try:
                rend = vitrine.RendererVitrine(info, scenes, polices, icone)
            except (FileNotFoundError, ValueError) as e:
                raise SystemExit(f"Format vitrine impossible : {e}")
        else:
            rend = rendu.Renderer(info, scenes, polices, icone)
        os.makedirs(os.path.dirname(args.sortie), exist_ok=True)
        if args.png:
            for t in args.png.split(","):
                out = os.path.join(os.path.dirname(args.sortie), f"image_{float(t):05.1f}.png")
                rend.save_png(float(t), out)
                log(f"Image : {out}")
            return
        rend.encode(wav, args.sortie, log)

    log(f"Vidéo prête : {args.sortie} ({os.path.getsize(args.sortie) / 1e6:.1f} Mo)")

    slot_id = f"{maintenant.date().isoformat()}:{creneau}"
    controle = controler_video(args.sortie, rend, info, slot_id)
    if not controle.accepte:
        log("::error::Contrôle avant publication REFUSÉ : " + ", ".join(controle.erreurs))
        raise SystemExit("Vidéo non conforme : rien n'est publié (le fichier reste téléchargeable pour examen).")
    log("Contrôle avant publication : accepté (1080x1920, H.264/AAC 48 kHz, intégrité, loudness, empreinte).")

    if args.publier:
        cle = os.environ.get("VIDEO_API_KEY")
        if not cle:
            raise SystemExit("VIDEO_API_KEY manquante : impossible de publier.")
        resultat = publier(args.sortie, info, cle)
        ecrire_resume(slot_id, info, resultat)
        if resultat["etat"] == "complet":
            return
        if resultat["etat"] == "partiel":
            log(f"::warning::Publication PARTIELLE (YouTube={resultat['youtube']}, Instagram={resultat['instagram']}). "
                "Ne relance pas ce créneau : l'autre plateforme a déjà la vidéo, un nouvel envoi créerait un doublon.")
            return
        if resultat["etat"] == "incertain":
            raise SystemExit(f"Envoi INCERTAIN ({resultat.get('detail')}) : la vidéo a peut-être été publiée. "
                             "Vérifie YouTube et Instagram AVANT de relancer ; aucun nouvel envoi automatique.")
        raise SystemExit("La publication a échoué sur les deux plateformes (vérifie quand même avant de relancer).")


if __name__ == "__main__":
    main()
