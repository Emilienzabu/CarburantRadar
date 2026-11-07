#!/usr/bin/env python3
"""Contrôle technique d'une vidéo AVANT publication. Local, sans réseau, ne publie jamais.

Origine : consolidation et adaptation au code réel des portes V97 à V100 du paquet d'audit ChatGPT
(video_delivery_gate, video_integrity_gate, render_provenance_gate, prepublish_gate), plus des contrôles qui
manquaient et qui viennent des spécifications officielles des Reels Instagram (AAC 48 kHz maximum, pas d'edit list,
moov au début du fichier) et de mesures réelles du rendu (loudness).

Philosophie : « fail closed ». Toute erreur, exception ou résultat incohérent refuse la publication.
Limite assumée : ce contrôle est TECHNIQUE. Il ne juge ni la qualité visuelle, ni la voix, ni l'exactitude des données.
Le manifeste est écrit par le pipeline lui-même (rendu.Renderer) : il prouve ce qui a été exécuté, pas une attestation
cryptographique ; un pipeline compromis pourrait le falsifier.

Utilisation :
    python video/controle_publication.py --mp4 video/sortie/video-du-jour.mp4 --manifest video/sortie/video-du-jour.manifeste.json
Code retour 0 = accepté, 2 = refusé. JSON sur la sortie standard.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import re
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LARGEUR, HAUTEUR = 1080, 1920
DUREE_MIN, DUREE_MAX = 12.0, 60.0        # secondes (Shorts <= 60 s ; Reels : 3 s minimum)
FPS_MIN, FPS_MAX = 24.0, 60.0
AUDIO_HZ_MAX = 48000                      # Meta : « AAC, 48khz sample rate maximum, 1 or 2 channels »
LUFS_MIN, LUFS_MAX = -18.0, -10.0         # cible du rendu : -14 LUFS (mesuré -14.0 sur un rendu réel)
PIC_MAX_DB = -0.5                         # crête (true peak) maximale tolérée
LUFS_SILENCE = -35.0                      # en dessous : piste quasi muette
ALLOWED_VIDEO_FILTERS = {"scale"}         # le filtre « scale » n'est admis que pour la conversion colorimétrique
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SLOT = re.compile(r"^\d{4}-\d{2}-\d{2}:(matin|soir)$")


@dataclass(frozen=True)
class Resultat:
    accepte: bool
    erreurs: tuple


def _resultat(erreurs):
    erreurs = tuple(dict.fromkeys(erreurs))
    return Resultat(not erreurs, erreurs)


# ---------- ffprobe / ffmpeg ----------

def sonder(chemin, timeout=30):
    """ffprobe -> dict. Lève subprocess.SubprocessError / OSError / ValueError en cas de problème."""
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,sample_aspect_ratio,"
         "sample_rate,channels:stream_tags=rotate:stream_side_data=rotation",
         "-of", "json", str(chemin)],
        capture_output=True, text=True, timeout=timeout, check=True)
    return json.loads(p.stdout)


def verifier_sonde(sonde, *, duree_min=DUREE_MIN, duree_max=DUREE_MAX):
    """Contrôles sur la sortie d'ffprobe (fonction pure, testable sans fichier)."""
    if not isinstance(sonde, dict) or not isinstance(sonde.get("streams"), list):
        return ("sonde_invalide",)
    e = []
    flux = [s for s in sonde["streams"] if isinstance(s, dict)]
    videos = [s for s in flux if s.get("codec_type") == "video"]
    audios = [s for s in flux if s.get("codec_type") == "audio"]
    if len(videos) != 1:
        e.append("un_seul_flux_video_attendu")
    else:
        v = videos[0]
        if (v.get("width"), v.get("height")) != (LARGEUR, HAUTEUR):
            e.append("resolution_incorrecte")
        if v.get("codec_name") != "h264":
            e.append("codec_video_incorrect")
        if v.get("pix_fmt") != "yuv420p":
            e.append("format_pixel_incorrect")
        try:
            a, b = (int(x) for x in str(v.get("avg_frame_rate", "")).split("/"))
            fps = a / b
            if not math.isfinite(fps) or not (FPS_MIN <= fps <= FPS_MAX):
                e.append("fps_incorrect")
        except (ValueError, ZeroDivisionError):
            e.append("fps_illisible")
        if v.get("sample_aspect_ratio") not in (None, "1:1", "0:1"):
            e.append("pixels_non_carres")
        rotations = [s.get("rotation") for s in v.get("side_data_list", []) if isinstance(s, dict) and "rotation" in s]
        rotations.append((v.get("tags") or {}).get("rotate") if isinstance(v.get("tags"), dict) else None)
        for r in rotations:
            if r is None:
                continue
            try:
                if float(r) != 0:
                    e.append("affichage_pivote")
            except (TypeError, ValueError):
                e.append("rotation_illisible")
    if len(audios) != 1:
        e.append("un_seul_flux_audio_attendu")
    else:
        a = audios[0]
        if a.get("codec_name") != "aac":
            e.append("codec_audio_incorrect")
        try:
            if int(a.get("sample_rate")) > AUDIO_HZ_MAX:
                e.append("audio_frequence_trop_elevee")   # contraire aux specs Reels (48 kHz max)
        except (TypeError, ValueError):
            e.append("audio_frequence_illisible")
        if a.get("channels") not in (1, 2):
            e.append("audio_canaux_incorrects")
    try:
        d = float(sonde.get("format", {}).get("duration"))
        if not math.isfinite(d) or not (duree_min <= d <= duree_max):
            e.append("duree_incorrecte")
    except (TypeError, ValueError, AttributeError):
        e.append("duree_illisible")
    return tuple(e)


def boites_mp4(octets):
    """Parcourt les boîtes de premier niveau : [(type, debut, fin)]. Lève ValueError si le fichier est incohérent."""
    res, pos, n = [], 0, len(octets)
    while pos < n:
        if pos + 8 > n:
            raise ValueError("boite tronquee")
        taille, typ = struct.unpack(">I4s", octets[pos:pos + 8])
        entete = 8
        if taille == 1:
            if pos + 16 > n:
                raise ValueError("boite tronquee")
            taille = struct.unpack(">Q", octets[pos + 8:pos + 16])[0]
            entete = 16
        elif taille == 0:
            taille = n - pos
        if taille < entete or pos + taille > n:
            raise ValueError("taille de boite invalide")
        res.append((typ.decode("latin-1"), pos, pos + taille))
        pos += taille
    return res


def verifier_conteneur(chemin):
    """moov avant mdat (démarrage rapide) et absence d'edit list (specs Reels). Binaire lu en entier (quelques Mo)."""
    try:
        octets = Path(chemin).read_bytes()
        boites = boites_mp4(octets)
    except (OSError, ValueError):
        return ("conteneur_illisible",)
    e = []
    types = [b[0] for b in boites]
    if "moov" not in types or "mdat" not in types:
        return ("conteneur_incomplet",)
    if types.index("moov") > types.index("mdat"):
        e.append("moov_apres_mdat")
    moov = next(b for b in boites if b[0] == "moov")
    if b"elst" in octets[moov[1]:moov[2]]:
        e.append("edit_list_presente")
    return tuple(e)


def verifier_decodage(chemin, timeout=180):
    """Décode intégralement les deux flux : détecte les troncatures que ffprobe laisse passer."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror", "-err_detect", "explode",
             "-i", str(chemin), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
            capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return ("decodage_trop_long",)
    except OSError:
        return ("ffmpeg_indisponible",)
    return () if p.returncode == 0 else ("decodage_echoue",)


def mesurer_loudness(chemin, timeout=180):
    """(LUFS intégrés, crête en dB) mesurés par ffmpeg ebur128. Lève ValueError si illisible."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(chemin), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, timeout=timeout, check=False)
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError("mesure impossible") from exc
    resume = p.stderr[p.stderr.rfind("Summary:"):] if "Summary:" in p.stderr else ""
    i = re.search(r"\bI:\s+(-?\d+(?:\.\d+)?|-inf)\s+LUFS", resume)
    pic = re.search(r"\bPeak:\s+(-?\d+(?:\.\d+)?|-inf)\s+dBFS", resume)
    if not i or not pic:
        raise ValueError("resume ebur128 introuvable")
    return float(i.group(1)), float(pic.group(1))


def verifier_audio(chemin, mesure=mesurer_loudness):
    try:
        lufs, pic = mesure(chemin)
    except (ValueError, OSError):
        return ("loudness_illisible",)
    if not math.isfinite(lufs) or lufs < LUFS_SILENCE:
        return ("audio_muet",)
    e = []
    if not (LUFS_MIN <= lufs <= LUFS_MAX):
        e.append("loudness_hors_plage")
    if pic > PIC_MAX_DB:
        e.append("crete_audio_trop_haute")
    return tuple(e)


# ---------- manifeste de rendu ----------

def sha256_fichier(chemin, bloc=1024 * 1024):
    h = hashlib.sha256()
    with Path(chemin).open("rb") as f:
        for morceau in iter(lambda: f.read(bloc), b""):
            h.update(morceau)
    return h.hexdigest()


def analyser_commande(commande, largeur=LARGEUR, hauteur=HAUTEUR):
    """Déduit de la commande ffmpeg réellement exécutée la taille d'entrée et la présence d'une mise à l'échelle.

    Renvoie (largeur_entree, hauteur_entree, redimensionne). `redimensionne` vaut True si un filtre autre que la
    conversion colorimétrique est présent, ou si la taille d'entrée diffère de la taille finale.
    """
    if not isinstance(commande, (list, tuple)) or not all(isinstance(x, str) for x in commande):
        raise ValueError("commande invalide")
    if "-s" not in commande:
        raise ValueError("taille d'entree absente")
    m = re.fullmatch(r"(\d+)x(\d+)", commande[commande.index("-s") + 1])
    if not m:
        raise ValueError("taille d'entree illisible")
    w, h = int(m.group(1)), int(m.group(2))
    redim = (w, h) != (largeur, hauteur)
    for opt in ("-vf", "-filter:v", "-filter_complex"):
        if opt in commande:
            for filtre in commande[commande.index(opt) + 1].split(","):
                nom, _, params = filtre.partition("=")
                if nom not in ALLOWED_VIDEO_FILTERS:
                    redim = True
                elif nom == "scale" and re.search(r"(^|:)(w|h|width|height)=|^\d", params):
                    redim = True   # un « scale » avec des dimensions n'est pas une conversion colorimétrique seule
    return w, h, redim


def construire_manifeste(mp4, commande, *, slot_id=None, format_video=None, titre=None, maintenant=None):
    """Manifeste écrit par le pipeline APRÈS l'encodage final (jamais « à la main » : tout vient de la commande exécutée)."""
    w, h, redim = analyser_commande(commande)
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    return {
        "schema_version": 1,
        "render_width": LARGEUR, "render_height": HAUTEUR,
        "source_canvases": [{"width": w, "height": h}],
        "upscaled_from_low_resolution": bool(redim),
        "final_mp4_sha256": sha256_fichier(mp4),
        "slot_id": slot_id, "format": format_video, "titre": titre,
        "genere_le": maintenant.astimezone(dt.timezone.utc).isoformat(timespec="seconds"),
        "commande_ffmpeg": list(commande),
    }


def ecrire_manifeste(chemin_manifeste, manifeste):
    Path(chemin_manifeste).write_text(json.dumps(manifeste, ensure_ascii=False, indent=2), encoding="utf-8")


def verifier_manifeste(manifeste, mp4, *, exiger_slot=False):
    if not isinstance(manifeste, dict) or manifeste.get("schema_version") != 1:
        return ("manifeste_schema_invalide",)
    e = []
    if manifeste.get("render_width") != LARGEUR or manifeste.get("render_height") != HAUTEUR:
        e.append("manifeste_canevas_incorrect")
    if manifeste.get("upscaled_from_low_resolution") is not False:
        e.append("mise_a_l_echelle_non_exclue")
    sources = manifeste.get("source_canvases")
    if not isinstance(sources, list) or not sources:
        e.append("sources_absentes")
    else:
        for s in sources:
            if not isinstance(s, dict) or type(s.get("width")) is not int or type(s.get("height")) is not int:
                e.append("source_invalide")
            elif s["width"] < LARGEUR or s["height"] < HAUTEUR:
                e.append("source_basse_resolution")
    attendu = manifeste.get("final_mp4_sha256")
    if not isinstance(attendu, str) or not SHA256.fullmatch(attendu):
        e.append("empreinte_invalide")
    else:
        try:
            if sha256_fichier(mp4) != attendu:
                e.append("empreinte_differente")
        except OSError:
            e.append("mp4_illisible")
    if exiger_slot and not (isinstance(manifeste.get("slot_id"), str) and SLOT.fullmatch(manifeste["slot_id"])):
        e.append("slot_invalide")
    return tuple(e)


# ---------- point d'entrée unique ----------

def valider_avant_publication(mp4, manifeste, *, sonder_fn=sonder, conteneur_fn=verifier_conteneur,
                              decodage_fn=verifier_decodage, audio_fn=verifier_audio, exiger_slot=False):
    """Exécute TOUS les contrôles sans s'arrêter au premier échec ; toute exception devient une erreur."""
    mp4, manifeste = Path(mp4), Path(manifeste)
    if not mp4.is_file():
        return Resultat(False, ("mp4_absent",))
    if mp4.stat().st_size < 1024:
        return Resultat(False, ("mp4_trop_petit",))
    erreurs = []

    def etape(nom, fn):
        try:
            res = fn()
            if not isinstance(res, tuple):
                raise TypeError("resultat inattendu")
            erreurs.extend(f"{nom}:{x}" for x in res)
        except Exception as exc:  # noqa: BLE001 - fail closed : une panne de contrôle refuse la publication
            erreurs.append(f"{nom}:exception_{type(exc).__name__}")

    etape("sonde", lambda: verifier_sonde(sonder_fn(mp4)))
    etape("conteneur", lambda: conteneur_fn(mp4))
    etape("decodage", lambda: decodage_fn(mp4))
    etape("audio", lambda: audio_fn(mp4))

    def _manifeste():
        if not manifeste.is_file():
            return ("manifeste_absent",)
        try:
            donnees = json.loads(manifeste.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ("manifeste_illisible",)
        return verifier_manifeste(donnees, mp4, exiger_slot=exiger_slot)
    etape("manifeste", _manifeste)
    return _resultat(erreurs)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--mp4", required=True)
    p.add_argument("--manifest", required=True)
    a = p.parse_args(argv)
    r = valider_avant_publication(a.mp4, a.manifest)
    print(json.dumps({"accepte": r.accepte, "erreurs": list(r.erreurs)}, ensure_ascii=False))
    return 0 if r.accepte else 2


if __name__ == "__main__":
    sys.exit(main())
