"""Génère deux pilotes éditoriaux à partir d'un lot de captures mobiles."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

import animations as an
import audio
from controle_publication import sha256_fichier
from performance import choisir_musique, experience_musique
from rendu import Fonts, H, Renderer, W
from vitrine import attacher_mots

BEIGE = "#f8f2e6"
PAPIER = "#fffaf1"
GRIS = "#625b51"
ORANGE_TEXTE = "#a84708"

SCENARIOS = {
    "detour": (
        ("question", 3.9, "Cette station est moins chère au litre. Mais est-elle sur ta route ?"),
        ("trace", 5.0, "Sur un aller-retour, ajoute le carburant consommé pour rejoindre la station."),
        ("preuve", 5.0, "Dans Carburant Radar, compare le coût total estimé pour décider."),
    ),
    "rayon": (
        ("question", 3.6, "Tu veux chercher des stations un peu plus loin ?"),
        ("geste", 5.0, "Dans le Radar, appuie sur dix kilomètres, juste au-dessous du choix du carburant."),
        ("zone", 5.0, "La recherche couvre alors une zone plus large autour de toi."),
    ),
}
MUSIQUES = {"detour": (3, 8), "rayon": (8, 3)}


class RenduBeige(Renderer):
    def __init__(self, scenes, fonts):
        self.scenes = scenes
        self.total = scenes[-1]["start"] + scenes[-1]["dur"]
        self.fonts = Fonts(fonts)

    @staticmethod
    def extrait(path, boite, largeur):
        with Image.open(path) as capture:
            x0, y0, x1, y1 = boite
            extrait = capture.crop((round(x0*capture.width), round(y0*capture.height),
                                    round(x1*capture.width), round(y1*capture.height))).convert("RGB")
        return extrait.resize((largeur, round(extrait.height*largeur/extrait.width)), Image.Resampling.LANCZOS)

    def texte(self, d, x, y, texte, taille, couleur=an.NOIR):
        d.text((x, y), texte, fill=couleur, font=self.fonts.get("bold", taille), anchor="lt")

    def titre(self, d, a, b):
        self.texte(d, 88, 288, a, 106)
        self.texte(d, 88, 413, b, 106, ORANGE_TEXTE)

    @staticmethod
    def panneau(d, boite):
        d.rounded_rectangle(boite, radius=36, fill=PAPIER, outline="#e5dbca", width=3)

    @staticmethod
    def capture(img, extrait, xy):
        masque = Image.new("L", extrait.size)
        ImageDraw.Draw(masque).rounded_rectangle((0, 0, extrait.width-1, extrait.height-1), radius=30, fill=255)
        img.paste(extrait, xy, masque)

    def frame(self, t):
        scene = next((s for s in reversed(self.scenes) if s["start"] <= t), self.scenes[0])
        u = t - scene["start"]
        img = Image.new("RGB", (W, H), BEIGE)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((88, 170, 143, 184), radius=7, fill=an.ORANGE)
        self.texte(d, 164, 157, "CarburantRadar", 39)
        calque = an.nouveau_calque(img)
        getattr(self, scene["id"])(img, d, calque, u)
        img.paste(calque, mask=calque.getchannel("A"))
        mots = scene.get("mots", [])
        for i in range(0, len(mots), 4):
            groupe = mots[i:i+4]
            if groupe[0][1] <= t <= groupe[-1][2]:
                self.texte(d, 90, 1650, " ".join(mot for mot, _, _ in groupe), 47)
                break
        return img


class Pilote(RenduBeige):
    def __init__(self, nom, scenes, captures, fonts):
        super().__init__(scenes, fonts)
        self.nom = nom
        self.radar = self.extrait(captures / "ecran_radar.png", (.035, .269, .965, .425), 890)
        self.trajet = self.extrait(captures / "ecran_trajet.png", (.055, .42, .945, .89), 856)

    def question(self, img, d, a, t):
        if self.nom == "detour":
            self.titre(d, "Le détour", "vaut le coup ?")
            self.panneau(d, (88, 674, 992, 1330))
            self.texte(d, 148, 752, "Moins cher au litre", 57)
            self.texte(d, 148, 1172, "Plus loin pour faire le plein", 48, GRIS)
            an.tracer(a, [(180, 1030), (385, 1030), (550, 956), (755, 956), (883, 1000)],
                      an.progression(t, .2, 1.65), an.NOIR, 12)
            an.epingle(a, (780, 962), an.progression(t, 1.1, .52), 43)
        else:
            self.titre(d, "Chercher", "plus loin ?")
            for r in (120, 214, 310):
                d.ellipse((540-r, 1000-r, 540+r, 1000+r), outline="#d9cdb9", width=4)
            an.zone(a, (540, 1000), 307, an.progression(t, .16, 1.75))
            an.epingle(a, (540, 1040), an.progression(t, .35, .48), 42)
            self.texte(d, 90, 1440, "Élargis le rayon du Radar.", 58)

    def trace(self, img, d, a, t):
        self.titre(d, "Plein", "+ détour")
        self.panneau(d, (88, 660, 992, 1300))
        direct = [(178, 1095), (362, 1070), (558, 1108), (770, 1085), (902, 1095)]
        detour = [(178, 1095), (295, 1018), (407, 898), (540, 863), (662, 893), (815, 1032), (902, 1095)]
        an.tracer(a, direct, an.progression(t, .05, .72), an.NOIR, 10)
        an.tracer(a, detour, an.progression(t, .78, 1.7), an.ORANGE, 16)
        an.epingle(a, (540, 871), an.progression(t, 1.65, .55), 44)
        self.texte(d, 137, 1168, "Trajet direct", 38)
        self.texte(d, 603, 1168, "Via la station", 38, ORANGE_TEXTE)
        an.reveler(a, (92, 1430), "À comparer : le coût total", self.fonts.get("bold", 63),
                   an.progression(t, 2.45, .55))

    def preuve(self, img, d, a, t):
        self.titre(d, "Le coût", "dans l’app")
        self.capture(img, self.trajet, (112, 610))
        an.surligner(a, (188, 892, 418, 1000), an.progression(t, 1.15, .55))
        self.texte(d, 112, 610 + self.trajet.height + 23, "Exemple dans CarburantRadar", 37, GRIS)

    def geste(self, img, d, a, t):
        self.titre(d, "Dans Radar", "tape 10 km")
        y = 755
        self.capture(img, self.radar, (95, y))
        x = 95 + round(self.radar.width * .394)
        cy = y + round(self.radar.height * .60)
        an.tap(a, (x, cy), an.progression(t, 1.18, .63))
        an.surligner(a, (x-49, cy-28, x+49, cy+28), an.progression(t, 1.2, .45))
        self.texte(d, 95, 1168, "Sous le choix du carburant", 49, GRIS)

    def zone(self, img, d, a, t):
        self.titre(d, "Un rayon", "plus large")
        d.ellipse((390, 847, 690, 1147), outline="#b6a897", width=5)
        an.zone(a, (540, 997), 310, an.progression(t, .4, 1.45))
        an.epingle(a, (540, 1035), an.progression(t, .28, .5), 43)
        an.reveler(a, (92, 1395), "5 km → 10 km", self.fonts.get("bold", 94),
                   an.progression(t, 1.45, .45))
        self.texte(d, 95, 1525, "Zone de recherche illustrée", 42, GRIS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--captures-mobiles", type=Path, required=True)
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--voix-locale", action="store_true", help="Voix de test eSpeak NG")
    parser.add_argument("--decisions", type=Path, help="Rapport calculé par performance.py")
    parser.add_argument("--id-video", help="Identifiant stable de la vidéo pour l'attribution")
    parser.add_argument("--paire-musique", help="Identifiant d'une paire prévue avant publication")
    parser.add_argument("--ordre", type=int, choices=(1, 2))
    args = parser.parse_args()
    if bool(args.paire_musique) != bool(args.ordre) or (args.decisions and args.paire_musique):
        parser.error("Une expérience exige une paire et un ordre et s'utilise seule.")
    if args.decisions and not args.id_video:
        parser.error("--decisions exige --id-video")
    temoin, variante = MUSIQUES[args.scenario]
    musique, experience = temoin, None
    if args.paire_musique:
        experience = experience_musique(args.scenario, temoin, variante, args.paire_musique, args.ordre)
        musique = variante if experience["bras"] == "variante" else temoin
    if args.decisions:
        resultats = json.loads(args.decisions.read_text(encoding="utf-8"))["experiences"]
        musique = choisir_musique((variante,), temoin, resultats, args.id_video, args.scenario)
    defs = [{"id": nom, "min": duree, "texte": texte} for nom, duree, texte in SCENARIOS[args.scenario]]
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        captures = args.captures_mobiles
        clips, mots = audio.synth_clips_mots(defs, tmp, moteur="espeak" if args.voix_locale else "edge")
        if any(clip is None for clip in clips):
            raise SystemExit("Voix indisponible, aperçu interrompu.")
        scenes = audio.planifier(defs, clips, debut=.2, fin=.65)
        attacher_mots(scenes, defs, mots)
        wav = str(Path(tmp) / "mix.wav")
        audio.ecrire_wav(wav, audio.mixer(scenes, clips, seed=musique))
        rendu = Pilote(args.scenario, scenes, captures, Path(__file__).parent / "fonts")
        rendu.encode(wav, str(args.sortie))
        fiche = dict(id_video=args.id_video, scenario=args.scenario,
                     categorie="avantage" if args.scenario == "detour" else "fonctionnement",
                     identite_visuelle="beige-v1", musique=musique, duree_s=rendu.total,
                     voix="espeak-ng" if args.voix_locale else audio.VOIX_DEFAUT,
                     experience=experience, sha256=sha256_fichier(args.sortie))
        args.sortie.with_suffix(".creation.json").write_text(json.dumps(fiche, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
