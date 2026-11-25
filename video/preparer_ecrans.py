#!/usr/bin/env python3
"""Prépare les écrans du format « vitrine » à partir des 4 plans composés (captures de l'application).

Usage : python video/preparer_ecrans.py DOSSIER_DES_PLANS [DOSSIER_DE_SORTIE]
        (DOSSIER_DES_PLANS contient radar.png, trajet.png, analyse.png, carte.png en 1080x1920)

Ce que fait le script (et rien d'autre) :
  - il ne garde que l'intérieur de l'écran du téléphone, SOUS l'en-tête de l'application : l'îlot dynamique du plan
    d'origine recouvre le haut du nom « CarburantRadar » et le logo y est rogné ; l'en-tête est redessiné au rendu à
    partir de l'icône réelle de l'application (icons/icon-512.png) ;
  - il coupe au bas de la barre d'onglets : sur le plan « analyse », un fragment de nom de station favorite dépasse
    en dessous (fuite de données personnelles, à ne pas publier) ;
  - aucune valeur n'est modifiée ni redessinée, aucun agrandissement (écrans de 592 x 1132 pixels).
"""
import os
import sys

from PIL import Image

PLANS = ("radar", "trajet", "analyse", "carte")
# Mesuré sur les plans 1080x1920 fournis : écran du téléphone x 244..836 ; contenu sous l'en-tête y 592..1724.
X0, X1, Y0, Y1 = 244, 836, 592, 1724
TAILLE_PLAN = (1080, 1920)


def preparer(dossier_plans, dossier_sortie):
    os.makedirs(dossier_sortie, exist_ok=True)
    sorties = []
    for nom in PLANS:
        src = os.path.join(dossier_plans, nom + ".png")
        if not os.path.isfile(src):
            raise FileNotFoundError(f"plan manquant : {src}")
        im = Image.open(src).convert("RGB")
        if im.size != TAILLE_PLAN:
            raise ValueError(f"{src} : {im.size} au lieu de {TAILLE_PLAN} (géométrie du recadrage non valable)")
        dst = os.path.join(dossier_sortie, f"ecran_{nom}.png")
        im.crop((X0, Y0, X1, Y1)).save(dst, optimize=True)
        sorties.append(dst)
    return sorties


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sortie = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vitrine")
    for p in preparer(sys.argv[1], sortie):
        print(p, f"{os.path.getsize(p) / 1024:.0f} Ko")
