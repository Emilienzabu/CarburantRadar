"""Génère les vidéos verticales du planning en mode aperçu."""
import argparse
import json
from datetime import date, datetime
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import animations as an
import audio
import controle_publication as controle
from comparatifs_beige import CARBURANTS, Comparatif, scenes_comparaison
from metadonnees_video import ecrire_fiche
from performance import choisir_musique
from planning_quotidien import CRENEAUX
from pilotes_beige import GRIS, MUSIQUES, ORANGE_TEXTE, SCENARIOS, Pilote, RenduBeige
from rendu import wrap
from vitrine import attacher_mots

POLICES = Path(__file__).with_name("fonts")


class SujetBeige(RenduBeige):
    def __init__(self, fiche, carburant, scenes):
        super().__init__(scenes, POLICES)
        self.fiche = fiche
        self.carburant = carburant

    def bloc(self, d, texte, x, y, taille, largeur, couleur=an.NOIR):
        for i, ligne in enumerate(wrap(texte, self.fonts.get("bold", taille), largeur)):
            self.texte(d, x, y + i * (taille + 12), ligne, taille, couleur)

    def prix_ville(self, img, d, a, t):
        f = self.fiche
        self.bloc(d, f["commune"], 88, 288, 94, 875)
        self.texte(d, 90, 540, CARBURANTS[self.carburant][0], 56)
        self.panneau(d, (88, 650, 968, 1120))
        an.reveler(a, (142, 738), f"{f['prix_litre']:.3f}".replace(".", ",") + " €/L",
                   self.fonts.get("bold", 128), an.progression(t, .08, .38), ORANGE_TEXTE)
        self.texte(d, 145, 945, f"Minimum sur {f['stations']} stations", 45)
        self.bloc(d, "D’après les derniers prix officiels", 90, 1285, 43, 850, GRIS)

    def adresse(self, img, d, a, t):
        f = self.fiche
        self.texte(d, 88, 300, "Où faire le plein ?", 78)
        an.epingle(a, (150, 610), an.progression(t, .12, .48), 37)
        self.panneau(d, (88, 640, 968, 1200))
        self.bloc(d, f["adresse"], 139, 745, 63, 770)
        jour = datetime.fromisoformat(f["prix_releve_le"]).astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")
        self.texte(d, 141, 1070, f"Prix signalé le {jour}", 43, GRIS)
        self.texte(d, 90, 1410, "carburantradar.fr", 58, ORANGE_TEXTE)

    def accroche(self, img, d, a, t):
        self.bloc(d, self.fiche["titre"], 88, 352, 86, 855)
        an.tracer(a, [(96, 1140), (450, 1140), (765, 1140)], an.progression(t, .1, .52), largeur=12)

    def conseil(self, scene, d, a, t):
        libelle = "Erreur" if "erreurs" in self.fiche["titre"].casefold() else "Point"
        self.texte(d, 88, 305, f"{libelle} {scene['idx'] + 1}", 73, ORANGE_TEXTE)
        self.panneau(d, (88, 570, 968, 1240))
        self.bloc(d, scene["caption"], 141, 718, 68, 770)
        an.surligner(a, (92, 574, 964, 1236), an.progression(t, .15, .55))

    def afficher_scene(self, scene, img, d, calque, t):
        if scene["id"] == "conseil":
            self.conseil(scene, d, calque, t)
        else:
            super().afficher_scene(scene, img, d, calque, t)


def specifier(sujet, captures):
    categorie = sujet["categorie"]
    fiche = sujet["donnees"]
    if categorie == "ville_du_jour":
        _, voix = CARBURANTS[sujet["carburant"]]
        prix = f"{fiche['prix_litre']:.3f}".rstrip("0").replace(".", ",").rstrip(",")
        defs = [{"id": "prix_ville", "min": 5.2,
                 "texte": f"À {fiche['commune']}, {voix} à {prix} euros le litre. Voici où."},
                {"id": "adresse", "min": 7.3,
                 "texte": f"Voici l’adresse. {fiche['adresse'].split(',')[0]}."}]
        return defs, partial(SujetBeige, fiche, sujet["carburant"]), (3, 8)
    if categorie == "astuce":
        defs = [{"id": "accroche", "min": 3.2, "texte": fiche["titre"]}]
        defs += [{"id": "conseil", "min": 3.2, "idx": i, "texte": texte}
                 for i, texte in enumerate(fiche["points"])]
        return defs, partial(SujetBeige, fiche, None), (8, 3)
    if categorie in ("fonctionnement", "avantage"):
        scenario = fiche["scenario"]
        if captures is None:
            raise ValueError(f"{categorie} exige des captures mobiles")
        defs = [{"id": nom, "min": duree, "texte": texte} for nom, duree, texte in SCENARIOS[scenario]]
        return defs, lambda scenes: Pilote(scenario, scenes, captures, POLICES), MUSIQUES[scenario]
    if categorie in ("ville_avant_maintenant", "ville_contre_ville"):
        defs = scenes_comparaison(fiche)
        defs[-1]["min"] = controle.DUREE_MIN + .5
        return defs, lambda scenes: Comparatif(fiche, scenes, POLICES), (3, 8)
    raise ValueError(f"Catégorie inconnue : {categorie}")


def rendre(sujet, slot, destination, captures=None, voix_locale=False, decisions=(), experience=None):
    defs, creer_rendu, (temoin, variante) = specifier(sujet, captures)
    categorie = sujet["categorie"]
    musique = choisir_musique((variante,), temoin, decisions, slot, categorie)
    if experience:
        musique = variante if experience["bras"] == "variante" else temoin
    moteur = "espeak" if voix_locale else "edge"
    destination.parent.mkdir(parents=True, exist_ok=True)
    voix_utilisee = audio.VOIX_DEFAUT

    def journal(message):
        nonlocal voix_utilisee
        if message.startswith("Voix : "):
            voix_utilisee = message.removeprefix("Voix : ")
        print(message)

    with TemporaryDirectory() as dossier:
        clips, mots = audio.synth_clips_mots(defs, dossier, log=journal, moteur=moteur)
        if any(c is None for c in clips):
            raise RuntimeError(f"Voix indisponible pour {slot}")
        scenes = audio.planifier(defs, clips, debut=.2, fin=.65)
        attacher_mots(scenes, defs, mots)
        wav = str(Path(dossier) / "mix.wav")
        audio.ecrire_wav(wav, audio.mixer(scenes, clips, seed=musique))
        rendu = creer_rendu(scenes)
        rendu.encode(wav, str(destination))

    manifeste = destination.with_suffix(".manifeste.json")
    controle.ecrire_manifeste(manifeste, controle.construire_manifeste(
        destination, rendu.derniere_commande, slot_id=slot, format_video=categorie))
    resultat = controle.valider_avant_publication(destination, manifeste, exiger_slot=True)
    if not resultat.accepte:
        raise RuntimeError(f"{slot} : " + ", ".join(resultat.erreurs))
    ecrire_fiche(destination, id_video=slot, categorie=categorie, villes=sujet["villes"],
                  sujet=sujet["sujet"], carburant=sujet["carburant"], musique=musique,
                  voix="espeak-ng" if voix_locale else voix_utilisee, identite_visuelle="beige-v1",
                  experience=experience)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("planning", type=Path)
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--captures-mobiles", type=Path)
    parser.add_argument("--voix-locale", action="store_true")
    parser.add_argument("--decisions", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.planning.read_text(encoding="utf-8"))
    jour = date.fromisoformat(plan["jour"])
    if len(plan["sujets"]) > len(CRENEAUX):
        parser.error("Le planning comporte plus de deux sujets.")
    sujets = {s.get("creneau", c): s for c, s in zip(CRENEAUX, plan["sujets"])}
    if len(sujets) != len(plan["sujets"]) or not sujets.keys() <= set(CRENEAUX):
        parser.error("Les créneaux du planning doivent être distincts et valides.")
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))["experiences"] if args.decisions else ()
    for creneau, sujet in sujets.items():
        rendre(sujet, f"{jour}:{creneau}", args.sortie / f"{creneau}.mp4",
               args.captures_mobiles, args.voix_locale, decisions)


if __name__ == "__main__":
    main()
