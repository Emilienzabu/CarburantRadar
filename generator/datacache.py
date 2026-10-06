"""Cache du dernier jeu de données valide d'une source souvent indisponible (API espagnole).

Le fichier (JSON compressé) est écrit dans le site publié. Au run suivant, si la source ne répond pas, on le retélécharge
depuis le site en ligne (comme les pages de la veille) et on régénère les pages avec le code à jour, au lieu de réutiliser
des pages qui n'ont pas les nouvelles sections. Il n'est jamais commité : seul le déploiement le conserve, donc il doit être
réécrit à CHAQUE run (jeu frais, ou copie du précédent). Aucune donnée n'est inventée : les dates affichées restent celles
du jeu d'origine.
"""
import gzip
import json
import os
import time
import urllib.request

from render_common import SITE_URL


def write_bytes(root, rel, data):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def save(root, rel, raw):
    """Écrit le jeu brut (déterministe : mtime fixe). Renvoie la taille en octets."""
    data = gzip.compress(json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9, mtime=0)
    write_bytes(root, rel, data)
    return len(data)


def download(rel, tries=3):
    """Octets du cache publié (le site en ligne est encore celui de la veille pendant le build)."""
    url = f"{SITE_URL}/{rel}"
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CarburantRadar-SEO-generator/2.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            decode(data)   # vérifie que c'est bien un gzip JSON complet avant de s'en servir
            return data
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url} : {last}")


def decode(data):
    return json.loads(gzip.decompress(data).decode("utf-8"))
