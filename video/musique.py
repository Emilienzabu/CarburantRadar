"""Musique de fond 100 % originale, générée par code (aucun droit d'auteur, aucun fichier à stocker).

Une piste = accords (pad) + arpège (pluck) + basse + batterie légère, avec effet de "pompage" sur les kicks
et un peu de réverbération. Tempo, tonalité et enchaînement d'accords changent selon la graine (le jour).
"""
import numpy as np

SR = 44100

# Dégrés de la gamme majeure (demi-tons depuis la tonique) et enchaînements d'accords (degré, qualité)
MAJOR = [0, 2, 4, 5, 7, 9, 11]
PROGRESSIONS = [
    [(0, "M"), (4, "M"), (5, "m"), (3, "M")],  # I  V  vi IV
    [(5, "m"), (3, "M"), (0, "M"), (4, "M")],  # vi IV I  V
    [(0, "M"), (5, "m"), (3, "M"), (4, "M")],  # I  vi IV V
    [(3, "M"), (0, "M"), (4, "M"), (5, "m")],  # IV I  V  vi
]


def _hz(midi):
    return 440.0 * 2 ** ((np.asarray(midi, dtype=np.float64) - 69) / 12)


def _chord_notes(root_midi, degree, quality):
    base = root_midi + MAJOR[degree]
    third = 3 if quality == "m" else 4
    return [base, base + third, base + 7]


def _saw(freq, n, phase=0.0):
    t = np.arange(n) / SR
    return 2.0 * ((freq * t + phase) % 1.0) - 1.0


def _lowpass(x, cutoff):
    """Filtre passe-bas par FFT avec pente douce (suffisant pour adoucir un pad)."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / SR)
    gain = 1.0 / (1.0 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec * gain, len(x))


def _highpass(x, cutoff):
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / SR)
    gain = 1.0 - 1.0 / (1.0 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec * gain, len(x))


def _env(n, attack, release, hold=None):
    """Enveloppe attaque/maintien/relâchement sur n échantillons."""
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    e = np.ones(n)
    a = min(a, n)
    e[:a] = np.linspace(0, 1, a)
    r = min(r, n)
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
        ir = rng.standard_normal(n_ir) * decay
        ir = _lowpass(ir, 5000)
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        wet_sig = np.fft.irfft(np.fft.rfft(stereo[:, ch], size) * np.fft.rfft(ir, size), size)[: stereo.shape[0]]
        out[:, ch] = stereo[:, ch] * (1 - wet) + wet_sig * wet * 2.2
    return out


def render_music(duration, seed=0):
    """Renvoie un tableau float32 (n, 2) de `duration` secondes, normalisé pour rester sous 0 dBFS."""
    rng = np.random.default_rng(seed)
    bpm = int(rng.choice([100, 104, 108, 112]))
    root = int(rng.choice([48, 50, 52, 53, 55]))  # C3, D3, E3, F3, G3
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    four_on_floor = bool(rng.integers(2))

    beat = 60.0 / bpm
    bar = 4 * beat
    total = duration + 2.0
    n = int(total * SR)
    n_bars = int(np.ceil(total / bar))

    pad = np.zeros(n)
    arp = np.zeros(n)
    bass = np.zeros(n)
    drums = np.zeros(n)
    kick_env = np.ones(n)  # pour le pompage du pad

    kick_len = int(0.28 * SR)
    t_k = np.arange(kick_len) / SR
    kick = np.sin(2 * np.pi * (45 * t_k + 75 * (1 - np.exp(-t_k * 28)) / 28)) * np.exp(-t_k * 14)
    clap_len = int(0.16 * SR)
    clap = _highpass(rng.standard_normal(clap_len), 1200) * np.exp(-np.arange(clap_len) / SR * 22)
    hat_len = int(0.05 * SR)
    hat = _highpass(rng.standard_normal(hat_len), 6500) * np.exp(-np.arange(hat_len) / SR * 70)

    for b in range(n_bars):
        t0 = b * bar
        degree, quality = prog[b % len(prog)]
        notes = _chord_notes(root, degree, quality)

        # Pad : 3 notes x 3 voix désaccordées
        L = int((bar + 0.5) * SR)
        chunk = np.zeros(L)
        for m in notes:
            for cents in (-9, 0, 9):
                f = float(_hz(m + 12 + cents / 100.0))
                chunk += _saw(f, L, phase=rng.random()) * 0.11
        chunk = _lowpass(chunk, 1400) * _env(L, 0.35, 0.5)
        _add(pad, chunk, t0)

        # Basse : fondamentale, deux notes par mesure
        for half in range(2):
            Lb = int(beat * 2 * SR)
            tb = np.arange(Lb) / SR
            f = float(_hz(notes[0] - 12))
            tone = (np.sin(2 * np.pi * f * tb) + 0.25 * np.sin(4 * np.pi * f * tb)) * np.exp(-tb * 1.6)
            _add(bass, tone * 0.5 * _env(Lb, 0.01, 0.15), t0 + half * 2 * beat)

        # Arpège en croches
        order = [0, 1, 2, 1, 0, 2, 1, 2]
        for i in range(8):
            Lp = int(0.45 * SR)
            tp = np.arange(Lp) / SR
            f = float(_hz(notes[order[i] % 3] + 24))
            tone = (np.sin(2 * np.pi * f * tp) + 0.35 * np.sin(4 * np.pi * f * tp)
                    + 0.15 * np.sin(6 * np.pi * f * tp)) * np.exp(-tp * 7.5)
            _add(arp, tone * 0.16, t0 + i * beat / 2)

        # Batterie
        for k in range(4):
            tk = t0 + k * beat
            if four_on_floor or k in (0, 2):
                _add(drums, kick * 0.9, tk)
                s = int(tk * SR)
                dur = int(0.30 * SR)
                if s < n:
                    kick_env[s:min(n, s + dur)] *= 1 - 0.45 * np.exp(-np.arange(min(n, s + dur) - s) / SR * 9)
            if k in (1, 3):
                _add(drums, clap * 0.22, tk)
            _add(drums, hat * 0.12, tk + beat / 2)
            if k % 2 == 1:
                _add(drums, hat * 0.06, tk)

    mono = pad * kick_env + arp + bass + drums

    # Pseudo-stéréo : arpège et pad légèrement décalés entre les deux canaux
    shift = int(0.012 * SR)
    left = pad * kick_env + bass + drums + arp
    right = pad * kick_env + bass + drums + np.roll(arp, shift)
    stereo = np.stack([left, right], axis=1)
    stereo = _reverb(stereo, seed=seed + 1)

    # Normalisation + fondu d'entrée/sortie
    stereo /= np.max(np.abs(stereo)) + 1e-9
    stereo *= 0.85
    out_n = int(duration * SR)
    stereo = stereo[:out_n]
    fade_in = int(0.4 * SR)
    fade_out = int(1.8 * SR)
    stereo[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    stereo[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    return stereo.astype(np.float32)
