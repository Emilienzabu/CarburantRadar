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
ENDPOINTS = ["https://api.indexnow.org/IndexNow", "https://www.bing.com/indexnow"]   # le 2e, propre à Bing, renvoie un message d'erreur plus précis
BATCH = 9000   # l'API accepte jusqu'à 10 000 URLs par requête
_UA = {"User-Agent": "CarburantRadar-SEO-generator/2.0"}


def ensure_key_file(root):
    """Le fichier de clé doit être publié avec le site (il est aussi commité dans le dépôt ; ceci le recrée s'il manque). Il ne contient que la clé."""
    p = os.path.join(root, KEY + ".txt")
    try:
        if open(p, encoding="utf-8").read().strip() == KEY:
            return
    except OSError:
        pass
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(KEY)


def key_is_served(timeout=20):
    """-> (ok, détail). Le site doit déjà servir la clé : sinon l'API répond un 403 peu parlant (clé « introuvable » ou « différente »)."""
    url = f"{SITE_URL}/{KEY}.txt"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout) as r:
            body = r.read(400).decode("utf-8", "replace").strip()
            return (r.status == 200 and body == KEY), f"HTTP {r.status}" + ("" if body == KEY else ", contenu différent de la clé")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__


def _post(endpoint, payload):
    req = urllib.request.Request(endpoint, data=payload, method="POST", headers={**_UA, "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read(300).decode("utf-8", "replace").replace("\n", " ").strip()
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:   # réseau, DNS, délai : on consigne sans échouer
        return type(e).__name__, ""


def submit(urls, endpoints=None):
    """Envoie les URLs par lots, en essayant les points d'entrée dans l'ordre jusqu'à un 200/202.
    Renvoie une ligne par lot, ex. « api.indexnow.org 200 » ou « api.indexnow.org 403 {…} → www.bing.com 403 {…} »."""
    host = urlparse(SITE_URL).netloc
    out = []
    for i in range(0, len(urls), BATCH):
        payload = json.dumps({"host": host, "key": KEY, "keyLocation": f"{SITE_URL}/{KEY}.txt", "urlList": urls[i:i + BATCH]}).encode("utf-8")
        tried = []
        for ep in (endpoints or ENDPOINTS):
            code, body = _post(ep, payload)
            tried.append(f"{urlparse(ep).netloc} {code}" + (f" {body[:140]}" if body and code not in (200, 202) else ""))
            if code in (200, 202):
                break
        out.append(" → ".join(tried))
    return out


def run(root, urls):
    ensure_key_file(root)
    urls = sorted(set(u for u in urls if u.startswith(SITE_URL + "/")))
    ok, info = key_is_served()
    if not ok:
        return {"n": 0, "codes": [f"non envoyé : la clé n'est pas servie à {SITE_URL}/{KEY}.txt ({info})"]}
    return {"n": len(urls), "codes": submit(urls)}
