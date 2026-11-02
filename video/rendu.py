"""Rendu des images de la vidéo (Pillow) et encodage (ffmpeg).

Format 1080x1920 (9:16), 30 images/s. Les éléments graphiques (cartes, pastilles, sous-titres) sont dessinés
en 3x puis réduits pour avoir des bords lisses ; seuls les textes animés sont redessinés à chaque image.
"""
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from donnees import fr_eur, fr_prix3

W, H, FPS = 1080, 1920, 30
SS = 3  # sur-échantillonnage des sprites

ACCENT = (245, 166, 35)
GOOD = (61, 220, 151)
TEXT = (232, 232, 240)
MUTED = (163, 163, 189)
SURFACE = (22, 22, 31)
BORDER = (37, 37, 53)
BG_TOP = (10, 10, 15)
BG_BOT = (22, 22, 36)
DARK = (10, 10, 15)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x ** 3


def ease_back(x):
    """Arrivée avec un léger dépassement (effet "pop")."""
    x = clamp(x)
    c1, c3 = 1.2, 2.2
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def mix(color, a, base=(14, 14, 22)):
    """Fait "apparaître" une couleur depuis le fond (a = 0..1)."""
    a = clamp(a)
    return tuple(int(base[i] + (color[i] - base[i]) * a) for i in range(3))


class Fonts:
    FILES = {"bold": "Poppins-Bold.ttf", "semibold": "Poppins-SemiBold.ttf", "medium": "Poppins-Medium.ttf"}
    FALLBACKS = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    def __init__(self, fonts_dir):
        self.dir = fonts_dir
        self.cache = {}

    def get(self, weight, size):
        size = int(size)
        key = (weight, size)
        if key not in self.cache:
            path = os.path.join(self.dir, self.FILES[weight])
            if not os.path.isfile(path):
                path = next(p for p in self.FALLBACKS if os.path.isfile(p))
            self.cache[key] = ImageFont.truetype(path, size)
        return self.cache[key]


def truncate(text, font, max_w):
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text + "…") > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap(text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_sprite(w, h, draw_fn):
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(img), SS)
    return img.resize((w, h), Image.LANCZOS)


def paste(img, sp, x, y, alpha=1.0):
    if alpha <= 0.003:
        return
    if alpha < 0.997:
        a = sp.getchannel("A").point(lambda v: int(v * alpha))
        sp = sp.copy()
        sp.putalpha(a)
    img.paste(sp, (int(x), int(y)), sp)


class Renderer:
    def __init__(self, info, scenes, fonts_dir, icon_path):
        self.info = info
        self.scenes = scenes
        self.total = scenes[-1]["start"] + scenes[-1]["dur"]
        self.F = Fonts(fonts_dir)
        self.icon = Image.open(icon_path).convert("RGBA") if icon_path and os.path.isfile(icon_path) else None
        self.base = self._make_base()
        self.glow = self._make_glow()
        self.sprites = {}
        self._prepare_sprites()

    # ---------- éléments fixes ----------

    def _make_base(self):
        ys = np.linspace(0, 1, H)[:, None, None]
        top, bot = np.array(BG_TOP), np.array(BG_BOT)
        arr = (top + (bot - top) * ys).repeat(W, axis=1).astype(np.uint8)
        img = Image.fromarray(arr, "RGB")

        # En-tête : logo + nom (zone sûre, sous la barre d'état)
        d = ImageDraw.Draw(img)
        x0, y0 = 70, 120
        if self.icon:
            ic = self.icon.resize((96, 96), Image.LANCZOS)
            mask = make_sprite(96, 96, lambda dd, s: dd.rounded_rectangle((0, 0, 96 * s - 1, 96 * s - 1), radius=24 * s, fill=(255, 255, 255, 255)))
            img.paste(ic.convert("RGB"), (x0, y0), mask.getchannel("A"))
        d.text((x0 + 120, y0 + 48), "Carburant", font=self.F.get("bold", 54), fill=TEXT, anchor="lm")
        w1 = self.F.get("bold", 54).getlength("Carburant")
        d.text((x0 + 120 + w1, y0 + 48), "Radar", font=self.F.get("bold", 54), fill=ACCENT, anchor="lm")
        return img

    def _make_glow(self):
        size = 1100
        yy, xx = np.mgrid[0:size, 0:size]
        r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
        a = (np.clip(1 - r, 0, 1) ** 2 * 255).astype(np.uint8)
        return Image.fromarray(a, "L")

    def _draw_glow(self, img, t):
        cx = 540 + 280 * math.sin(t * 0.32)
        cy = 560 + 170 * math.cos(t * 0.25)
        m1 = self.glow.point(lambda v: int(v * 0.16))
        img.paste(Image.new("RGB", self.glow.size, ACCENT), (int(cx - 550), int(cy - 550)), m1)
        cx2 = 540 - 260 * math.sin(t * 0.21 + 1)
        cy2 = 1500 + 120 * math.cos(t * 0.3)
        m2 = self.glow.point(lambda v: int(v * 0.09))
        img.paste(Image.new("RGB", self.glow.size, GOOD), (int(cx2 - 550), int(cy2 - 550)), m2)

    # ---------- sprites ----------

    def pill(self, text, color, filled=False, size=36, pad=34, height=76):
        f = self.F.get("bold", size)
        w = int(f.getlength(text) + pad * 2)

        def fn(d, s):
            fb = self.F.get("bold", size * s)
            if filled:
                d.rounded_rectangle((0, 0, w * s - 1, height * s - 1), radius=(height // 2) * s, fill=color)
                d.text((w * s // 2, height * s // 2), text, font=fb, fill=DARK, anchor="mm")
            else:
                d.rounded_rectangle((0, 0, w * s - 1, height * s - 1), radius=(height // 2) * s, fill=color)
                d.rounded_rectangle((3 * s, 3 * s, w * s - 1 - 3 * s, height * s - 1 - 3 * s),
                                    radius=(height // 2 - 3) * s, fill=(18, 18, 26, 255))
                d.text((w * s // 2, height * s // 2), text, font=fb, fill=color, anchor="mm")
        return make_sprite(w, height, fn)

    def caption(self, text, width=920):
        f = self.F.get("medium", 44 * SS)
        lines = wrap(text, f, (width - 80) * SS)
        line_h = 64
        h = len(lines) * line_h + 52

        def fn(d, s):
            d.rounded_rectangle((0, 0, width * s - 1, h * s - 1), radius=38 * s, fill=(8, 8, 14, 214))
            ff = self.F.get("medium", 44 * s)
            for i, line in enumerate(lines):
                d.text((width * s // 2, (26 + line_h // 2 + i * line_h) * s), line, font=ff, fill=TEXT, anchor="mm")
        return make_sprite(width, h, fn)

    def card(self, rank, prix, adresse, ecart, best):
        w, h = 920, 240

        def fn(d, s):
            fill = (22, 38, 36, 255) if best else (*SURFACE, 255)
            border = GOOD if best else BORDER
            d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=38 * s, fill=border)
            d.rounded_rectangle((3 * s, 3 * s, w * s - 1 - 3 * s, h * s - 1 - 3 * s), radius=35 * s, fill=fill)
            cx, cy, r = 84 * s, (h // 2) * s, 46 * s
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOOD if best else BORDER)
            d.text((cx, cy - 2 * s), str(rank), font=self.F.get("bold", 54 * s), fill=DARK if best else TEXT, anchor="mm")
            d.text((170 * s, 88 * s), fr_prix3(prix) + " €", font=self.F.get("bold", 98 * s),
                   fill=GOOD if best else TEXT, anchor="lm")
            fa = self.F.get("medium", 33 * s)
            d.text((170 * s, 178 * s), truncate(adresse, fa, 500 * s), font=fa, fill=MUTED, anchor="lm")
            if best:
                tag = "LA MOINS CHÈRE"
                ft = self.F.get("bold", 25 * s)
                tw = int(ft.getlength(tag) / s + 44)
                x1, y1 = (w - 34) * s, 40 * s
                d.rounded_rectangle((x1 - tw * s, y1, x1, y1 + 56 * s), radius=28 * s, fill=GOOD)
                d.text((x1 - tw * s // 2, y1 + 28 * s), tag, font=ft, fill=DARK, anchor="mm")
            else:
                d.text(((w - 40) * s, 88 * s), "+" + fr_prix3(ecart) + " €", font=self.F.get("bold", 38 * s),
                       fill=MUTED, anchor="rm")
        return make_sprite(w, h, fn)

    def row(self, label, value, color):
        w, h = 920, 112

        def fn(d, s):
            d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=34 * s, fill=(*SURFACE, 255))
            d.text((44 * s, (h // 2) * s), label, font=self.F.get("semibold", 40 * s), fill=MUTED, anchor="lm")
            d.text(((w - 44) * s, (h // 2) * s), value, font=self.F.get("bold", 54 * s), fill=color, anchor="rm")
        return make_sprite(w, h, fn)

    def button(self, text):
        f = self.F.get("bold", 74)
        w, h = int(f.getlength(text) + 150), 150

        def fn(d, s):
            d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=(h // 2) * s, fill=ACCENT)
            d.text((w * s // 2, (h // 2 - 2) * s), text, font=self.F.get("bold", 74 * s), fill=DARK, anchor="mm")
        return make_sprite(w, h, fn)

    def _prepare_sprites(self):
        info, S = self.info, self.sprites
        S["pill"] = self.pill(f"{info['carburant_label'].upper()} · {info['ville'].upper()}", ACCENT)
        S["cards"] = [self.card(i + 1, s["prix"], s["adresse"], s["prix"] - info["top3"][0]["prix"], i == 0)
                      for i, s in enumerate(info["top3"])]
        S["row_moy"] = self.row("Station moyenne", fr_eur(info["cout_moy"]) + " €", MUTED)
        S["row_min"] = self.row("La moins chère", fr_eur(info["cout_min"]) + " €", GOOD)
        S["button"] = self.button("carburantradar.fr")
        for sc in self.scenes:
            sc["cap"] = self.caption(sc["caption"])
        if self.icon:
            big = self.icon.resize((300, 300), Image.LANCZOS)
            mask = make_sprite(300, 300, lambda d, s: d.rounded_rectangle((0, 0, 300 * s - 1, 300 * s - 1), radius=72 * s, fill=(255, 255, 255, 255)))
            big.putalpha(mask.getchannel("A"))
            S["icon"] = big

    # ---------- scènes ----------

    def text_c(self, d, xy, text, weight, size, color, alpha=1.0, anchor="mm"):
        d.text(xy, text, font=self.F.get(weight, size), fill=mix(color, alpha), anchor=anchor)

    def _caption(self, img, sc, tl, y=1380):
        a = ease_out((tl - 0.35) / 0.35)
        cap = sc["cap"]
        paste(img, cap, (W - cap.width) // 2, y + (1 - a) * 24, a)

    def _scene_hook(self, img, tl, dur, sc):
        d = ImageDraw.Draw(img)
        S = self.sprites
        a = ease_out(tl / 0.45)
        pill = S["pill"]
        paste(img, pill, (W - pill.width) // 2, 470 + (1 - a) * 40, a)

        k = ease_out((tl - 0.3) / 1.4)
        value = self.info["ecart_plein"] * k
        size = int(250 * (0.92 + 0.08 * ease_back((tl - 0.2) / 0.7)))
        self.text_c(d, (W // 2, 840), fr_eur(value) + " €", "bold", size, ACCENT, ease_out((tl - 0.15) / 0.3))

        a2 = ease_out((tl - 1.1) / 0.5)
        self.text_c(d, (W // 2, 1065 + (1 - a2) * 30), "d'écart sur un plein de 50 L", "semibold", 56, TEXT, a2)
        a3 = ease_out((tl - 1.5) / 0.5)
        self.text_c(d, (W // 2, 1145 + (1 - a3) * 30), "selon la station", "medium", 50, MUTED, a3)
        self._caption(img, sc, tl)

    def _scene_top3(self, img, tl, dur, sc):
        d = ImageDraw.Draw(img)
        S = self.sprites
        a = ease_out(tl / 0.4)
        self.text_c(d, (W // 2, 340 + (1 - a) * 30), "Les 3 moins chères aujourd'hui", "semibold", 56, TEXT, a)
        for i, cd in enumerate(S["cards"]):
            t0 = 0.3 + i * 0.75
            p = ease_out((tl - t0) / 0.55)
            y = 440 + i * 268
            x = (W - cd.width) // 2 + (1 - p) * 180
            paste(img, cd, x, y, p)
        a4 = ease_out((tl - 2.7) / 0.5)
        self.text_c(d, (W // 2, 1262), "Prix officiels · mis à jour aujourd'hui", "medium", 36, MUTED, a4)
        self._caption(img, sc, tl, y=1340)

    def _scene_eco(self, img, tl, dur, sc):
        d = ImageDraw.Draw(img)
        S = self.sprites
        k = ease_out((tl - 0.2) / 1.2)
        value = self.info["eco_plein"] * k
        size = int(230 * (0.92 + 0.08 * ease_back((tl - 0.1) / 0.7)))
        self.text_c(d, (W // 2, 720), "−" + fr_eur(value) + " €", "bold", size, GOOD, ease_out((tl - 0.1) / 0.3))
        a = ease_out((tl - 0.9) / 0.5)
        self.text_c(d, (W // 2, 930 + (1 - a) * 28), "d'économie sur un plein de 50 L", "semibold", 52, TEXT, a)
        a1 = ease_out((tl - 1.4) / 0.5)
        a2 = ease_out((tl - 1.9) / 0.5)
        paste(img, S["row_moy"], (W - 920) // 2, 1030 + (1 - a1) * 40, a1)
        paste(img, S["row_min"], (W - 920) // 2, 1160 + (1 - a2) * 40, a2)
        self._caption(img, sc, tl, y=1340)

    def _scene_cta(self, img, tl, dur, sc):
        d = ImageDraw.Draw(img)
        S = self.sprites
        a = ease_out(tl / 0.5)
        pulse = 1 + 0.025 * math.sin(tl * 3.2)
        if "icon" in S:
            ic = S["icon"]
            s = pulse * (0.7 + 0.3 * ease_back(tl / 0.7))
            size = max(1, int(300 * s))
            icr = ic.resize((size, size), Image.LANCZOS)
            paste(img, icr, (W - size) // 2, 520 - (size - 300) // 2, a)
        self.text_c(d, (W // 2, 880), "CarburantRadar", "bold", 92, TEXT, ease_out((tl - 0.3) / 0.4))
        self.text_c(d, (W // 2, 985), "Les prix du carburant près de chez toi", "medium", 42, MUTED, ease_out((tl - 0.6) / 0.4))
        b = S["button"]
        bp = ease_out((tl - 0.8) / 0.5)
        sc_b = (1 + 0.03 * math.sin(tl * 4.0)) * (0.85 + 0.15 * bp)
        bw, bh = int(b.width * sc_b), int(b.height * sc_b)
        br = b.resize((bw, bh), Image.LANCZOS)
        paste(img, br, (W - bw) // 2, 1090 - (bh - b.height) // 2, bp)
        self.text_c(d, (W // 2, 1290), "Gratuit · Sans compte · Prix officiels", "medium", 40, MUTED, ease_out((tl - 1.3) / 0.4))
        self._caption(img, sc, tl, y=1400)

    # ---------- image complète ----------

    def frame(self, t):
        bg = self.base.copy()
        self._draw_glow(bg, t)
        d = ImageDraw.Draw(bg)
        prog = clamp(t / self.total)
        d.rounded_rectangle((70, 262, 70 + 940, 268), radius=3, fill=BORDER)
        if prog > 0.005:
            d.rounded_rectangle((70, 262, 70 + int(940 * prog), 268), radius=3, fill=ACCENT)

        sc = self.scenes[-1]
        for s in self.scenes:
            if s["start"] <= t < s["start"] + s["dur"]:
                sc = s
                break
        tl = t - sc["start"]
        layer = bg.copy()
        getattr(self, "_scene_" + sc["id"])(layer, tl, sc["dur"], sc)
        last = sc is self.scenes[-1]
        a_in = ease_in_out(tl / 0.3)
        a_out = 1.0 if last else ease_in_out((sc["dur"] - tl) / 0.3)
        a = min(a_in, a_out)
        if a < 0.995:
            layer = Image.blend(bg, layer, a)
        return layer

    def save_png(self, t, path):
        self.frame(t).save(path)

    def encode(self, audio_wav, out_path, log=print):
        n = int(round(self.total * FPS))
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-i", audio_wav,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-t", f"{self.total:.3f}", "-movflags", "+faststart", out_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(n):
                proc.stdin.write(self.frame(i / FPS).tobytes())
                if i % 150 == 0:
                    log(f"  image {i}/{n}")
            proc.stdin.close()
        except BrokenPipeError:
            pass
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg a échoué (code {code})")
