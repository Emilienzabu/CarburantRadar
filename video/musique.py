"""Musique de fond 100 % originale, générée par code (aucun droit d'auteur, aucun fichier à stocker).

Chaque vidéo a sa propre piste : le style (lo-fi, pop, house, chill, funk, dream) change à chaque publication,
et tempo, tonalité, accords, rythme, basse et arpège varient en plus selon la graine.
"""
import numpy as np

SR = 44100

MAJOR = [0, 2, 4, 5, 7, 9, 11]
# enchaînements d'accords : (degré de la gamme, qualité M/m)
PROGRESSIONS = [
    [(0, "M"), (4, "M"), (5, "m"), (3, "M")],  # I  V  vi IV
    [(5, "m"), (3, "M"), (0, "M"), (4, "M")],  # vi IV I  V
    [(0, "M"), (5, "m"), (3, "M"), (4, "M")],  # I  vi IV V
    [(3, "M"), (0, "M"), (4, "M"), (5, "m")],  # IV I  V  vi
    [(0, "M"), (3, "M"), (5, "m"), (4, "M")],  # I  IV vi V
    [(5, "m"), (4, "M"), (3, "M"), (4, "M")],  # vi V  IV V
    [(0, "M"), (2, "m"), (3, "M"), (4, "M")],  # I  iii IV V
    [(3, "M"), (4, "M"), (2, "m"), (5, "m")],  # IV V  iii vi
]

STYLES = [
    {"nom": "lofi", "bpm": [76, 80, 84, 88], "drums": "halftime", "arp": "sparse", "pad_cut": 900,
     "wave": "tri", "swing": 0.14, "arp_oct": 24, "bell": False},
    {"nom": "pop", "bpm": [104, 108, 112], "drums": "backbeat", "arp": "eighth", "pad_cut": 1600,
     "wave": "saw", "swing": 0.0, "arp_oct": 24, "bell": False},
    {"nom": "house", "bpm": [118, 120, 122], "drums": "four", "arp": "sixteenth", "pad_cut": 2200,
     "wave": "saw", "swing": 0.0, "arp_oct": 12, "bell": False},
    {"nom": "chill", "bpm": [92, 96, 100], "drums": "twostep", "arp": "syncop", "pad_cut": 1200,
     "wave": "tri", "swing": 0.08, "arp_oct": 24, "bell": True},
    {"nom": "funk", "bpm": [100, 104, 108], "drums": "backbeat", "arp": "syncop", "pad_cut": 1800,
     "wave": "saw", "swing": 0.1, "arp_oct": 12, "bell": False},
    {"nom": "dream", "bpm": [84, 88, 92], "drums": "halftime", "arp": "eighth", "pad_cut": 1100,
     "wave": "tri", "swing": 0.0, "arp_oct": 36, "bell": True},
]

# grille de 16 doubles-croches par mesure
ARP_PATTERNS = {
    "sparse": [(0, 0), (3, 2), (6, 1), (8, 0), (11, 2), (14, 1)],
    "eighth": [(2 * i, t) for i, t in enumerate([0, 1, 2, 1, 0, 2, 1, 2])],
    "sixteenth": [(i, [0, 1, 2, 1][i % 4]) for i in range(16)],
    "syncop": [(0, 0), (3, 1), (6, 2), (8, 1), (10, 0), (13, 2)],
}
DRUMS = {
    "halftime": {"kick": [0, 10], "clap": [8], "hat": [2, 6, 10, 14]},
    "backbeat": {"kick": [0, 8, 10], "clap": [4, 12], "hat": [2, 6, 10, 14]},
    "four": {"kick": [0, 4, 8, 12], "clap": [4, 12], "hat": [2, 6, 10, 14]},
    "twostep": {"kick": [0, 7, 10], "clap": [4, 12], "hat": [2, 4, 6, 8, 10, 12, 14]},
}
BASS_PATTERNS = [[0, 8], [0, 6, 10], [0, 12], [0, 8, 14]]


def _hz(midi):
    return 440.0 * 2 ** ((np.asarray(midi, dtype=np.float64) - 69) / 12)


def _chord_notes(root_midi, degree, quality):
    base = root_midi + MAJOR[degree]
    third = 3 if quality == "m" else 4
    return [base, base + third, base + 7]


def _osc(wave, freq, n, phase=0.0):
    t = np.arange(n) / SR
    ph = (freq * t + phase) % 1.0
    if wave == "tri":
        return 4.0 * np.abs(ph - 0.5) - 1.0
    return 2.0 * ph - 1.0


def _lowpass(x, cutoff):
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / SR)
    return np.fft.irfft(spec / (1.0 + (freqs / cutoff) ** 4), len(x))


def _highpass(x, cutoff):
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / SR)
    return np.fft.irfft(spec * (1.0 - 1.0 / (1.0 + (freqs / cutoff) ** 4)), len(x))


def _env(n, attack, release):
    a, r = min(max(1, int(attack * SR)), n), min(max(1, int(release * SR)), n)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    e[n - r:] *= np.linspace(1, 0, r)
    return e


def _add(dst, src, start):
    s = int(start * SR)
    if s >= len(dst):
        return
    end = min(len(dst), s + len(src))
    dst[s:end] += src[: end - s]


def _reverb(stereo, wet=0.22, seconds=1.6, seed=1):
    rng = np.random.default_rng(seed)
    n_ir = int(seconds * SR)
    decay = np.exp(-np.linspace(0, 6.5, n_ir))
    out = np.zeros_like(stereo)
    n = stereo.shape[0] + n_ir
    size = 1 << (n - 1).bit_length()
    for ch in range(2):
        ir = _lowpass(rng.standard_normal(n_ir) * decay, 5000)
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        wet_sig = np.fft.irfft(np.fft.rfft(stereo[:, ch], size) * np.fft.rfft(ir, size), size)[: stereo.shape[0]]
        out[:, ch] = stereo[:, ch] * (1 - wet) + wet_sig * wet * 2.2
    return out


def render_music(duration, seed=0):
    """float32 (n, 2) de `duration` secondes. Le style dépend de la graine : deux publications de suite ne se ressemblent pas."""
    style = STYLES[seed % len(STYLES)]
    rng = np.random.default_rng(seed * 7919 + 13)
    bpm = int(rng.choice(style["bpm"]))
    root = int(rng.choice([46, 48, 50, 51, 53, 55]))
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    bass_pat = BASS_PATTERNS[int(rng.integers(len(BASS_PATTERNS)))]
    pad_shift = int(rng.choice([0, 12]))
    drums = DRUMS[style["drums"]]
    arp_pat = ARP_PATTERNS[style["arp"]]
    arp_gain = 0.11 if style["arp"] == "sixteenth" else 0.16

    step = 60.0 / bpm / 4          # durée d'une double-croche
    bar = step * 16
    total = duration + 2.0
    n = int(total * SR)
    n_bars = int(np.ceil(total / bar))

    def when(b, s):
        shift = style["swing"] * (step * 2) if s % 4 == 2 else 0.0
        return b * bar + s * step + shift

    pad, arp, bass, dr = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    kick_env = np.ones(n)

    kl = int(0.28 * SR)
    t_k = np.arange(kl) / SR
    kick = np.sin(2 * np.pi * (45 * t_k + 75 * (1 - np.exp(-t_k * 28)) / 28)) * np.exp(-t_k * 14)
    cl = int(0.16 * SR)
    clap = _highpass(rng.standard_normal(cl), 1200) * np.exp(-np.arange(cl) / SR * 22)
    hl = int(0.05 * SR)
    hat = _highpass(rng.standard_normal(hl), 6500) * np.exp(-np.arange(hl) / SR * 70)

    for b in range(n_bars):
        degree, quality = prog[b % len(prog)]
        notes = _chord_notes(root, degree, quality)

        # pad : 3 notes x 3 voix désaccordées
        L = int((bar + 0.6) * SR)
        chunk = np.zeros(L)
        for m in notes:
            for cents in (-9, 0, 9):
                f = float(_hz(m + 12 + pad_shift + cents / 100.0))
                chunk += _osc(style["wave"], f, L, rng.random()) * 0.11
        chunk = _lowpass(chunk, style["pad_cut"]) * _env(L, 0.35, 0.5)
        _add(pad, chunk, b * bar)

        # basse
        for s in bass_pat:
            Lb = int(step * 6 * SR)
            tb = np.arange(Lb) / SR
            f = float(_hz(notes[0] - 12))
            tone = (np.sin(2 * np.pi * f * tb) + 0.25 * np.sin(4 * np.pi * f * tb)) * np.exp(-tb * 2.2)
            _add(bass, tone * 0.5 * _env(Lb, 0.01, 0.12), when(b, s))

        # arpège
        for s, tone_idx in arp_pat:
            Lp = int(0.5 * SR)
            tp = np.arange(Lp) / SR
            f = float(_hz(notes[tone_idx % 3] + style["arp_oct"]))
            tone = (np.sin(2 * np.pi * f * tp) + 0.35 * np.sin(4 * np.pi * f * tp)
                    + 0.15 * np.sin(6 * np.pi * f * tp)) * np.exp(-tp * 7.5)
            if style["bell"]:
                tone += 0.25 * np.sin(2 * np.pi * f * 2.76 * tp) * np.exp(-tp * 11)
            _add(arp, tone * arp_gain, when(b, s))

        # batterie
        for s in drums["kick"]:
            tk = when(b, s)
            _add(dr, kick * 0.9, tk)
            i0 = int(tk * SR)
            i1 = min(n, i0 + int(0.30 * SR))
            if i0 < n:
                kick_env[i0:i1] *= 1 - 0.45 * np.exp(-np.arange(i1 - i0) / SR * 9)
        for s in drums["clap"]:
            _add(dr, clap * 0.22, when(b, s))
        for s in drums["hat"]:
            _add(dr, hat * 0.11, when(b, s))

    shift = int(0.012 * SR)
    left = pad * kick_env + bass + dr + arp
    right = pad * kick_env + bass + dr + np.roll(arp, shift)
    stereo = _reverb(np.stack([left, right], axis=1), seed=seed + 1)

    stereo /= np.max(np.abs(stereo)) + 1e-9
    stereo *= 0.85
    stereo = stereo[: int(duration * SR)]
    fi, fo = int(0.4 * SR), int(1.8 * SR)
    stereo[:fi] *= np.linspace(0, 1, fi)[:, None]
    stereo[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return stereo.astype(np.float32)
