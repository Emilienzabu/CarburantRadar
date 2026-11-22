"""Voix off + musique : synthèse vocale, durée des scènes calée sur la voix, mixage avec baisse de la musique sous la voix."""
import asyncio
import os
import re
import subprocess
import time
import wave

import numpy as np

from musique import SR, render_music

VOIX_DEFAUT = "fr-FR-RemyMultilingualNeural"   # voix d'homme, la plus naturelle
VOIX_SECOURS = "fr-FR-HenriNeural"             # autre voix d'homme si la première est indisponible
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
        com = edge_tts.Communicate(texte, voix, rate="+4%")
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


def synth_clips(scenes_def, tmpdir, voix=VOIX_DEFAUT, log=print):
    """Renvoie une liste de tableaux (un par scène), ou [None, ...] si aucune voix d'homme n'est disponible."""
    for nom in dict.fromkeys([voix, VOIX_SECOURS]):
        clips = []
        try:
            for i, sc in enumerate(scenes_def):
                chemin = os.path.join(tmpdir, f"voix_{i}.mp3")
                _tts_edge(sc["texte"], nom, chemin)
                x = _decode(chemin)
                # petit fondu pour éviter les clics
                f = int(0.01 * SR)
                x[:f] *= np.linspace(0, 1, f)
                x[-f:] *= np.linspace(1, 0, f)
                clips.append(x)
            log(f"Voix : {nom}")
            peak = max(float(np.max(np.abs(c))) for c in clips)
            return [c * (0.92 / (peak + 1e-9)) for c in clips]
        except Exception as e:
            log(f"Voix {nom} indisponible : {e}")
    log("ATTENTION : aucune voix disponible.")
    return [None] * len(scenes_def)


# ---------- planification ----------

def planifier(scenes_def, clips, debut=DEBUT, fin=FIN):
    """Donne à chaque scène une durée adaptée à sa voix. Renvoie des scènes avec start/dur/caption."""
    scenes, t = [], 0.0
    for sc, clip in zip(scenes_def, clips):
        if clip is not None:
            besoin = debut + len(clip) / SR + fin
        else:
            besoin = debut + len(sc["texte"].split()) * 0.38 + fin
        dur = max(sc["min"], besoin)
        scenes.append({"id": sc["id"], "start": t, "dur": dur, "caption": sc.get("caption", sc["texte"]), "idx": sc.get("idx"), "voix_debut": t + debut})
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


# ---------- horodatage des mots (sous-titres mot à mot) ----------

DEBIT_VITRINE = "+10%"   # PROVISOIRE : débit à valider à l'oreille avec Remy (le format existant garde +4 %)
NEGATIONS = {"ne", "n'", "n’", "jamais", "rien", "personne", "aucun", "aucune"}


def prononcer_tokens(tokens):
    """Ajuste la prononciation (texte envoyé à la voix SEULEMENT, jamais affiché).

    Le « s » de « plus » se prononce quand « plus » est quantitatif : « plus de », « en plus », « de plus », « au plus »,
    ou en fin de proposition. Il reste muet devant un adjectif ou un adverbe (« plus cher ») et dans une négation
    (« ne … plus »). Pour la voix : « plusse ». Renvoie une nouvelle liste de mots (même longueur)."""
    bas = [t.lower() for t in tokens]
    negation = any(re.sub(r"[^\w'’]", "", b) in NEGATIONS or b.startswith(("n'", "n’")) for b in bas)
    sortie = []
    for i, tok in enumerate(tokens):
        m = re.fullmatch(r"(?i)(plus)([\W_]*)", tok)
        if not m or negation:
            sortie.append(tok)
            continue
        suivant = bas[i + 1] if i + 1 < len(bas) else ""
        precedent = re.sub(r"\W", "", bas[i - 1]) if i > 0 else ""
        fin_prop = bool(m.group(2)) and m.group(2)[0] in ".,;:!?"
        quantitatif = suivant.startswith(("de ", "d'", "d’")) or suivant == "de" or precedent in {"en", "de", "au"} or fin_prop
        sortie.append(m.group(1) + "se" + m.group(2) if quantitatif else tok)
    return sortie


def _syllabes(mot):
    """Nombre approximatif de syllabes d'un mot français (groupes de voyelles, « e » final muet), au moins 1."""
    m = re.sub(r"[^a-zàâäéèêëîïôöùûüœæç0-9]", "", mot.lower())
    if not m:
        return 1
    if m.isdigit():
        return max(1, len(m))
    n = len(re.findall(r"[aeiouyàâäéèêëîïôöùûüœæ]+", m))
    if m.endswith("e") and n > 1 and not m.endswith(("ée", "ie", "ue")):
        n -= 1
    return max(1, n)


def _plages_parole(clip, sr=SR, pas=0.01, creux=0.12):
    """Plages [(debut, fin)] en secondes où l'on parle (énergie > ~-26 dB du pic) ; les silences de moins de `creux` s
    sont absorbés. Renvoie [] si le clip est vide ou muet."""
    n = max(1, int(pas * sr))
    k = len(clip) // n
    if k == 0:
        return []
    env = np.sqrt(np.mean(clip[: k * n].reshape(k, n) ** 2, axis=1))
    if env.max() <= 1e-6:
        return []
    actif = env > env.max() * 0.05
    plages, a = [], None
    for i, v in enumerate(actif):
        if v and a is None:
            a = i
        elif not v and a is not None:
            plages.append([a, i])
            a = None
    if a is not None:
        plages.append([a, k])
    fus = []
    for p in plages:
        if fus and (p[0] - fus[-1][1]) * pas < creux:
            fus[-1][1] = p[1]
        else:
            fus.append(p)
    return [(a * pas, b * pas) for a, b in fus]


def aligner_estime(mots, clip, sr=SR):
    """Estime (debut, fin) de chaque mot quand le service ne fournit pas les limites de mots.

    `mots` = textes prononcés. Début et fin de parole viennent de l'énergie de l'audio ; les mots se répartissent selon
    leur nombre de syllabes. Si le nombre de plages de parole égale le nombre de propositions (coupées à la ponctuation),
    chaque proposition est calée sur sa plage. ESTIMATION : l'écart avec la vraie voix n'est pas mesuré ici."""
    if not mots:
        return []
    plages = _plages_parole(clip, sr)
    if not plages:
        d = len(clip) / sr
        plages = [(0.0, d)]
    groupes, cur = [], []
    for m in mots:
        cur.append(m)
        if m[-1:] in ",.;:!?…":
            groupes.append(cur)
            cur = []
    if cur:
        groupes.append(cur)
    if len(plages) == len(groupes):
        zones = list(zip(groupes, plages))
    else:
        zones = [(mots, (plages[0][0], plages[-1][1]))]
    res = []
    for ms, (a, b) in zones:
        poids = [_syllabes(m) + 0.15 for m in ms]
        total, cum = sum(poids), 0.0
        for m, w in zip(ms, poids):
            res.append((a + (b - a) * cum / total, a + (b - a) * (cum + w) / total))
            cum += w
    return res


def mapper_limites(tokens, limites):
    """Associe les limites de mots du service à des mots AFFICHÉS. `tokens` = [(affiché, prononcé)] ; un mot affiché peut
    couvrir plusieurs mots prononcés (« carburantradar.fr » -> « Carburant Radar point F R »). Renvoie None si le nombre de
    limites ne correspond pas (l'appelant se rabat alors sur l'estimation)."""
    n_attendu = sum(len(p.split()) for _, p in tokens)
    if len(limites) != n_attendu:
        return None
    res, i = [], 0
    for aff, pro in tokens:
        k = len(pro.split())
        res.append((aff, limites[i][1], limites[i + k - 1][2]))
        i += k
    return res


def _tts_edge_mots(texte, voix, chemin, rate):
    """Comme _tts_edge, avec les limites de mots du service. Renvoie [(texte, debut_s, fin_s)] ([] si non fournies)."""
    import edge_tts
    limites = []

    async def run():
        limites.clear()
        try:
            com = edge_tts.Communicate(texte, voix, rate=rate, boundary="WordBoundary")
        except TypeError:   # ancienne version d'edge-tts : pas de paramètre `boundary`
            com = edge_tts.Communicate(texte, voix, rate=rate)
        donnees = bytearray()
        async for morceau in com.stream():
            if morceau.get("type") == "audio":
                donnees.extend(morceau["data"])
            elif morceau.get("type") == "WordBoundary":   # offset et durée en pas de 100 ns
                limites.append((morceau["text"], morceau["offset"] / 1e7, (morceau["offset"] + morceau["duration"]) / 1e7))
        with open(chemin, "wb") as f:
            f.write(bytes(donnees))

    last = None
    for essai in range(3):
        try:
            asyncio.run(run())
            if os.path.getsize(chemin) > 1000:
                return list(limites)
        except Exception as e:  # réseau, service indisponible…
            last = e
        time.sleep(2 + essai * 2)
    raise RuntimeError(f"edge-tts indisponible : {last}")


def _tts_espeak(texte, chemin):
    """Voix locale de TEST (hors ligne) : jamais utilisée pour une publication."""
    subprocess.run(["espeak-ng", "-v", "fr", "-s", "165", "-w", chemin, texte], check=True, capture_output=True)


def synth_clips_mots(scenes_def, tmpdir, voix=VOIX_DEFAUT, log=print, rate=DEBIT_VITRINE, moteur="edge"):
    """Comme synth_clips, avec l'horodatage des mots. Renvoie (clips, mots) : `mots[i]` = [(mot affiché, debut_s, fin_s)]
    relatifs au début du clip de la scène i. Chaque scène peut porter `mots` = [(affiché, prononcé)] ; sinon les mots du
    texte sont pris tels quels. Une scène sans texte donne un clip vide. Si aucune voix n'est disponible : ([None]*n, [None]*n)."""
    def tokens(sc):
        return sc.get("mots") or [(m, m) for m in sc["texte"].split()]

    noms = [voix] if moteur == "espeak" else list(dict.fromkeys([voix, VOIX_SECOURS]))
    for nom in noms:
        clips, mots = [], []
        try:
            for i, sc in enumerate(scenes_def):
                toks = tokens(sc)
                if not toks:
                    clips.append(np.zeros(0, dtype=np.float32))
                    mots.append([])
                    continue
                texte = " ".join(p for _, p in toks)
                if moteur == "espeak":
                    chemin = os.path.join(tmpdir, f"voix_{i}.wav")
                    _tts_espeak(texte, chemin)
                    limites = []
                else:
                    chemin = os.path.join(tmpdir, f"voix_{i}.mp3")
                    limites = _tts_edge_mots(texte, nom, chemin, rate)
                x = _decode(chemin)
                f = int(0.01 * SR)
                x[:f] *= np.linspace(0, 1, f)
                x[-f:] *= np.linspace(1, 0, f)
                clips.append(x)
                m = mapper_limites(toks, limites) if limites else None
                if m is None:
                    est = aligner_estime(" ".join(p for _, p in toks).split(), x)   # un élément par mot PRONONCÉ
                    # un mot affiché couvre k mots prononcés : on fusionne les estimations
                    m, j = [], 0
                    for aff, pro in toks:
                        k = len(pro.split())
                        m.append((aff, est[j][0], est[j + k - 1][1]))
                        j += k
                    log(f"  scène {i} : horodatage ESTIMÉ ({'limites du service absentes' if not limites else 'nombre de limites inattendu'})")
                mots.append(m)
            log(f"Voix : {nom if moteur != 'espeak' else 'espeak-ng (TEST local)'}")
            pic = max((float(np.max(np.abs(c))) for c in clips if len(c)), default=0.0)
            if pic > 0:
                clips = [c * (0.92 / (pic + 1e-9)) for c in clips]
            return clips, mots
        except Exception as e:
            log(f"Voix {nom} indisponible : {e}")
    log("ATTENTION : aucune voix disponible.")
    return [None] * len(scenes_def), [None] * len(scenes_def)
