#!/usr/bin/env python3
"""Rapport OBJECTIF sur une vidéo « vitrine » générée (mesures seulement : aucun jugement d'écoute).

Usage : python video/diagnostic_vitrine.py VIDEO.mp4 [VIDEO.mots.json]
        (le .mots.json est écrit par generate_video.py à côté du MP4 ; par défaut même nom que la vidéo)

Mesure : caractéristiques du fichier, loudness, synchronisation mots/voix (limites de mots comparées à l'énergie réelle
de la voix seule), niveau voix/musique, instants des animations par rapport aux mots clés, largeur des sous-titres.
Chaque écart est signalé « ÉCART » ; la sortie se lit dans le journal de l'exécution GitHub Actions.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio  # noqa: E402
import vitrine  # noqa: E402

SEUIL_SYNCHRO = 0.15   # s : écart toléré entre limite de mot et énergie de la voix


def sonde(chemin):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,r_frame_rate,pix_fmt,nb_frames,sample_rate,channels",
                          "-show_entries", "format=duration", "-of", "json", chemin], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def loudness(chemin):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", chemin, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    bloc = r[r.rfind("Summary"):]
    return {k: re.search(rf"{k}:\s+(-?[\d.]+)", bloc).group(1) if re.search(rf"{k}:\s+(-?[\d.]+)", bloc) else "?" for k in ("I", "LRA", "Peak")}


def db_rms(x, sr, a, b):
    seg = x[int(a * sr):int(b * sr)]
    return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9) if len(seg) else float("nan")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    mp4 = sys.argv[1]
    mots_json = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(mp4)[0] + ".mots.json"
    ecarts = []

    print("=== Fichier ===")
    info = sonde(mp4)
    v = next(s for s in info["streams"] if "width" in s)
    a = next(s for s in info["streams"] if "sample_rate" in s)
    print(f"vidéo {v['codec_name']} {v['width']}x{v['height']} {v['r_frame_rate']} {v['pix_fmt']} images={v.get('nb_frames')} | "
          f"audio {a['codec_name']} {a['sample_rate']} Hz {a['channels']} canaux | durée {float(info['format']['duration']):.2f} s")
    if (v["width"], v["height"]) != (1080, 1920):
        ecarts.append("dimensions")
    l = loudness(mp4)
    print(f"loudness I={l['I']} LUFS  LRA={l['LRA']}  crête vraie={l['Peak']} dBFS")
    if l["Peak"] not in ("?",) and float(l["Peak"]) > -1.0:
        ecarts.append("crête vraie > -1 dBFS")

    scenes = json.load(open(mots_json, encoding="utf-8"))
    mix = audio._decode(mp4)
    sr = audio.SR

    print("\n=== Synchronisation mots / voix (limites de mots vs énergie de la voix seule) ===")
    for sc in scenes:
        if not sc["mots"]:
            continue
        deb_mot, fin_mot = sc["mots"][0][1], sc["mots"][-1][2]
        if not sc["plages"]:
            print(f"{sc['id']:8s} aucune plage de parole détectée"); ecarts.append(f"{sc['id']}: voix muette"); continue
        deb_voix, fin_voix = sc["plages"][0][0], sc["plages"][-1][1]
        d1, d2 = deb_mot - deb_voix, fin_mot - fin_voix
        marque = "" if max(abs(d1), abs(d2)) <= SEUIL_SYNCHRO else "  <-- ÉCART"
        if marque:
            ecarts.append(f"{sc['id']}: synchro {d1 * 1000:+.0f}/{d2 * 1000:+.0f} ms")
        print(f"{sc['id']:8s} début mot - début voix = {d1 * 1000:+5.0f} ms | fin mot - fin voix = {d2 * 1000:+5.0f} ms | {len(sc['mots'])} mots, {len(sc['plages'])} plages{marque}")
        pauses = [m[2] for m in sc["mots"][:-1] if m[0][-1:] in ",.;:!?"]
        if len(pauses) + 1 == len(sc["plages"]):
            for k, (t_mot, (_, fin_p)) in enumerate(zip(pauses, sc["plages"])):
                d = t_mot - fin_p
                flag = "" if abs(d) <= SEUIL_SYNCHRO else "  <-- ÉCART"
                if flag:
                    ecarts.append(f"{sc['id']}: pause {k + 1} {d * 1000:+.0f} ms")
                print(f"           pause {k + 1} : fin du mot - fin de la plage = {d * 1000:+5.0f} ms{flag}")
        else:
            print(f"           ({len(sc['plages'])} plages pour {len(pauses) + 1} propositions : comparaison par pause non applicable)")
    print("\nMots (scène : mot début-fin en s) :")
    for sc in scenes:
        print(f"  {sc['id']}: " + " | ".join(f"{m[0]} {m[1]:.2f}-{m[2]:.2f}" for m in sc["mots"]) if sc["mots"] else f"  {sc['id']}: (sans voix)")

    print("\n=== Voix / musique (mixage final, dBFS RMS) ===")
    mots_all = [(m[1], m[2]) for sc in scenes for m in sc["mots"] if m[2] - m[1] > 0.1]
    voix_db = np.nanmean([db_rms(mix, sr, a_, b_) for a_, b_ in mots_all]) if mots_all else float("nan")
    creux = [db_rms(mix, sr, sc["start"], sc["start"] + 0.2) for sc in scenes[1:]]
    fin_ = scenes[-1]
    musique_fin = db_rms(mix, sr, fin_["start"] + 0.4, fin_["start"] + fin_["dur"] - 0.3)
    print(f"sur les mots : {voix_db:.1f} | début de scène (musique remontée) : {np.nanmean(creux):.1f} | écran de fin (musique seule) : {musique_fin:.1f}")
    print(f"marge voix - musique remontée : {voix_db - np.nanmean(creux):.1f} dB (à confirmer à l'oreille)")

    print("\n=== Animations vs mots clés ===")
    ecrans = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vitrine")
    polices = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    icone = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "icons", "icon-512.png")
    sc_r = [{"id": s["id"], "start": s["start"], "dur": s["dur"], "voix_debut": s["voix_debut"],
             "mots": [tuple(m) for m in s["mots"]]} for s in scenes]
    r = vitrine.RendererVitrine(vitrine.info_vitrine(), sc_r, polices, icone, ecrans)
    attendus = {"radar": [("stations", 1.0), ("économies", 2.9)], "trajet": [("détour", 0.9), ("coût", 2.9)],
                "analyse": [("évolution", 0.9), ("mois", 2.6)], "carte": [("tout", 2.0)]}
    for sc in sc_r:
        for mot, defaut in attendus.get(sc["id"], []):
            t = r._cue(sc, mot, None)
            print(f"{sc['id']:8s} « {mot} » {'à %.2f s de la scène' % t if t is not None else 'INTROUVABLE (instant par défaut %.1f s)' % defaut}")
            if t is None:
                ecarts.append(f"{sc['id']}: mot clé « {mot} » introuvable")
    fins = {}
    for sc in sc_r:
        c = lambda m, d: (r._cue(sc, m, None) if r._cue(sc, m, None) is not None else d)
        if sc["id"] == "radar":
            fins["radar"] = c("économies", 2.9) + 0.6
        elif sc["id"] == "trajet":
            t0 = c("détour", 0.9)
            fins["trajet"] = max(t0 + 2.0, c("coût", t0 + 2.0)) + 1.4 + 0.4
        elif sc["id"] == "analyse":
            fin = c("évolution", 0.9) - 0.1 + 1.7
            fins["analyse"] = max(fin - 0.3, min(c("mois", fin), fin + 0.6)) + 0.6
        elif sc["id"] == "carte":
            fins["carte"] = c("tout", 2.0) + 0.5
    for sc in sc_r:
        if sc["id"] in fins:
            marge = sc["dur"] - 0.1 - fins[sc["id"]]
            flag = "" if marge >= 0 else "  <-- ÉCART (l'animation n'a pas fini avant la fin de la scène)"
            if flag:
                ecarts.append(f"{sc['id']}: animation coupée ({marge:+.2f} s)")
            print(f"{sc['id']:8s} animation terminée à {fins[sc['id']]:.2f} s pour une scène de {sc['dur']:.2f} s (marge {marge:+.2f} s){flag}")

    print("\n=== Sous-titres ===")
    f = r.F.get("bold", 62)
    large = max(c["x"][-1] + f.getlength(c["mots"][-1][0]) - c["x"][0] for c in r.chunks)
    print(f"{len(r.chunks)} groupes de mots, largeur maximale {large:.0f} px (limite {vitrine.LARGEUR_MAX_SOUS_TITRES})")
    if large > vitrine.LARGEUR_MAX_SOUS_TITRES + 1:
        ecarts.append("sous-titres trop larges")

    print("\n=== Bilan ===")
    print("ÉCARTS : " + ("; ".join(ecarts) if ecarts else "aucun sur les critères mesurés") + "\nCe rapport ne remplace pas l'écoute : voix, débit et musique restent à juger par une personne.")


if __name__ == "__main__":
    main()
