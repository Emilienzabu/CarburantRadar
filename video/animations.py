"""Animations transparentes composables pour les vidéos verticales."""
from math import hypot

from PIL import Image, ImageDraw

ORANGE = "#f5a623"
NOIR = "#181613"


def progression(t, debut, duree):
    x = max(0, min(1, (t - debut) / duree))
    return x * x * (3 - 2 * x)


def tracer(calque, points, p, couleur=ORANGE, largeur=12):
    """Révèle une polyligne à vitesse constante le long de sa longueur."""
    if p <= 0 or len(points) < 2:
        return
    segments = [hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])]
    reste = sum(segments) * min(p, 1)
    visibles = [points[0]]
    for a, b, longueur in zip(points, points[1:], segments):
        if not longueur:
            continue
        if reste < longueur:
            f = reste / longueur
            visibles.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            break
        visibles.append(b)
        reste -= longueur
    d = ImageDraw.Draw(calque)
    d.line(visibles, fill=couleur, width=largeur, joint="curve")
    r = largeur / 2
    for x, y in (visibles[0], visibles[-1]):
        d.ellipse((x-r, y-r, x+r, y+r), fill=couleur)


def epingle(calque, xy, p, taille=42):
    if p <= 0:
        return
    x, y = xy
    r = taille * p
    d = ImageDraw.Draw(calque)
    d.polygon([(x-r*.82, y-r*1.65), (x+r*.82, y-r*1.65), (x, y)], fill=ORANGE)
    d.ellipse((x-r, y-3*r, x+r, y-r), fill=ORANGE)
    d.ellipse((x-r*.32, y-2.32*r, x+r*.32, y-1.68*r), fill=NOIR)


def tap(calque, xy, p):
    if not 0 < p < 1:
        return
    x, y = xy
    r = 18 + 62 * p
    alpha = round(255 * (1-p))
    d = ImageDraw.Draw(calque)
    d.ellipse((x-r, y-r, x+r, y+r), outline=(245, 166, 35, alpha), width=7)
    d.ellipse((x-8, y-8, x+8, y+8), fill=(245, 166, 35, alpha))


def surligner(calque, boite, p):
    if p > 0:
        ImageDraw.Draw(calque).rounded_rectangle(
            boite, radius=18, outline=(245, 166, 35, round(255 * min(p, 1))), width=6,
        )


def zone(calque, xy, rayon, p):
    if p > 0:
        x, y = xy
        r = rayon * p
        ImageDraw.Draw(calque).ellipse(
            (x-r, y-r, x+r, y+r), fill=(245, 166, 35, 38), outline=ORANGE, width=5,
        )


def reveler(calque, xy, texte, police, p, couleur=NOIR):
    if p > 0:
        x, y = xy
        rgb = tuple(bytes.fromhex(couleur.lstrip("#")))
        ImageDraw.Draw(calque).text(
            (x, y + 28 * (1-p)), texte, font=police,
            fill=(*rgb, round(255 * min(p, 1))), anchor="lt",
        )


def nouveau_calque(image):
    return Image.new("RGBA", image.size)
