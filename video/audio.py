"""Voix off + musique : synthèse vocale, durée des scènes calée sur la voix, mixage avec baisse de la musique sous la voix."""
import asyncio
import os
import subprocess
import time
import wave

import numpy as np

from musique import SR, render_music

VOIX_DEFAUT = "fr-FR-DeniseNeural"
DEBUT = 0.35   # silence avant la voix dans chaque scène
FIN = 0.75     # silence après la voix


# ---------- synthèse vocale ----------

def _decode(path):
    """mp3/wav -> tableau float32 mono à 44,1 kHz."""
    out = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def _tts_edge(texte, voix, chemin):
    import edge_tts

    async def run():
        com = edge_tts.Communicate(texte, voix, rate="+6%")
        await com.save(chemin)

    last = None
    for essai in range(3):
        try:
            asyncio.run(run())
            if os.path.getsize(chemin) > 1000:
                return
        except Exception as e:  # réseau, service indisponible…
            last = e
        time.sleep(2 + essai * 2)
    raise RuntimeError(f"edge-tts indisponible : {last}")


def _tts_gtts(texte, voix, chemin):
    from gtts import gTTS
    gTTS(texte, lang="fr").save(chemin)


def synth_clips(scenes_def, tmpdir, voix=VOIX_DEFAUT, log=print):
    """Renvoie une liste de tableaux (un par scène) ou None pour une scène sans voix."""
    for nom, fn in (("edge-tts", _tts_edge), ("gTTS", _tts_gtts)):
        clips = []
        try:
            for i, sc in enumerate(scenes_def):
                chemin = os.path.join(tmpdir, f"voix_{i}.mp3")
                fn(sc["texte"], voix, chemin)
                x = _decode(chemin)
                # petit fondu pour éviter les clics + coupe le silence de fin
                f = int(0.01 * SR)
                x[:f] *= np.linspace(0, 1, f)
                x[-f:] *= np.linspace(1, 0, f)
                clips.append(x)
            log(f"Voix : {nom}")
            peak = max(float(np.max(np.abs(c))) for c in clips)
            return [c * (0.92 / (peak + 1e-9)) for c in clips]
        except Exception as e:
            log(f"Voix {nom} indisponible : {e}")
    log("ATTENTION : aucune voix disponible, la vidéo sera publiée avec musique et texte seulement.")
    return [None] * len(scenes_def)


# ---------- planification ----------

def planifier(scenes_def, clips):
    """Donne à chaque scène une durée adaptée à sa voix. Renvoie des scènes avec start/dur/caption."""
    scenes, t = [], 0.0
    for sc, clip in zip(scenes_def, clips):
        if clip is not None:
            besoin = DEBUT + len(clip) / SR + FIN
        else:
            besoin = DEBUT + len(sc["texte"].split()) * 0.38 + FIN
        dur = max(sc["min"], besoin)
        scenes.append({"id": sc["id"], "start": t, "dur": dur, "caption": sc.get("caption", sc["texte"]), "voix_debut": t + DEBUT})
        t += dur
    return scenes


# ---------- mixage ----------

def _moyenne_glissante(x, fenetre):
    pad = np.pad(x, (fenetre // 2, fenetre - fenetre // 2), mode="edge")
    cs = np.cumsum(pad, dtype=np.float64)
    return ((cs[fenetre:] - cs[:-fenetre]) / fenetre)[: len(x)].astype(np.float32)


def mixer(scenes, clips, seed):
    total = scenes[-1]["start"] + scenes[-1]["dur"]
    n = int(total * SR)
    voix = np.zeros(n, dtype=np.float32)
    for sc, clip in zip(scenes, clips):
        if clip is None:
            continue
        s = int(sc["voix_debut"] * SR)
        e = min(n, s + len(clip))
        voix[s:e] += clip[: e - s]

    musique = render_music(total, seed)

    if voix.any():
        env = np.sqrt(_moyenne_glissante(voix ** 2, int(0.12 * SR)))
        env = np.clip(env / 0.07, 0, 1)
        env = _moyenne_glissante(env, int(0.40 * SR))
        gain = 0.52 - 0.36 * env          # ~0.52 sans voix, ~0.16 quand on parle
    else:
        gain = np.full(n, 0.8, dtype=np.float32)

    mix = musique * gain[:, None] + voix[:, None] * 0.95
    mix = np.tanh(mix * 1.15) / np.tanh(1.15)   # limiteur doux
    return mix.astype(np.float32)


def ecrire_wav(chemin, stereo):
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    with wave.open(chemin, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
