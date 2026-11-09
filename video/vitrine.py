"""Format « vitrine » : l'application CarburantRadar en vrai (captures d'écran), avec voix, sous-titres mot à mot et animations.

Ce format est une DÉMONSTRATION : les valeurs affichées viennent de captures de l'application, pas du flux officiel du
jour. Il n'est JAMAIS publié automatiquement (generate_video.py le refuse) et ne passe pas par les données géographiques.

Rendu : mêmes dimensions, mêmes encodage et contrôle avant publication que les autres formats (classe Renderer héritée).
Différences voulues avec les formats existants : aucun logo fixe en haut, aucune barre de progression, aucun halo lumineux ;
le téléphone est dessiné en vectoriel (bords nets) et les écrans ne sont JAMAIS agrandis (échelle d'affichage < 1).

Écrans attendus dans video/assets/vitrine/ : ecran_radar.png, ecran_trajet.png, ecran_analyse.png, ecran_carte.png
(592 x 1132, produits par video/preparer_ecrans.py).
"""
import math
import os
import re

import numpy as np
from PIL import Image, ImageDraw

import rendu
from donnees import CTA_TEXTE, fr_eur, fr_prix3
from rendu import (ACCENT, BG_BOT, BG_TOP, BORDER, DARK, FPS, GOOD, H, MUTED, SS, SURFACE, TEXT, W, Fonts, clamp, ease_back,
                   ease_in_out, ease_out, make_sprite, paste)

ECRANS = ("radar", "trajet", "analyse", "carte")
ORANGE = (255, 112, 67)     # « prix moyen » dans l'application
VIOLET = (167, 139, 250)    # « détour » et repères de carte dans l'application

# Valeurs lues sur les captures (démonstration, pas des prix du jour). Elles servent aux bulles ; les tests les comparent
# au script pour qu'aucun chiffre ne soit inventé.
VALEURS = {"prix_min": 2.035, "prix_moy": 2.168, "economie": 4.97, "detour_min": 7, "direct_min": 14, "total_min": 21,
           "variation_pct": -6.4}

# ---------- script : texte affiché / texte prononcé ----------
# Un mot entre crochets [affiché|prononcé] est dit autrement qu'il n'est écrit.
SCENES_DEF = [
    {"id": "radar", "titre": "Compare les stations", "min": 4.4,
     "script": "Compare les stations autour de toi. Et repère les économies possibles."},
    {"id": "trajet", "titre": "Optimise ton trajet", "min": 4.8,
     "script": "Un détour peut tout changer. Compare aussi le coût du trajet."},
    {"id": "analyse", "titre": "Suis les prix", "min": 4.8,
     "script": "Retrouve l’évolution des prix sur plusieurs mois, directement dans l’application."},
    {"id": "carte", "titre": "Explore la carte", "min": 4.4,
     "script": "Carte, trajet, radar : tout est réuni sur [carburantradar.fr|Carburant Radar point F R]."},
    {"id": "cta", "titre": None, "min": 2.8, "script": ""},   # écran de fin sans voix : l'adresse vient d'être dite
]
DEBUT_SCENE, FIN_SCENE = 0.30, 0.45   # silences avant / après la voix dans chaque scène (plus serré que les autres formats)
SEED_MUSIQUE = 3                       # style « chill » de musique.py (fixe : rendu reproductible)


def analyser_script(script):
    """'Un mot [a.fr|A F R].' -> [(affiché, prononcé)] ; l'apostrophe typographique est normalisée pour la voix."""
    import audio
    bruts = []
    for m in re.finditer(r"\[([^\]|]*)\|([^\]]*)\](\S*)|\S+", script):
        if m.group(1) is not None:       # la ponctuation collée au crochet fait partie du mot (affiché et prononcé)
            bruts.append((m.group(1) + m.group(3), m.group(2) + m.group(3)))
        else:
            bruts.append((m.group(0), m.group(0)))
    parles = audio.prononcer_tokens([p for _, p in bruts])   # une entrée par mot affiché : mêmes longueurs
    return [(aff, pro.replace("’", "'")) for (aff, _), pro in zip(bruts, parles)]


def scenes_texte(info=None):
    """Même contrat que donnees.scenes_texte : liste de scènes {id, min, texte, caption, mots}."""
    scenes = []
    for sc in SCENES_DEF:
        toks = analyser_script(sc["script"])
        scenes.append({"id": sc["id"], "min": sc["min"], "texte": " ".join(p for _, p in toks), "caption": None,
                       "mots": toks, "titre": sc["titre"]})
    return scenes


def info_vitrine():
    return {"format": "vitrine", "slug": "vitrine", "hook_pill": "VITRINE", "demo": True, "valeurs": dict(VALEURS),
            "titre": "CarburantRadar en vrai : radar, trajet, analyse et carte"}


def textes_publication(info):
    """Texte de métadonnées pour le manifeste de rendu. Ce format n'est jamais publié : aucune valeur n'y figure."""
    titre = info["titre"]
    return titre[:100], titre + "\nDémonstration de l'application (valeurs de captures).", titre[:100]


def attacher_mots(scenes, scenes_def, mots_par_scene):
    """Ajoute à chaque scène planifiée la liste absolue [(mot, debut_s, fin_s)] utilisée par les sous-titres.
    Sans horodatage (voix indisponible), les mots sont répartis à parts égales dans la scène."""
    for sc, sd, mots in zip(scenes, scenes_def, mots_par_scene):
        if mots is None:
            toks = sd.get("mots") or []
            duree = max(0.1, sc["dur"] - (sc["voix_debut"] - sc["start"]) - FIN_SCENE)
            n = max(1, len(toks))
            mots = [(a, i * duree / n, (i + 1) * duree / n) for i, (a, _) in enumerate(toks)]
        sc["mots"] = [(m, sc["voix_debut"] + a, sc["voix_debut"] + b) for m, a, b in mots]


# ---------- géométrie ----------
S = 0.78                                   # échelle d'affichage des écrans (< 1 : aucun agrandissement)
EC_W, EC_H = 592, 1132                     # écran de l'application (capture recadrée)
STATUS_H, HEAD_H = 48, 100                 # zone de l'îlot + en-tête redessiné
TETE = STATUS_H + HEAD_H
SCR_W, SCR_H = EC_W, TETE + EC_H
DISP_W, DISP_H = round(SCR_W * S), round(SCR_H * S)
BEZEL = 14
BODY_W, BODY_H = DISP_W + 2 * BEZEL, DISP_H + 2 * BEZEL
PX, PY = (W - BODY_W) // 2, 322
TR = 0.5                                   # durée d'une transition entre écrans (centrée sur le début de la scène)

# zones utiles dans la capture recadrée (x0, y0, x1, y1), mesurées sur les écrans fournis
CIBLES = {
    "radar_min": (213, 90, 376, 228), "radar_moy": (393, 90, 556, 228), "radar_eco": (65, 775, 527, 881),
    "trajet_detour": (224, 614, 370, 690), "trajet_total": (396, 614, 530, 690),
    "analyse_variation": (222, 380, 372, 488), "analyse_prix": (60, 380, 208, 488),
    "analyse_graphique": (70, 522, 528, 964),
    "carte_pins": (400, 740, 600, 830),
}
PANNEAU = (220, 585, 640, 330)             # carte « trajet » : x, y, largeur, hauteur (en pixels de la vidéo)
SOUS_TITRES_Y = 1478
DISCLAIMER = "Valeurs de démonstration issues de captures de l’application"


def _lisse(pts, n=60):
    """Courbe de Bézier cubique passant par une suite de points [P0, c1, c2, P1, c3, c4, P2...] -> liste de points."""
    out = []
    for i in range(0, len(pts) - 3, 3):
        p0, c1, c2, p1 = [np.array(p, dtype=float) for p in pts[i:i + 4]]
        for k in range(n + 1):
            u = k / n
            out.append(tuple((1 - u) ** 3 * p0 + 3 * (1 - u) ** 2 * u * c1 + 3 * (1 - u) * u ** 2 * c2 + u ** 3 * p1))
    return out


def _longueurs(pts):
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    return cum


def _point_a(pts, cum, frac):
    cible = cum[-1] * clamp(frac)
    for i in range(1, len(cum)):
        if cum[i] >= cible:
            seg = max(1e-9, cum[i] - cum[i - 1])
            u = (cible - cum[i - 1]) / seg
            return (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * u, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * u), i
    return pts[-1], len(pts) - 1


class RendererVitrine(rendu.Renderer):
    """Même interface que rendu.Renderer (frame, save_png, encode, commande_ffmpeg héritées)."""

    def __init__(self, info, scenes, fonts_dir, icon_path, assets_dir=None):
        self.info = info
        self.scenes = scenes
        self.total = scenes[-1]["start"] + scenes[-1]["dur"]
        self.F = Fonts(fonts_dir)
        self.icon = Image.open(icon_path).convert("RGBA") if icon_path and os.path.isfile(icon_path) else None
        self.assets_dir = assets_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vitrine")
        self.bg = self._fond()
        self.cache = {}
        self.crops = self._charger_ecrans()
        self.screens = {n: self._ecran(n, c) for n, c in self.crops.items()}
        self.body = self._corps()
        self.mask = make_sprite(DISP_W, DISP_H, lambda d, s: d.rounded_rectangle(
            (0, 0, DISP_W * s - 1, DISP_H * s - 1), radius=62 * s, fill=(255, 255, 255, 255))).getchannel("A")
        self.island = make_sprite(112, 32, lambda d, s: d.rounded_rectangle((0, 0, 112 * s - 1, 32 * s - 1), radius=16 * s, fill=(6, 6, 8, 255)))
        self._route_prep()
        self._preparer_sous_titres()
        self.idx_ecran = {sc["id"]: i for i, sc in enumerate(scenes)}

    # ---------- éléments fixes ----------

    def _fond(self):
        ys = np.linspace(0, 1, H)[:, None, None]
        top, bot = np.array(BG_TOP), np.array(BG_BOT)
        arr = (top + (bot - top) * ys).repeat(W, axis=1).astype(np.uint8)
        return Image.fromarray(arr, "RGB")

    def _charger_ecrans(self):
        manquants = [n for n in ECRANS if not os.path.isfile(os.path.join(self.assets_dir, f"ecran_{n}.png"))]
        if manquants:
            raise FileNotFoundError("écrans du format vitrine manquants dans " + self.assets_dir + " : "
                                    + ", ".join(f"ecran_{n}.png" for n in manquants)
                                    + " (à produire avec video/preparer_ecrans.py)")
        crops = {}
        for n in ECRANS:
            im = Image.open(os.path.join(self.assets_dir, f"ecran_{n}.png")).convert("RGB")
            if im.size != (EC_W, EC_H):
                raise ValueError(f"ecran_{n}.png : {im.size} au lieu de {(EC_W, EC_H)}")
            crops[n] = im
        return crops

    def _ecran(self, nom, crop):
        """Écran natif (592 x 1280) = zone îlot + en-tête redessiné (icône réelle de l'app) + capture, réduit à l'échelle S."""
        img = Image.new("RGB", (SCR_W, SCR_H), (11, 10, 15))
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, SCR_W, TETE), fill=(22, 22, 30))
        d.rectangle((0, TETE - 2, SCR_W, TETE - 1), fill=(37, 37, 53))
        if self.icon:
            ic = self.icon.resize((64, 64), Image.LANCZOS).convert("RGB")
            m = make_sprite(64, 64, lambda dd, s: dd.rounded_rectangle((0, 0, 64 * s - 1, 64 * s - 1), radius=16 * s, fill=(255, 255, 255, 255)))
            img.paste(ic, (26, STATUS_H + 18), m.getchannel("A"))
        f = self.F.get("bold", 36)
        d.text((106, STATUS_H + 34), "Carburant", font=f, fill=TEXT, anchor="lm")
        d.text((106 + f.getlength("Carburant"), STATUS_H + 34), "Radar", font=f, fill=ACCENT, anchor="lm")
        d.text((106, STATUS_H + 70), "PRIX EN TEMPS RÉEL", font=self.F.get("medium", 17), fill=MUTED, anchor="lm")
        for k in (-12, 0, 12):
            d.rectangle((522, STATUS_H + 50 + k - 1, 556, STATUS_H + 50 + k + 1), fill=TEXT)
        img.paste(crop, (0, TETE))
        return img.resize((DISP_W, DISP_H), Image.LANCZOS)

    def _corps(self):
        w, h = BODY_W, BODY_H

        def fn(d, s):
            d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=76 * s, fill=(74, 74, 88, 255))
            d.rounded_rectangle((3 * s, 3 * s, w * s - 1 - 3 * s, h * s - 1 - 3 * s), radius=73 * s, fill=(22, 22, 28, 255))
        return make_sprite(w, h, fn)

    # ---------- primitives ----------

    def _aa(self, img, x, y, w, h, fn, alpha=1.0):
        """Dessine fn(d, s) sur un calque (w x h) sur-échantillonné x3 (bords lisses) puis le colle en (x, y)."""
        layer = Image.new("RGBA", (int(w) * SS, int(h) * SS), (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer), SS)
        paste(img, layer.resize((int(w), int(h)), Image.LANCZOS), x, y, alpha)

    def _contour(self, img, rect, couleur, p, dy):
        """Cadre de mise en valeur autour d'une zone de la capture (x0, y0, x1, y1 en pixels de capture)."""
        if p <= 0.01:
            return
        x0, y0, x1, y1 = rect
        X0, Y0 = PX + BEZEL + x0 * S, PY + BEZEL + (TETE + y0) * S + dy
        w, h = (x1 - x0) * S, (y1 - y0) * S
        g = 6 + (1 - ease_back(p)) * 10
        key = ("contour", int(w + 2 * g), int(h + 2 * g), couleur)
        if key not in self.cache:
            ww, hh = int(w + 2 * g), int(h + 2 * g)
            self.cache[key] = make_sprite(ww, hh, lambda d, s: d.rounded_rectangle(
                (0, 0, ww * s - 1, hh * s - 1), radius=18 * s, outline=(*couleur, 255), width=4 * s))
        sp = self.cache[key]
        paste(img, sp, X0 - g, Y0 - g, clamp(p * 1.5))

    def _bulle(self, img, cote, y_centre, valeur, etiquette, couleur, p):
        """Bulle de valeur dans la marge (gauche ou droite du téléphone), alignée sur la zone mise en valeur."""
        if p <= 0.01:
            return
        h = 118
        w = max(262, int(max(self.F.get("bold", 50).getlength(valeur), self.F.get("medium", 25).getlength(etiquette)) + 64))
        key = ("bulle", valeur, etiquette, couleur)
        if key not in self.cache:
            def fn(d, s):
                d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=30 * s, fill=(*couleur, 255))
                d.rounded_rectangle((3 * s, 3 * s, w * s - 1 - 3 * s, h * s - 1 - 3 * s), radius=27 * s, fill=(18, 18, 27, 255))
                d.text((w * s // 2, 46 * s), valeur, font=self.F.get("bold", 50 * s), fill=(*couleur, 255), anchor="mm")
                d.text((w * s // 2, 90 * s), etiquette, font=self.F.get("medium", 25 * s), fill=(*MUTED, 255), anchor="mm")
            self.cache[key] = make_sprite(w, h, fn)
        x = 30 if cote == "g" else W - 30 - w
        e = ease_out(p)
        paste(img, self.cache[key], x + (-1 if cote == "g" else 1) * (1 - e) * 60, y_centre - h / 2, e)

    def _texte(self, img, xy, texte, poids, taille, couleur, alpha=1.0, anchor="mm"):
        ImageDraw.Draw(img).text(xy, texte, font=self.F.get(poids, taille), fill=mix_(couleur, alpha), anchor=anchor)

    # ---------- temps ----------

    def _scene_a(self, t):
        for i, s in enumerate(self.scenes):
            if s["start"] <= t < s["start"] + s["dur"]:
                return i, t - s["start"]
        return len(self.scenes) - 1, t - self.scenes[-1]["start"]

    def _cue(self, sc, mot, defaut):
        """Instant (relatif à la scène) où le mot est prononcé ; `defaut` si le mot est introuvable."""
        cle = mot.lower()
        for m, a, _ in sc.get("mots", []):
            if cle in re.sub(r"[^\w]", "", m.lower()):
                return a - sc["start"]
        return defaut

    def _dy_telephone(self, t):
        dy = (1 - ease_out(t / 0.6)) * 70
        cta = next((s for s in self.scenes if s["id"] == "cta"), None)
        if cta:
            dy += ease_in_out((t - (cta["start"] - TR / 2)) / TR) * (H - PY + 60)
        return dy

    # ---------- téléphone ----------

    def _ecrans_a(self, t, idx):
        """[(nom d'écran, décalage horizontal)] : glissement latéral net entre deux écrans, centré sur le début de scène."""
        nom = lambda i: self.scenes[i]["id"] if self.scenes[i]["id"] in self.screens else None
        for j in range(1, len(self.scenes)):
            d0 = self.scenes[j]["start"]
            if abs(t - d0) < TR / 2 and nom(j - 1) and nom(j) and nom(j - 1) != nom(j):
                p = ease_in_out((t - d0 + TR / 2) / TR)
                return [(nom(j - 1), -p * DISP_W), (nom(j), (1 - p) * DISP_W)]
        n = nom(idx) or nom(max(0, idx - 1))
        return [(n, 0)] if n else []

    def _graphique_masque(self, base, reveal):
        """Écran « analyse » avec la zone du graphique révélée de gauche à droite (valeurs réelles de la capture, rien d'ajouté)."""
        x0, y0, x1, y1 = CIBLES["analyse_graphique"]
        rx0, ry0, rx1, ry1 = [round(v * S) for v in (x0, TETE + y0, x1, TETE + y1)]
        key = "analyse_vide"
        if key not in self.cache:
            vide = base.copy()
            ImageDraw.Draw(vide).rectangle((rx0, ry0, rx1, ry1), fill=self.screens["analyse"].getpixel((rx0 + 8, ry0 + 8)))
            self.cache[key] = vide
        out = self.cache[key].copy()
        w = int((rx1 - rx0) * clamp(reveal))
        if w > 0:
            out.paste(base.crop((rx0, ry0, rx0 + w, ry1)), (rx0, ry0))
        return out

    def _telephone(self, img, t, idx, dy):
        sc = self.scenes[idx]
        couche = Image.new("RGB", (DISP_W, DISP_H), (11, 10, 15))
        for nom, off in self._ecrans_a(t, idx):
            ec = self.screens[nom]
            if nom == "analyse":
                tl = t - self.scenes[self.idx_ecran["analyse"]]["start"]
                a = self._cue(self.scenes[self.idx_ecran["analyse"]], "évolution", 0.9) - 0.1
                ec = self._graphique_masque(ec, ease_in_out((tl - a) / 1.7))
            couche.paste(ec, (int(off), 0))
        paste(img, self.body, PX, PY + dy)
        img.paste(couche, (PX + BEZEL, int(PY + BEZEL + dy)), self.mask)
        paste(img, self.island, PX + (BODY_W - 112) // 2, PY + BEZEL + 12 + dy)

    # ---------- surcouches par scène ----------

    def _ov_radar(self, img, tl, sc, dy):
        a1 = self._cue(sc, "stations", 1.0)
        a2 = a1 + 0.6
        a3 = self._cue(sc, "économies", 2.9)
        yb = PY + BEZEL + (TETE + 159) * S + dy
        p1, p2, p3 = ease_out((tl - a1) / 0.45), ease_out((tl - a2) / 0.45), ease_out((tl - a3) / 0.45)
        self._contour(img, CIBLES["radar_min"], GOOD, p1, dy)
        self._contour(img, CIBLES["radar_moy"], ORANGE, p2, dy)
        self._contour(img, CIBLES["radar_eco"], GOOD, p3, dy)
        self._bulle(img, "g", yb, fr_prix3(VALEURS["prix_min"]) + " €", "prix le plus bas", GOOD, p1)
        self._bulle(img, "d", yb, fr_prix3(VALEURS["prix_moy"]) + " €", "prix moyen", ORANGE, p2)
        k = ease_out((tl - a3) / 0.6)
        ye = PY + BEZEL + (TETE + 828) * S + dy
        self._bulle(img, "g", ye, "+" + fr_eur(VALEURS["economie"] * k) + " €", "d’économie estimée", GOOD, p3)

    def _route_prep(self):
        """Prépare la carte « trajet » : fond et tracés (vectoriels) ; les parties animées sont dessinées image par image."""
        pw, ph = PANNEAU[2], PANNEAU[3]
        A, B = (86, 248), (pw - 96, 92)
        S_ = (352, 266)
        self.r_A, self.r_B, self.r_S = A, B, S_
        self.r_direct = _lisse([A, (230, 205), (440, 60), B], 50)
        self.r_via = _lisse([A, (150, 266), (260, 282), S_, (470, 262), (570, 150), B], 50)
        self.r_cum = _longueurs(self.r_via)
        # fraction du parcours où se trouve la station
        self.r_fracS = min(range(len(self.r_via)), key=lambda i: math.dist(self.r_via[i], S_)) / (len(self.r_via) - 1)
        base = Image.new("RGBA", (pw * SS, ph * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        d.rounded_rectangle((0, 0, pw * SS - 1, ph * SS - 1), radius=34 * SS, fill=(*BORDER, 255))
        d.rounded_rectangle((3 * SS, 3 * SS, pw * SS - 1 - 3 * SS, ph * SS - 1 - 3 * SS), radius=31 * SS, fill=(17, 17, 26, 255))
        for gx in range(70, pw, 110):      # quadrillage de rues très discret
            d.line([(gx * SS, 10 * SS), (gx * SS, (ph - 10) * SS)], fill=(30, 30, 44, 255), width=2 * SS)
        for gy in range(60, ph, 80):
            d.line([(10 * SS, gy * SS), ((pw - 10) * SS, gy * SS)], fill=(30, 30, 44, 255), width=2 * SS)
        # trajet direct en pointillés
        cum = _longueurs(self.r_direct)
        pos, on = 0.0, True
        while pos < cum[-1]:
            a, _ = _point_a(self.r_direct, cum, pos / cum[-1])
            b, _ = _point_a(self.r_direct, cum, min(1.0, (pos + 16) / cum[-1]))
            if on:
                d.line([(a[0] * SS, a[1] * SS), (b[0] * SS, b[1] * SS)], fill=(*MUTED, 255), width=5 * SS)
            pos += 16 if on else 12
            on = not on
        for (x, y), nom in ((A, "Départ"), (B, "Arrivée")):
            d.ellipse(((x - 12) * SS, (y - 12) * SS, (x + 12) * SS, (y + 12) * SS), fill=(*TEXT, 255))
            d.ellipse(((x - 5) * SS, (y - 5) * SS, (x + 5) * SS, (y + 5) * SS), fill=(*DARK, 255))
            d.text((x * SS, (y + (-38 if nom == "Arrivée" else 36)) * SS), nom, font=self.F.get("medium", 24 * SS), fill=(*MUTED, 255), anchor="mm")
        self.r_base = base

    def _ov_trajet(self, img, tl, sc, dy):
        pw, ph = PANNEAU[2], PANNEAU[3]
        a0 = self._cue(sc, "détour", 0.9)
        ap = ease_out((tl - (a0 - 0.35)) / 0.45)
        if ap <= 0.01:
            return
        t0 = a0
        f1 = ease_in_out((tl - t0) / 1.7)                    # aller (départ -> arrivée par la station)
        t_ret = max(t0 + 2.0, self._cue(sc, "coût", t0 + 2.0))
        f2 = ease_in_out((tl - t_ret) / 1.4)                 # retour (arrivée -> départ)
        prog = f1 if tl < t_ret else 1 - f2
        layer = self.r_base.copy()
        d = ImageDraw.Draw(layer)
        vers = int(round(f1 * (len(self.r_via) - 1)))
        if vers >= 1:                                         # tracé de l'itinéraire, laissé en place pendant le retour
            pts = [(x * SS, y * SS) for x, y in self.r_via[: vers + 1]]
            d.line(pts, fill=(*ACCENT, 255), width=10 * SS, joint="curve")
            for p_ in (pts[0], pts[-1]):
                d.ellipse((p_[0] - 5 * SS, p_[1] - 5 * SS, p_[0] + 5 * SS, p_[1] + 5 * SS), fill=(*ACCENT, 255))
        sx, sy = self.r_S
        if f1 >= self.r_fracS - 0.02:                         # épingle station, quand le curseur y passe
            e = ease_back((f1 - self.r_fracS + 0.02) / 0.12)
            r = 24 * e
            d.ellipse(((sx - r) * SS, (sy - r) * SS, (sx + r) * SS, (sy + r) * SS), fill=(*GOOD, 255))
            d.rounded_rectangle(((sx - 8 * e) * SS, (sy - 11 * e) * SS, (sx + 5 * e) * SS, (sy + 11 * e) * SS), radius=3 * SS, fill=(*DARK, 255))
            d.rectangle(((sx - 5 * e) * SS, (sy - 8 * e) * SS, (sx + 2 * e) * SS, (sy - 2 * e) * SS), fill=(*GOOD, 255))
        # curseur
        c, _ = _point_a(self.r_via, self.r_cum, prog)
        d.ellipse(((c[0] - 17) * SS, (c[1] - 17) * SS, (c[0] + 17) * SS, (c[1] + 17) * SS), fill=(*TEXT, 255))
        d.ellipse(((c[0] - 10) * SS, (c[1] - 10) * SS, (c[0] + 10) * SS, (c[1] + 10) * SS), fill=(*ACCENT, 255))
        lay = layer.resize((pw, ph), Image.LANCZOS)
        # étiquettes de durée (texte net, dessiné après la réduction)
        dd = ImageDraw.Draw(lay)

        def etiquette(xy, texte, couleur, a):
            if a <= 0.02:
                return
            f = self.F.get("bold", 30)
            tw = f.getlength(texte) + 30
            x, y = xy
            dd.rounded_rectangle((x - tw / 2, y - 26, x + tw / 2, y + 26), radius=26, fill=(*couleur, int(255 * clamp(a))))
            dd.text((x, y - 1), texte, font=f, fill=(*DARK, int(255 * clamp(a))), anchor="mm")
        mid = self.r_direct[len(self.r_direct) // 2]
        etiquette((mid[0] + 10, mid[1] - 46), f"{VALEURS['direct_min']} min", MUTED, ease_out((tl - t0 - 0.2) / 0.4))
        etiquette((sx - 6, sy - 50), f"+{VALEURS['detour_min']} min", VIOLET, ease_out((f1 - self.r_fracS) / 0.08))
        etiquette((self.r_B[0] - 70, self.r_B[1] + 62), f"{VALEURS['total_min']} min", ACCENT, ease_out((f1 - 0.97) / 0.03))
        paste(img, lay, PANNEAU[0], PANNEAU[1] + (1 - ap) * 26, ap)
        fin = ease_out((tl - t_ret - 1.4) / 0.4)
        self._contour(img, CIBLES["trajet_detour"], VIOLET, fin, dy)
        self._contour(img, CIBLES["trajet_total"], ACCENT, fin, dy)

    def _ov_analyse(self, img, tl, sc, dy):
        a = self._cue(sc, "évolution", 0.9) - 0.1
        fin = a + 1.7
        t_val = max(fin - 0.3, min(self._cue(sc, "mois", fin), fin + 0.6))   # la valeur apparaît quand le graphique est révélé
        p = ease_out((tl - t_val) / 0.5)
        x0, y0, x1, y1 = CIBLES["analyse_graphique"]
        # trait vertical de balayage, pendant la révélation
        r = ease_in_out((tl - a) / 1.7)
        if 0.0 < r < 1.0:
            x = PX + BEZEL + (x0 + (x1 - x0) * r) * S
            ya, yb = PY + BEZEL + (TETE + y0) * S + dy, PY + BEZEL + (TETE + y1) * S + dy
            self._aa(img, x - 6, ya, 12, yb - ya, lambda d, s: d.rounded_rectangle((4 * s, 0, 8 * s, (yb - ya) * s), radius=2 * s, fill=(*ACCENT, 255)))
        self._contour(img, CIBLES["analyse_variation"], GOOD, p, dy)
        yv = PY + BEZEL + (TETE + 434) * S + dy
        k = ease_out((tl - t_val) / 0.6)
        self._bulle(img, "d", yv, "−" + f"{abs(VALEURS['variation_pct']) * k:.1f}".replace(".", ",") + " %", "sur 3 mois", GOOD, p)

    def _ov_carte(self, img, tl, sc, dy):
        a = self._cue(sc, "tout", 2.0)
        p = ease_out((tl - a) / 0.5)
        if p <= 0.01:
            return
        x0, y0, x1, y1 = CIBLES["carte_pins"]
        cx = PX + BEZEL + (x0 + x1) / 2 * S
        cy = PY + BEZEL + (TETE + (y0 + y1) / 2) * S + dy
        R = 44 * (0.7 + 0.3 * ease_back(p))
        self._aa(img, cx - 60, cy - 60, 120, 120, lambda d, s: d.ellipse(
            (60 * s - R * s, 60 * s - R * s, 60 * s + R * s, 60 * s + R * s), outline=(*VIOLET, 255), width=5 * s), clamp(p * 1.5))
        self._bulle(img, "g", cy, "Autour de toi", "les stations de ta zone", VIOLET, p)

    def _ov_cta(self, img, tl, sc, dy):
        """Écran de fin : même contenu que le CTA des autres formats (icône, nom, bouton), sans sous-titres."""
        if self.icon:
            if "icone" not in self.cache:
                big = self.icon.resize((300, 300), Image.LANCZOS)
                m = make_sprite(300, 300, lambda d, s: d.rounded_rectangle((0, 0, 300 * s - 1, 300 * s - 1), radius=72 * s, fill=(255, 255, 255, 255)))
                big.putalpha(m.getchannel("A"))
                self.cache["icone"] = big
            e = ease_out((tl - 0.1) / 0.5)
            s = 0.8 + 0.2 * ease_back((tl - 0.1) / 0.6)
            size = max(1, int(300 * s))
            paste(img, self.cache["icone"].resize((size, size), Image.LANCZOS), (W - size) // 2, 520 - (size - 300) // 2, e)
        self._texte(img, (W // 2, 880), "CarburantRadar", "bold", 92, TEXT, ease_out((tl - 0.3) / 0.4))
        self._texte(img, (W // 2, 985), "Les prix du carburant près de chez toi", "medium", 42, MUTED, ease_out((tl - 0.55) / 0.4))
        if "bouton" not in self.cache:
            self.cache["bouton"] = self.button("carburantradar.fr")
        b = self.cache["bouton"]
        bp = ease_out((tl - 0.7) / 0.5)
        sb = 0.88 + 0.12 * ease_back((tl - 0.7) / 0.6)
        bw, bh = int(b.width * sb), int(b.height * sb)
        paste(img, b.resize((bw, bh), Image.LANCZOS), (W - bw) // 2, 1090 - (bh - b.height) // 2, bp)
        self._texte(img, (W // 2, 1290), "Gratuit · Sans compte · Prix officiels", "medium", 40, MUTED, ease_out((tl - 1.1) / 0.4))

    # ---------- titres et mentions ----------

    def _titre(self, img, t):
        for i, sc in enumerate(self.scenes):
            titre = SCENES_DEF[i].get("titre") if i < len(SCENES_DEF) else None
            if not titre:
                continue
            d0, d1 = sc["start"], sc["start"] + sc["dur"]
            a_in = 1.0 if i == 0 else ease_out((t - (d0 - 0.1)) / 0.3)
            a_out = ease_out((d1 - 0.05 - t) / 0.25)
            a = min(a_in, a_out)
            if a > 0.01:
                self._texte(img, (W // 2, 238 + (1 - a_in) * 26), titre, "bold", 66, TEXT, a)

    def _mention(self, img, t):
        cta = next((s for s in self.scenes if s["id"] == "cta"), None)
        fin = cta["start"] - TR / 2 if cta else self.total
        a = ease_out((fin - t) / 0.25) * ease_out((t - 0.6) / 0.4)
        if a > 0.01:
            self._texte(img, (W // 2, PY + BODY_H + 40), DISCLAIMER, "medium", 27, MUTED, a)

    # ---------- sous-titres mot à mot ----------

    def _preparer_sous_titres(self):
        self.chunks = []
        f = self.F.get("bold", 62)
        for sc in self.scenes:
            mots = sc.get("mots") or []
            groupes, cur = [], []
            for m in mots:
                cur.append(m)
                if m[0][-1:] in ",.;:!?" or len(cur) >= 4 or sum(len(x[0]) for x in cur) >= 24:
                    groupes.append(cur)
                    cur = []
            if cur:
                groupes.append(cur)
            for g in groupes:
                larg = [f.getlength(m[0]) for m in g]
                esp = f.getlength(" ")
                total = sum(larg) + esp * (len(g) - 1)
                x, pos = (W - total) / 2, []
                for l in larg:
                    pos.append(x)
                    x += l + esp
                self.chunks.append({"mots": g, "x": pos, "t0": g[0][1] - 0.06, "t1": g[-1][2] + 0.30})
        for i, c in enumerate(self.chunks[:-1]):   # un groupe ne déborde pas sur le suivant
            c["t1"] = min(c["t1"], self.chunks[i + 1]["t0"])

    def _sous_titres(self, img, t):
        for c in self.chunks:
            if not (c["t0"] <= t < c["t1"]):
                continue
            a = ease_out((t - c["t0"]) / 0.14)
            d = ImageDraw.Draw(img, "RGBA")
            f = self.F.get("bold", 62)
            y = SOUS_TITRES_Y + (1 - a) * 14
            for (mot, a0, a1), x in zip(c["mots"], c["x"]):
                if t >= a1:
                    col = TEXT
                elif t >= a0:
                    col = ACCENT
                else:
                    col = (150, 150, 172)
                d.text((x, y), mot, font=f, fill=(*col, int(255 * a)), stroke_width=7, stroke_fill=(8, 8, 14, int(235 * a)), anchor="ls")
            return

    # ---------- image complète ----------

    def frame(self, t):
        idx, tl = self._scene_a(t)
        sc = self.scenes[idx]
        img = self.bg.copy()
        dy = self._dy_telephone(t)
        self._titre(img, t)
        if dy < H - PY:
            self._telephone(img, t, idx, dy)
        sortie = ease_out((sc["start"] + sc["dur"] - 0.05 - t) / 0.22) if sc["id"] != "cta" else 1.0
        sur = img if sortie >= 0.995 else img.copy()
        getattr(self, "_ov_" + sc["id"])(sur, tl, sc, dy)
        if sur is not img:
            img = Image.blend(img, sur, clamp(sortie))
        self._mention(img, t)
        self._sous_titres(img, t)
        return img


def mix_(couleur, alpha, base=(14, 14, 22)):
    return rendu.mix(couleur, alpha, base)
