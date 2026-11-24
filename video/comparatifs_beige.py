"""Rend un comparatif beige à partir des prix communaux archivés."""
import argparse
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import animations as an
import audio
from comparaisons import comparer
from metadonnees_video import ecrire_fiche
from pilotes_beige import GRIS, ORANGE_TEXTE, RenduBeige
from vitrine import attacher_mots

CARBURANTS = {
    "gazole": ("Gazole", "gazole"), "e10": ("SP95-E10", "sans plomb E dix"),
    "sp98": ("SP98", "sans plomb quatre-vingt-dix-huit"), "sp95": ("SP95", "sans plomb quatre-vingt-quinze"),
    "e85": ("E85", "éthanol E quatre-vingt-cinq"), "gplc": ("GPLc", "G P L"),
}


def nom(slug):
    return slug.replace("-", " ").capitalize()


def affichage_date(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


class Comparatif(RenduBeige):
    def __init__(self, donnees, scenes, fonts):
        super().__init__(scenes, fonts)
        self.donnees = donnees

    def prix(self, img, d, a, t):
        gauche, droite = self.donnees["valeurs"]
        historique = gauche["ville"] == droite["ville"]
        titre = nom(gauche["ville"]) if historique else "Deux villes"
        taille = 106
        while self.fonts.get("bold", taille).getlength(titre) > 900:
            taille -= 4
        self.texte(d, 88, 288, titre, taille)
        self.texte(d, 88, 413, "Avant / maintenant" if historique else "Même carburant", 90, ORANGE_TEXTE)
        label = CARBURANTS[self.donnees["carburant"]][0]
        indicateur = "Prix minimum" if self.donnees["indicateur"] == "minimum" else "Prix moyen"
        self.texte(d, 92, 562, f"{label}  ·  {indicateur}", 53, GRIS)
        for i, ligne in enumerate((gauche, droite)):
            y = 680 + i * 320
            self.panneau(d, (88, y, 992, y+280))
            self.texte(d, 128, y+42, nom(ligne["ville"]), 55)
            self.texte(d, 128, y+115, affichage_date(ligne["date"]), 41, GRIS)
            self.texte(d, 128, y+183, f"{ligne['stations']} stations", 37, GRIS)
            prix = f"{ligne['prix']:.3f}".replace(".", ",") + " €/L"
            an.reveler(a, (510, y+109), prix, self.fonts.get("bold", 83),
                       an.progression(t, 1.2 + i * .9, .55), ORANGE_TEXTE)
        ecart = abs(self.donnees["ecart"]) * 100
        texte = "Même prix" if not ecart else f"{ecart:.1f}".replace(".", ",") + " c€/L d’écart"
        an.reveler(a, (90, 1398), texte, self.fonts.get("bold", 84), an.progression(t, 4, .55))
        self.texte(d, 92, 1508, "Relevés communaux • CarburantRadar", 39, GRIS)


def scenes_comparaison(donnees):
    a, b = donnees["valeurs"]
    libelle = CARBURANTS[donnees["carburant"]][1]
    comparaison = f"à {nom(a['ville'])}, à deux dates" if a["ville"] == b["ville"] else (
        f"à {nom(a['ville'])} et à {nom(b['ville'])}, le même jour")
    return [dict(id="prix", min=9.0,
                 texte=f"Voici le prix {donnees['indicateur']} du {libelle} {comparaison}. Regarde la différence au litre.")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historique", type=Path, default=Path("france/prix-carburant/history.json"))
    parser.add_argument("--gauche", nargs=2, metavar=("VILLE", "DATE"), required=True)
    parser.add_argument("--droite", nargs=2, metavar=("VILLE", "DATE"), required=True)
    parser.add_argument("--carburant", choices=CARBURANTS, required=True)
    parser.add_argument("--indicateur", choices=("minimum", "moyenne"), default="minimum")
    parser.add_argument("--voix-locale", action="store_true")
    parser.add_argument("--sortie", type=Path, required=True)
    args = parser.parse_args()
    historique = json.loads(args.historique.read_text(encoding="utf-8"))
    try:
        donnees = comparer(historique, args.carburant, args.gauche, args.droite, args.indicateur)
    except ValueError as e:
        parser.error(str(e))
    defs = scenes_comparaison(donnees)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        clips, mots = audio.synth_clips_mots(defs, tmp, moteur="espeak" if args.voix_locale else "edge")
        if any(c is None for c in clips):
            raise SystemExit("Voix indisponible.")
        scenes = audio.planifier(defs, clips, debut=.2, fin=1.5)
        attacher_mots(scenes, defs, mots)
        wav = str(Path(tmp) / "mix.wav")
        audio.ecrire_wav(wav, audio.mixer(scenes, clips, seed=3))
        rendu = Comparatif(donnees, scenes, Path(__file__).parent / "fonts")
        rendu.encode(wav, str(args.sortie))
        ecrire_fiche(args.sortie, **donnees, identite_visuelle="beige-v1", musique=3,
                      voix="espeak-ng" if args.voix_locale else audio.VOIX_DEFAUT)


if __name__ == "__main__":
    main()
