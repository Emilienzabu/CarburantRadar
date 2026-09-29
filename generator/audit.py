"""Audit du site généré : SEO technique, liens, sitemap, JSON-LD, doublons de contenu.
Indépendant du générateur : il relit les fichiers HTML tels qu'ils seront publiés."""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

SITE_URL = "https://emilienzabu.github.io/CarburantRadar"
LEGACY = {"/", "/france/", "/espagne/", "/italie/", "/guide/"}
SKIP_DIRS = {".git", ".github", "admin", "icons", "node_modules", "generator"}
MIN_WORDS = 250
SHINGLE = 6
DUP_JACCARD = 0.5


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.desc = None
        self.canonical = None
        self.robots = None
        self.h1 = []
        self._in_h1 = False
        self.hrefs = []
        self.assets = []
        self.jsonld = []
        self._in_ld = False
        self._ld = ""
        self._skip = 0
        self.in_main = False
        self.text = []
        self.main = []
        self.headings = []
        self._cur_h = None
        self.imgs_no_alt = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            n = (a.get("name") or "").lower()
            if n == "description":
                self.desc = a.get("content", "")
            elif n == "robots":
                self.robots = (a.get("content") or "").lower()
        elif tag == "link":
            if a.get("rel") == "canonical":
                self.canonical = a.get("href")
            elif a.get("href"):
                self.assets.append(a["href"])
        elif tag == "a" and a.get("href") is not None:
            self.hrefs.append(a["href"])
        elif tag == "script":
            if a.get("type") == "application/ld+json":
                self._in_ld, self._ld = True, ""
            if a.get("src"):
                self.assets.append(a["src"])
            self._skip += 1
        elif tag == "style":
            self._skip += 1
        elif tag == "img":
            if a.get("src"):
                self.assets.append(a["src"])
            if a.get("alt") is None:
                self.imgs_no_alt += 1
        elif tag == "main":
            self.in_main = True
        elif tag in ("h1", "h2", "h3", "h4"):
            self._cur_h = tag
            if tag == "h1":
                self._in_h1 = True
                self.h1.append("")
            self.headings.append(int(tag[1]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            if self._in_ld:
                self.jsonld.append(self._ld)
                self._in_ld = False
            self._skip = max(0, self._skip - 1)
        elif tag == "style":
            self._skip = max(0, self._skip - 1)
        elif tag == "main":
            self.in_main = False
        elif tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self._ld += data
            return
        if self._skip:
            return
        if self._in_h1 and self.h1:
            self.h1[-1] += data
        self.text.append(data)
        if self.in_main:
            self.main.append(data)


def _walk(root):
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x != ".git" and not (d == root and x in SKIP_DIRS))
        if "index.html" in files:
            yield os.path.relpath(os.path.join(d, "index.html"), root)


def urlpath(rel):
    p = "/" + os.path.dirname(rel).replace(os.sep, "/")
    return p if p.endswith("/") else p + "/"


def norm_ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def page_type(p):
    parts = [x for x in p.strip("/").split("/") if x]
    if p == "/france/prix-carburant/":
        return "hub"
    if len(parts) == 2 and parts[0] == "france" and parts[1] != "prix-carburant":
        return "geo"
    if len(parts) == 3 and parts[0] == "france" and parts[1] == "prix-carburant":
        return "city"
    if len(parts) == 4 and parts[0] == "france" and parts[1] == "prix-carburant":
        return "fuel"
    if len(parts) == 3 and parts[0] in ("espagne", "italie"):
        return "city_" + parts[0]
    if len(parts) == 2 and parts[0] in ("espagne", "italie"):
        return "hub_" + parts[0]
    return "other"


def resolve(root, cur, href):
    """Résout un lien interne. Renvoie (chemin_url, erreur|None) ou (None, None) si externe/ignoré."""
    h = href.strip()
    if not h or h.startswith(("#", "mailto:", "tel:", "javascript:", "data:", "sms:", "intent:", "market:")):
        return None, None
    if h.startswith(SITE_URL + "/") or h == SITE_URL:
        h = h[len(SITE_URL):] or "/"
        target = urljoin("https://x.test/", h)
        raw = urlparse(target).path
        return raw, None
    if re.match(r"^[a-z][a-z0-9+.-]*:", h, re.I) or h.startswith("//"):
        return None, None
    if h.startswith("/"):
        return urlparse(urljoin("https://x.test/", h)).path, "lien racine absolu (cassé sur un site de projet GitHub Pages)"
    full = urljoin("https://x.test" + cur, h)
    return urlparse(full).path, None


def target_exists(root, path):
    fs = os.path.join(root, path.lstrip("/"))
    if path.endswith("/"):
        return os.path.isfile(os.path.join(fs, "index.html"))
    if os.path.isfile(fs):
        return True
    return False


def audit(root, generated_check=True):
    errors, warns = [], []
    pages = {}
    for rel in _walk(root):
        p = urlpath(rel)
        parser = Page()
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
            parser.feed(f.read())
        pages[p] = parser

    def err(p, msg):
        (warns if p in LEGACY else errors).append(f"{p} : {msg}")

    def warn(p, msg):
        warns.append(f"{p} : {msg}")

    info = {}
    inbound = defaultdict(set)
    internal_links = {}
    for p, pg in pages.items():
        t = page_type(p)
        title, desc = norm_ws(pg.title), norm_ws(pg.desc) if pg.desc is not None else None
        h1 = [norm_ws(x) for x in pg.h1]
        if not title:
            err(p, "title manquant")
        if not desc:
            err(p, "meta description manquante")
        if len(h1) == 0:
            err(p, "H1 manquant")
        elif len(h1) > 1:
            err(p, f"{len(h1)} balises H1")
        exp = SITE_URL + p
        if pg.canonical != exp:
            err(p, f"canonical incorrect ({pg.canonical!r}, attendu {exp!r})")
        if pg.robots is None:
            warn(p, "meta robots absente")
        # hiérarchie des titres : pas de saut de niveau
        last = 0
        for lv in pg.headings:
            if last and lv > last + 1:
                warn(p, f"saut de niveau de titre (h{last} -> h{lv})")
                break
            last = lv
        if pg.imgs_no_alt:
            warn(p, f"{pg.imgs_no_alt} image(s) sans attribut alt")
        # liens
        links = set()
        for href in pg.hrefs:
            path, problem = resolve(root, p, href)
            if path is None:
                continue
            if problem:
                err(p, f"{problem} : {href}")
                continue
            if not path.endswith("/") and not os.path.splitext(path)[1]:
                fs = os.path.join(root, path.lstrip("/"))
                if os.path.isdir(fs):
                    err(p, f"lien vers un dossier sans slash final : {href}")
                    continue
            if not target_exists(root, path):
                err(p, f"lien cassé : {href} -> {path}")
                continue
            links.add(path)
            if path != p:
                inbound[path].add(p)
        for a in pg.assets:
            path, problem = resolve(root, p, a)
            if path is None:
                continue
            if problem:
                err(p, f"{problem} : {a}")
            elif not target_exists(root, path):
                err(p, f"ressource introuvable : {a}")
        internal_links[p] = links
        # JSON-LD
        text_all = norm_ws(" ".join(pg.text))
        for raw in pg.jsonld:
            try:
                d = json.loads(raw)
            except json.JSONDecodeError as e:
                err(p, f"JSON-LD invalide ({e})")
                continue
            ty = d.get("@type")
            if ty == "FAQPage":
                for q in d.get("mainEntity", []):
                    if norm_ws(q.get("name")) not in text_all or norm_ws(q["acceptedAnswer"]["text"]) not in text_all:
                        err(p, "FAQPage JSON-LD ne correspond pas au contenu visible")
                        break
            elif ty == "BreadcrumbList":
                for it in d.get("itemListElement", []):
                    u = it.get("item", "")
                    if not u.startswith(SITE_URL) or not target_exists(root, u[len(SITE_URL):] or "/"):
                        err(p, f"BreadcrumbList : URL inexistante {u}")
                if d.get("itemListElement") and d["itemListElement"][-1]["item"] != exp:
                    err(p, "BreadcrumbList : le dernier élément n'est pas la page courante")
            elif ty == "ItemList":
                for it in d.get("itemListElement", []):
                    u = it.get("url", "")
                    if not u.startswith(SITE_URL) or not target_exists(root, u[len(SITE_URL):] or "/"):
                        err(p, f"ItemList : URL inexistante {u}")
        main_text = norm_ws(" ".join(pg.main))
        words = len(main_text.split())
        info[p] = {"type": t, "title": title, "desc": desc, "h1": h1[0] if h1 else "", "canonical": pg.canonical,
                   "robots": pg.robots or "", "noindex": "noindex" in (pg.robots or ""), "words": words,
                   "main": main_text, "n_links": len(links), "faq": any('"FAQPage"' in j for j in pg.jsonld),
                   "jsonld_types": sorted({(json.loads(j).get("@type") if j.strip().startswith("{") else "?") for j in pg.jsonld if _ok(j)})}

    # sitemap
    sm_urls = []
    smp = os.path.join(root, "sitemap_1.xml")
    if not os.path.isfile(smp):
        errors.append("sitemap_1.xml introuvable")
    else:
        sm_urls = re.findall(r"<loc>([^<]+)</loc>", open(smp, encoding="utf-8").read())
        dup = [u for u, n in Counter(sm_urls).items() if n > 1]
        for u in dup:
            errors.append(f"sitemap : URL en double {u}")
        sm_paths = set()
        for u in sm_urls:
            if not u.startswith(SITE_URL):
                errors.append(f"sitemap : URL hors site {u}")
                continue
            path = u[len(SITE_URL):] or "/"
            sm_paths.add(path)
            if not target_exists(root, path):
                errors.append(f"sitemap : URL inexistante {u}")
            elif path in info and info[path]["noindex"]:
                errors.append(f"sitemap : page noindex présente {u}")
            elif path in info and not path.endswith("/"):
                errors.append(f"sitemap : mauvais slash {u}")
        for p, i in info.items():
            if not i["noindex"] and p not in sm_paths:
                errors.append(f"{p} : page indexable absente du sitemap")

    # robots.txt
    rp = os.path.join(root, "robots.txt")
    if os.path.isfile(rp):
        m = re.findall(r"(?im)^sitemap:\s*(\S+)", open(rp, encoding="utf-8").read())
        for u in m:
            if not u.startswith(SITE_URL) or not target_exists(root, u[len(SITE_URL):]):
                errors.append(f"robots.txt : Sitemap inexistant {u}")

    # unicité
    for key, sev in (("title", errors), ("canonical", errors), ("desc", warns), ("h1", warns)):
        c = Counter(i[key] for p, i in info.items() if p not in LEGACY and i[key])
        for v, n in c.items():
            if n > 1:
                sev.append(f"{key} en double ({n} pages) : {str(v)[:80]}")

    # orphelines : atteignables depuis l'accueil par liens HTML
    seen, todo = {"/"}, ["/"]
    while todo:
        cur = todo.pop()
        for nxt in internal_links.get(cur, ()):
            if nxt in info and nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    orphans = sorted(p for p, i in info.items() if p not in seen and not i["noindex"])
    for p in orphans:
        err(p, "page orpheline (aucun chemin de liens depuis l'accueil)")
    noindex_orphans = sorted(p for p, i in info.items() if p not in seen and i["noindex"])

    # test spécial : lien /france/ depuis une page ville
    special = None
    for p, i in info.items():
        if i["type"] == "city" and p.endswith("/avignon/"):
            path, _ = resolve(root, p, "../../")
            special = (p, path, target_exists(root, path or "/"))
            if path != "/france/" or not special[2]:
                errors.append(f"{p} : ../../ ne mène pas à /france/")
            break

    return {"errors": errors, "warnings": warns, "info": info, "sitemap": sm_urls, "orphans": [p for p in orphans if p not in LEGACY],
            "noindex_orphans": noindex_orphans, "inbound": {k: len(v) for k, v in inbound.items()}, "special": special}


def _ok(j):
    try:
        json.loads(j)
        return True
    except Exception:
        return False


def similarity(info):
    """Unicité du contenu entre pages du même type (zone <main> uniquement)."""
    groups = defaultdict(list)
    for p, i in info.items():
        if i["type"] in ("city", "fuel", "geo"):
            groups[i["type"]].append(p)
    res = {}
    for ty, plist in groups.items():
        sh = {}
        for p in plist:
            w = re.findall(r"\w+", info[p]["main"].lower())
            sh[p] = {" ".join(w[k:k + SHINGLE]) for k in range(max(0, len(w) - SHINGLE + 1))}
        count = Counter(s for v in sh.values() for s in v)
        uniq = {p: (sum(1 for s in v if count[s] == 1) / len(v) * 100 if v else 0.0) for p, v in sh.items()}
        pairs = []
        for i_, a in enumerate(plist):
            for b in plist[i_ + 1:]:
                inter = len(sh[a] & sh[b])
                if inter:
                    j = inter / len(sh[a] | sh[b])
                    if j >= DUP_JACCARD:
                        pairs.append((round(j, 2), a, b))
        res[ty] = {"unique_pct": uniq, "dups": sorted(pairs, reverse=True)}
    return res


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = audit(root)
    for w in r["warnings"][:60]:
        print("AVERTISSEMENT", w)
    for e in r["errors"]:
        print("ERREUR", e)
    print(f"{len(r['info'])} pages auditées, {len(r['errors'])} erreur(s), {len(r['warnings'])} avertissement(s)")
    sys.exit(1 if r["errors"] else 0)
