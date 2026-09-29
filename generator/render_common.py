"""Briques HTML communes : coque de page, CSS (identité CarburantRadar), fil d'Ariane, JSON-LD."""
import html
import json
import posixpath
import re

SITE_URL = "https://emilienzabu.github.io/CarburantRadar"
DATASET_URL = "https://data.economie.gouv.fr/explore/dataset/prix-des-carburants-en-france-flux-instantane-v2/"
GTAG = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-VNKWD96SLL"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-VNKWD96SLL');
</script>"""

CSS = """*{margin:0;padding:0;box-sizing:border-box}
:root{--bg-page:#0a0a0f;--bg-surface:#16161f;--border:#252535;--text:#e8e8f0;--text-muted:#a3a3bd;--accent:#f5a623;--good:#3ddc97;--warn:#ff6b35;--link:#a78bfa}
body{background:var(--bg-page);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6}
.wrap{max-width:700px;margin:0 auto;padding:20px 20px 60px}
a{color:var(--link)}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
header{margin-bottom:20px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--text);font-weight:700;font-size:16px;margin-bottom:18px}
.brand span{color:var(--accent)}
.breadcrumb{font-size:12px;color:var(--text-muted);margin-bottom:14px}
.breadcrumb ol{list-style:none;display:flex;flex-wrap:wrap;gap:4px}
.breadcrumb li{margin:0;padding:0;font-size:12px;list-style:none}
.breadcrumb li::before{content:none}
.breadcrumb li+li::before{content:"›";position:static;color:var(--text-muted);margin-right:4px;font-weight:400}
.breadcrumb a{color:var(--text-muted)}
h1{font-size:22px;margin-bottom:6px;line-height:1.3}
.subtitle{color:var(--text-muted);font-size:13px;margin-bottom:20px}
h2{font-size:17px;margin:28px 0 12px;color:var(--text)}
h3{font-size:15px;margin:18px 0 8px;color:var(--accent)}
p{margin-bottom:14px;font-size:15px;color:var(--text)}
li{margin-bottom:10px;font-size:14px;list-style:none;padding-left:22px;position:relative}
li::before{content:"✓";position:absolute;left:0;color:var(--accent);font-weight:700}
ul{margin:0 0 14px 0}
ul.plain li,ol.stations li{padding-left:0}
ul.plain li::before,ol.stations li::before{content:none}
.hero-price{background:linear-gradient(160deg,var(--bg-surface),var(--bg-page));border:1px solid var(--border);border-radius:18px;padding:22px;text-align:center;margin-bottom:14px}
.hero-price .label{font-size:12px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
.hero-price .price{font-size:38px;font-weight:800;color:var(--accent);line-height:1}
.hero-price .fuel{font-size:13px;color:var(--text-muted);margin-top:6px}
.hero-price .station{font-size:12px;color:var(--text-muted);margin-top:2px}
.cta-primary{display:block;text-align:center;background:var(--accent);color:#1a1200;font-weight:800;padding:15px;border-radius:12px;text-decoration:none;margin:0 0 24px;font-size:15px;box-shadow:0 4px 16px rgba(245,166,35,.25)}
.cta-secondary{display:block;text-align:center;background:var(--bg-surface);border:1px solid var(--border);color:var(--text);font-weight:700;padding:14px;border-radius:12px;text-decoration:none;margin:20px 0;font-size:14px}
.card{background:var(--bg-surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px;margin:16px 0}
.live-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border);font-size:14px}
.live-row:last-child{border-bottom:none}
.live-name{font-weight:600;color:var(--text)}
.live-addr{color:var(--text-muted);font-size:12px}
.live-price{font-weight:800;color:var(--accent);font-size:15px;white-space:nowrap;margin-left:10px}
.live-status{color:var(--text-muted);font-size:13px;text-align:center;padding:14px 0}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px}
.badge{background:var(--bg-surface);border:1px solid var(--border);color:var(--text-muted);font-size:11px;font-weight:600;padding:5px 10px;border-radius:20px}
.tablewrap{overflow-x:auto;margin:0 0 14px}
table{border-collapse:collapse;width:100%;font-size:13px;background:var(--bg-surface);border:1px solid var(--border);border-radius:10px}
caption{caption-side:top;text-align:left;color:var(--text-muted);font-size:12px;padding:0 0 8px}
th,td{padding:9px 10px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{color:var(--text-muted);font-weight:600;font-size:12px}
tbody tr:last-child td,tbody tr:last-child th{border-bottom:none}
tbody th{font-weight:600;color:var(--text)}
.min{color:var(--good);font-weight:800}
.max{color:var(--warn);font-weight:700}
ol.stations{margin:0 0 14px 0}
ol.stations li{background:var(--bg-surface);border:1px solid var(--border);border-radius:12px;padding:10px 12px;margin-bottom:8px}
.s-top{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.s-name{font-weight:600;font-size:14px}
.s-price{font-weight:800;color:var(--good);white-space:nowrap}
.s-meta{color:var(--text-muted);font-size:12px;margin-top:2px}
.s-links{font-size:12px;margin-top:4px}
.note{color:var(--text-muted);font-size:12px}
.updated{color:var(--text-muted);font-size:12px;border-top:1px solid var(--border);padding-top:12px;margin-top:22px}
.faq h3{color:var(--text);font-size:15px}
footer{margin-top:32px;padding-top:16px;border-top:1px solid var(--border);color:var(--text-muted);font-size:12px;text-align:center}
footer a{color:var(--text-muted)}"""


def esc(s):
    return html.escape(str(s), quote=True)


def rel(cur, target):
    """Lien relatif entre deux chemins de pages (répertoires avec slash final)."""
    r = posixpath.relpath(target, cur)
    return "./" if r == "." else r + "/"


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s))).strip()


def jsonld(obj):
    return '<script type="application/ld+json">\n' + json.dumps(obj, ensure_ascii=False, indent=2) + "\n</script>"


def breadcrumb(cur, items):
    """items = [(libellé, chemin_de_page)] ; le dernier est la page courante. Renvoie (html, json-ld)."""
    lis, ld = [], []
    for i, (label, path) in enumerate(items):
        last = i == len(items) - 1
        if last:
            lis.append(f'<li aria-current="page">{esc(label)}</li>')
        else:
            lis.append(f'<li><a href="{rel(cur, path)}">{esc(label)}</a></li>')
        ld.append({"@type": "ListItem", "position": i + 1, "name": label, "item": SITE_URL + path})
    nav = '<nav class="breadcrumb" aria-label="Fil d\'Ariane"><ol>' + "".join(lis) + "</ol></nav>"
    return nav, jsonld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": ld})


def item_list(cur_name, entries):
    """ItemList JSON-LD ; entries = [(nom, chemin)] tous visibles sur la page."""
    return jsonld({"@context": "https://schema.org", "@type": "ItemList", "name": cur_name,
                   "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "url": SITE_URL + p}
                                       for i, (n, p) in enumerate(entries)]})


def faq_ld(qas):
    return jsonld({"@context": "https://schema.org", "@type": "FAQPage",
                   "mainEntity": [{"@type": "Question", "name": q,
                                   "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas]})


def faq_html(qas, heading):
    out = [f'<section class="faq" aria-labelledby="faq"><h2 id="faq">{esc(heading)}</h2>']
    for q, a in qas:
        out.append(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>")
    out.append("</section>")
    return "\n".join(out)


def fit_desc(parts, limit=158):
    out = ""
    for p in parts:
        cand = (out + " " + p).strip()
        if len(cand) > limit:
            break
        out = cand
    return out


def shell(*, lang, title, desc, canonical, robots, cur, head_extra, body, script=""):
    icon = rel(cur, "/icons/icon-192.png").rstrip("/")
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<link rel="icon" type="image/png" sizes="192x192" href="{icon}">
<link rel="apple-touch-icon" href="{icon}">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="{robots}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="CarburantRadar">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE_URL}/icons/icon-192.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE_URL}/icons/icon-192.png">
<meta name="theme-color" content="#f5a623">
<meta name="color-scheme" content="dark">
{GTAG}
{head_extra}
<style>
{CSS}
</style>
</head>
<body>
{body}
{script}
</body>
</html>
"""
