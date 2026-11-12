"""Fail-closed geographic audit of actual application state; no network calls."""
import math

EARTH_KM = 6371.0088

def distance_km(a_lat, a_lon, b_lat, b_lon):
    vals = [a_lat, a_lon, b_lat, b_lon]
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in vals):
        raise ValueError('Coordonnées invalides')
    if not (-90 <= a_lat <= 90 and -90 <= b_lat <= 90 and -180 <= a_lon <= 180 and -180 <= b_lon <= 180):
        raise ValueError('Coordonnées hors limites')
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2-p1, math.radians(b_lon-a_lon)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return EARTH_KM * 2 * math.asin(min(1.0, math.sqrt(max(0.0, h))))

def audit_state(state, target_lat, target_lon, fuel, max_center_error_km=0.3, tolerance_km=2.0):
    if not isinstance(state, dict): raise ValueError('Etat application manquant')
    center = distance_km(target_lat, target_lon, state.get('lat'), state.get('lon'))
    if center > max_center_error_km: raise ValueError(f'Position incorrecte : {center:.2f} km')
    if state.get('fuel') != fuel: raise ValueError('Carburant incorrect dans l’application')
    radius = state.get('radius')
    if isinstance(radius, bool) or not isinstance(radius, (int, float)) or radius not in (5,10,20,50):
        raise ValueError('Rayon de recherche non valide')
    stations = state.get('stations')
    if not isinstance(stations, list) or not stations: raise ValueError('Aucune station à auditer')
    distances = []
    for i, station in enumerate(stations):
        if not isinstance(station, dict): raise ValueError(f'Station {i} mal formée')
        try: dist = distance_km(target_lat,target_lon,station.get('lat'),station.get('lon'))
        except (ValueError, TypeError) as e: raise ValueError(f'Station {i} sans coordonnées valides') from e
        if dist > radius + tolerance_km: raise ValueError(f'Station {i} hors zone : {dist:.2f} km pour {radius} km')
        distances.append(dist)
    return {'verified':True, 'station_count_audited':len(stations), 'max_station_distance_km':round(max(distances),3), 'center_error_km':round(center,3), 'radius_km':radius, 'tolerance_km':tolerance_km}
