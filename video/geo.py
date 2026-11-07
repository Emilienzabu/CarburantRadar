"""Contrôles géographiques et de fraîcheur des stations (prêt à brancher, NON branché sur donnees.py).

Contexte : audit E0/E1 du 2026-11-05 (voir CarburantRadar-Workspace/audits/AUDIT_E0_E1_2026-11-05.md) : le paramètre
`geofilter.distance` est ignoré par l'API ; la méthode `within_distance` renvoie des stations réellement dans le rayon.
Décision D-014 (ACCEPTÉE) : chaque station est vérifiée géographiquement dans le rayon ; une commune affichée vient des
données de la station, jamais de la ville annoncée par défaut.

Ce module est volontairement indépendant : fonctions pures, sans réseau. Le brancher dans `recuperer_stations` est une
modification de la production qui attend la validation de la méthode par Émilien (et un essai sur l'API réelle).
"""
import datetime as dt
import math

TOLERANCE_RAYON = 1.01          # audit §7 : « rayon + 1 % »
TOLERANCE_FUTUR = dt.timedelta(hours=1)   # audit E1 : dates futures observées jusqu'à 0,41 h (décalage d'horloge)
RAYON_TERRE_KM = 6371.0088


def distance_km(lat1, lon1, lat2, lon2):
    """Distance orthodromique (Haversine) en km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RAYON_TERRE_KM * math.asin(min(1.0, math.sqrt(a)))


def extraire_coord(station):
    """(lat, lon) depuis le champ `geom` ({"lon":..,"lat":..}) ; None si absent ou invalide (fail closed)."""
    g = station.get("geom") if isinstance(station, dict) else None
    if not isinstance(g, dict):
        return None
    lat, lon = g.get("lat"), g.get("lon")
    if isinstance(lat, bool) or isinstance(lon, bool) or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return float(lat), float(lon)


def station_dans_rayon(station, ville):
    """True seulement si la station a des coordonnées valides ET se trouve dans le rayon de la ville (+1 %).

    `ville["rayon"]` est exprimé en mètres (comme dans donnees.VILLES).
    """
    c = extraire_coord(station)
    if c is None:
        return False
    return distance_km(ville["lat"], ville["lon"], c[0], c[1]) <= ville["rayon"] / 1000.0 * TOLERANCE_RAYON


def commune_affichable(station):
    """Commune propre à la station (D-014). Chaîne vide si absente : on n'invente jamais la ville annoncée."""
    v = station.get("ville") if isinstance(station, dict) else None
    return v.strip().title() if isinstance(v, str) and v.strip() else ""


def date_plausible(maj, maintenant, age_max_jours):
    """True si la date est connue, pas trop vieille, et pas plus qu'une heure dans le futur."""
    if not isinstance(maj, dt.datetime) or maj.tzinfo is None:
        return False
    if maj - maintenant > TOLERANCE_FUTUR:
        return False
    return (maintenant - maj).days <= age_max_jours


def filtrer(stations, ville):
    """Sépare (gardées, rejetées_hors_rayon_ou_sans_coordonnées). Aucun remplacement silencieux."""
    gardees, rejetees = [], []
    for s in stations:
        (gardees if station_dans_rayon(s, ville) else rejetees).append(s)
    return gardees, rejetees
