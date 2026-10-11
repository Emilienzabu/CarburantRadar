"""IndexNow : signale chaque jour à Bing (et Yandex, Naver, Seznam, Yep) les URLs du sitemap, sans attendre leur exploration.

Protocole : https://www.indexnow.org/documentation. La clé est publique par conception : elle doit être servie par le site
(fichier <clé>.txt à la racine de /CarburantRadar/, qui borne aussi les URLs acceptables). Un échec réseau ou une réponse d'erreur
ne fait jamais échouer le build : le résultat est simplement consigné dans SEO_REPORT.md.
"""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from render_common import SITE_URL

KEY = "83fdcccdbae67706dc7a797e5d95e963"
ENDPOINT = "https://api.indexnow.org/IndexNow"
BATCH = 9000   # l'API accepte jusqu'à 10 000 URLs par requête


def ensure_key_file(root):
    """Le fichier de clé doit être publié avec le site (il est aussi commité dans le dépôt ; ceci le recrée s'il manque)."""
    p = os.path.join(root, KEY + ".txt")
    try:
        if open(p, encoding="utf-8").read().strip() == KEY:
            return
    except OSError:
        pass
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(KEY + "\n")


def submit(urls, endpoint=None):
    """Envoie les URLs par lots ; renvoie la liste des codes HTTP (ou d'un court nom d'erreur réseau)."""
    host = urlparse(SITE_URL).netloc
    codes = []
    for i in range(0, len(urls), BATCH):
        body = json.dumps({"host": host, "key": KEY, "keyLocation": f"{SITE_URL}/{KEY}.txt", "urlList": urls[i:i + BATCH]}).encode("utf-8")
        req = urllib.request.Request(endpoint or ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "CarburantRadar-SEO-generator/2.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                codes.append(r.status)
        except urllib.error.HTTPError as e:
            codes.append(e.code)
        except Exception as e:   # réseau, DNS, délai : on consigne sans échouer
            codes.append(type(e).__name__)
    return codes


def run(root, urls):
    ensure_key_file(root)
    urls = sorted(set(u for u in urls if u.startswith(SITE_URL + "/")))
    return {"n": len(urls), "codes": submit(urls)}
