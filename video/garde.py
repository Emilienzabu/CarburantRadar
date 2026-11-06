"""Garde temporaire de publication (2026-11) et rotation des conseils.

Diagnostic E0 du 2026-11-05 : le filtre `geofilter.distance` de l'API des prix est ignoré (même échantillon national
pour toutes les villes). Tant que la récupération géographique n'est pas corrigée, toute PUBLICATION se limite au
format « astuce » (aucun chiffre géographique). La génération SANS publication reste libre (tous les formats).

Désactivation explicite, une fois la source corrigée et validée : variable d'environnement VIDEO_GARDE_ASTUCE=0.
"""
import os
import random


def garde_astuce_active(env=None):
    env = os.environ if env is None else env
    return str(env.get("VIDEO_GARDE_ASTUCE", "1")).strip().lower() not in ("0", "false", "non", "off")


def appliquer_garde_astuce(args, journal=None):
    """Si on publie : impose le format astuce (et ignore ville/carburant). Renvoie True si les arguments ont changé."""
    if not args.publier or not garde_astuce_active():
        return False
    change = args.format != "astuce" or bool(args.ville) or bool(args.carburant)
    if change and journal:
        journal(f"GARDE ASTUCE : publication demandée avec format={args.format or 'planning'}, ville={args.ville}, "
                f"carburant={args.carburant} -> format astuce imposé (données géographiques non fiables).")
    args.format, args.ville, args.carburant = "astuce", None, None
    return change


def _ordre_astuces(cycle, n):
    """Ordre des n conseils pour un cycle (identique à donnees.pioche() quand tous les poids valent 1)."""
    ordre = list(range(n))
    random.Random(f"astuce-{cycle}").shuffle(ordre)
    return ordre


def indice_astuce(k, n):
    """Conseil de la k-ième publication : chaque conseil une fois par cycle de n publications, et jamais le même
    conseil deux publications de suite (la frontière entre deux cycles est corrigée par un échange)."""
    cycle, idx = divmod(k, n)
    ordre = _ordre_astuces(cycle, n)
    if cycle > 0 and n > 2 and ordre[0] == _ordre_astuces(cycle - 1, n)[-1]:
        ordre[0], ordre[1] = ordre[1], ordre[0]
    return ordre[idx]


def plan_astuce(k, astuces):
    return {"format": "astuce", "astuce": astuces[indice_astuce(k, len(astuces))]}
