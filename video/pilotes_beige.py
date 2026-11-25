"""Génère les pilotes éditoriaux à partir des captures mobiles de CarburantRadar."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

import animations as an
import audio
from metadonnees_video import ecrire_fiche
from performance import PLATEFORMES, choisir_musique, experience_musique
from planning_editorial import SCENARIOS_APP
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
    "analyse": (
        ("courbe", 3.9, "Le prix près de chez toi monte ou baisse ?"),
        ("periode", 4.7, "Dans Analyse, ouvre la moyenne de ta zone et choisis une période."),
        ("graphique", 5.1, "La courbe te montre comment le prix a évolué sur cette période."),
    ),
    "carte": (
        ("prix_sur_carte", 3.9, "Où sont les stations autour de toi, et à quel prix ?"),
        ("ouvrir_carte", 4.7, "Appuie sur Carte, en bas à gauche."),
        ("stations_sur_carte", 5.1, "Les prix apparaissent directement à l’emplacement des stations."),
    ),
}
MUSIQUES = {"detour": (3, 8), "rayon": (8, 3), "analyse": (8, 3), "carte": (3, 8)}


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
        self.afficher_scene(scene, img, d, calque, u)
        img.paste(calque, mask=calque.getchannel("A"))
        mots = scene.get("mots", [])
        for i in range(0, len(mots), 4):
            groupe = mots[i:i+4]
            if groupe[0][1] <= t <= groupe[-1][2]:
                self.texte(d, 90, 1650, " ".join(mot for mot, _, _ in groupe), 47)
                break
        return img

    def afficher_scene(self, scene, img, d, calque, t):
        getattr(self, scene["id"])(img, d, calque, t)


class Pilote(RenduBeige):
    def __init__(self, nom, scenes, captures, fonts):
        super().__init__(scenes, fonts)
        self.nom = nom
        if nom == "rayon":
            self.radar = self.extrait(captures / "ecran_radar.png", (.035, .269, .965, .425), 890)
        elif nom == "detour":
            self.trajet = self.extrait(captures / "ecran_trajet.png", (.055, .42, .945, .89), 856)
        elif nom == "analyse":
            analyse = captures / "ecran_analyse.png"
            self.selecteur = self.extrait(analyse, (.085, .20, .915, .34), 884)
            self.resultat = self.extrait(analyse, (.112, .48, .888, .89), 814)
        elif nom == "carte":
            carte = captures / "ecran_carte.png"
            self.navigation = self.extrait(carte, (.026, .907, .974, .986), 884)
            # La zone affichée conserve les crédits cartographiques en bas à droite.
            self.stations = self.extrait(carte, (0, .282, 1, .872), 806)

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

    def courbe(self, img, d, a, t):
        self.titre(d, "Le prix", "monte ou baisse ?")
        self.panneau(d, (88, 650, 992, 1330))
        for y in (820, 975, 1130):
            d.line((160, y, 920, y), fill="#e5dbca", width=4)
        an.tracer(a, [(169, 1115), (293, 1010), (412, 1090), (518, 904),
                      (638, 970), (751, 840), (913, 881)], an.progression(t, .2, 1.57), largeur=15)
        self.texte(d, 156, 1205, "Exemple d’évolution", 48, GRIS)

    def periode(self, img, d, a, t):
        self.titre(d, "Dans Analyse", "choisis la période")
        self.capture(img, self.selecteur, (98, 720))
        cx, cy = 638, 908
        an.surligner(a, (cx-96, cy-40, cx+96, cy+40), an.progression(t, .95, .4))
        an.tap(a, (cx, cy), an.progression(t, .98, .62))
        self.texte(d, 98, 1130, "Moyenne des prix de ta zone", 54, GRIS)

    def graphique(self, img, d, a, t):
        self.titre(d, "Lis la courbe", "des prix")
        self.capture(img, self.resultat, (133, 565))
        an.surligner(a, (150, 780, 930, 1435), an.progression(t, .7, .45))
        self.texte(d, 133, 1490, "Capture de CarburantRadar", 39, GRIS)

    def prix_sur_carte(self, img, d, a, t):
        self.titre(d, "Les prix", "près de toi")
        self.panneau(d, (88, 650, 992, 1330))
        an.tracer(a, [(158, 1110), (333, 972), (599, 1090), (915, 886)],
                  an.progression(t, .1, 1.3), "#d8ccba", 24)
        an.tracer(a, [(215, 808), (455, 1063), (733, 933), (858, 1180)],
                  an.progression(t, .25, 1.5), "#d8ccba", 24)
        for i, position in enumerate(((321, 1011), (592, 1100), (821, 975))):
            an.epingle(a, position, an.progression(t, .46 + .25*i, .4), 35)
        self.texte(d, 152, 1218, "Une station, un prix", 51, GRIS)

    def ouvrir_carte(self, img, d, a, t):
        self.titre(d, "Appuie", "sur Carte")
        self.capture(img, self.navigation, (98, 750))
        an.surligner(a, (119, 768, 333, 883), an.progression(t, .75, .42))
        an.tap(a, (229, 825), an.progression(t, .86, .65))
        self.texte(d, 98, 1010, "En bas à gauche", 58, GRIS)

    def stations_sur_carte(self, img, d, a, t):
        self.texte(d, 88, 288, "Prix par station", 91)
        self.capture(img, self.stations, (137, 465))
        self.texte(d, 137, 1475, "Capture de CarburantRadar", 39, GRIS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--captures-mobiles", type=Path, required=True)
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--voix-locale", action="store_true", help="Voix de test eSpeak NG")
    parser.add_argument("--decisions", type=Path, help="Rapport calculé par performance.py")
    parser.add_argument("--plateformes-apprentissage", nargs="+", choices=sorted(PLATEFORMES),
                        help="Destinations à prendre en compte, YouTube et Instagram par défaut")
    parser.add_argument("--id-video", help="Identifiant stable de la vidéo pour l'attribution")
    parser.add_argument("--paire-musique", help="Identifiant d'une paire prévue avant publication")
    parser.add_argument("--ordre", type=int, choices=(1, 2))
    args = parser.parse_args()
    if bool(args.paire_musique) != bool(args.ordre) or (args.decisions and args.paire_musique):
        parser.error("Une expérience exige une paire et un ordre et s'utilise seule.")
    if args.plateformes_apprentissage and not args.decisions:
        parser.error("--plateformes-apprentissage exige --decisions")
    if args.decisions and not args.id_video:
        parser.error("--decisions exige --id-video")
    temoin, variante = MUSIQUES[args.scenario]
    musique, experience = temoin, None
    if args.paire_musique:
        experience = experience_musique(args.scenario, temoin, variante, args.paire_musique, args.ordre)
        musique = variante if experience["bras"] == "variante" else temoin
    if args.decisions:
        resultats = json.loads(args.decisions.read_text(encoding="utf-8"))["experiences"]
        plateformes = {"plateformes": args.plateformes_apprentissage} if args.plateformes_apprentissage else {}
        musique = choisir_musique((variante,), temoin, resultats, args.id_video, args.scenario, **plateformes)
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
        ecrire_fiche(args.sortie, id_video=args.id_video, scenario=args.scenario,
                     categorie=SCENARIOS_APP[args.scenario][0],
                     identite_visuelle="beige-v1", musique=musique,
                     voix="espeak-ng" if args.voix_locale else audio.VOIX_DEFAUT, experience=experience)


if __name__ == "__main__":
    main()
