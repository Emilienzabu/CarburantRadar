"""Resolve any French commune through the official French administrative geo API.
No fixed city list. Ambiguous names require an INSEE code. Fail closed on errors.
"""
import json
import math
import re
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import urlopen

API = 'https://geo.api.gouv.fr/communes'

@dataclass(frozen=True)
class Commune:
    nom: str
    code: str
    latitude: float
    longitude: float


def parse_communes(payload, city, insee=None):
    if not isinstance(payload, list):
        raise ValueError('Réponse géographique invalide')
    name = city.strip().casefold()
    matches = [v for v in payload if isinstance(v, dict) and
               isinstance(v.get('nom'), str) and v['nom'].strip().casefold() == name]
    if insee:
        matches = [v for v in matches if v.get('code') == insee]
    if not matches:
        raise ValueError(f'Commune introuvable : {city!r}')
    if len(matches) != 1:
        codes = ', '.join(str(v.get('code', '?')) for v in matches)
        raise ValueError(f'Commune ambiguë ({codes}) : préciser --insee')
    v = matches[0]
    coordinates = (v.get('centre') or {}).get('coordinates')
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        raise ValueError('Coordonnées officielles manquantes')
    lon, lat = coordinates
    if not all(isinstance(x, (float, int)) and math.isfinite(x) for x in (lat, lon)):
        raise ValueError('Coordonnées non valides')
    if not (41 <= lat <= 52 and -6 <= lon <= 10):
        raise ValueError('Coordonnées hors France métropolitaine : scénario à adapter')
    code = v.get('code')
    if not isinstance(code, str) or not re.fullmatch(r'[0-9AB]{5}', code):
        raise ValueError('Code INSEE invalide')
    return Commune(v['nom'], code, lat, lon)


def resolve(city, insee=None, opener=urlopen):
    if not isinstance(city, str) or not (1 <= len(city.strip()) <= 100):
        raise ValueError('Nom de ville invalide')
    if insee is not None and not re.fullmatch(r'[0-9AB]{5}', insee):
        raise ValueError('Code INSEE invalide')
    params = urlencode({'nom': city.strip(), 'fields': 'nom,code,centre', 'format': 'json', 'geometry': 'centre'})
    with opener(API + '?' + params, timeout=12) as response:
        data = json.load(response)
    return parse_communes(data, city, insee)
