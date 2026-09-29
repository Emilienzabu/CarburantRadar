"""Helpers géographiques et de texte (sans dépendance externe)."""
import math
import re
import unicodedata


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slugify(s):
    s = strip_accents(s).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def norm_name(s):
    """Normalise un nom de commune pour comparaison (accents, casse, tirets, saint/sainte)."""
    s = strip_accents(s or "").upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s).strip()
    s = re.sub(r"\bSAINTE\b", "STE", s)
    s = re.sub(r"\bSAINT\b", "ST", s)
    return s


def same_commune(station_ville_norm, city_norm):
    """Vrai si le nom normalisé de la station correspond à la ville (arrondissements inclus)."""
    if station_ville_norm == city_norm:
        return True
    if station_ville_norm.startswith(city_norm + " "):
        rest = station_ville_norm[len(city_norm) + 1:]
        return bool(re.fullmatch(r"\d{1,2}( ?(ER|E|EME|EM))?", rest))
    return False


def haversine(lat1, lon1, lat2, lon2):
    """Distance en km à vol d'oiseau."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------- formats français ----------

def fr_price(x):
    return f"{x:.3f}".replace(".", ",")


def fr_eur(x):
    return f"{x:.2f}".replace(".", ",")


def fr_km(d):
    if d < 10:
        return f"{d:.1f}".replace(".", ",") + " km"
    return f"{d:.0f} km"


def fr_cents(x):
    """Écart en centimes par litre (x en €/L)."""
    return f"{x * 100:.1f}".replace(".", ",")


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def join_fr(items, last="et"):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {last} " + items[-1]
