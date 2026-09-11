#!/usr/bin/env python3
"""
Génère automatiquement toutes les pages "prix carburant par ville"
à partir d'un seul template + d'un fichier de données (villes.json).

Usage : python3 generator/generate.py
(exécuté automatiquement par la GitHub Action à chaque modif de villes.json)
"""
import json
import os
import hashlib

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SITE_URL = "https://emilienzabu.github.io/CarburantRadar"

with open(os.path.join(BASE, "villes.json"), encoding="utf-8") as f:
    data = json.load(f)

with open(os.path.join(BASE, "template.html"), encoding="utf-8") as f:
    TEMPLATE = f.read()

PAYS_CFG = data["pays"]
VILLES = data["villes"]


def pick_variant(variants, slug):
    """Choisit toujours la même variante pour une ville donnée (stable),
    répartie entre les variantes disponibles."""
    idx = int(hashlib.md5(slug.encode("utf-8")).hexdigest(), 16) % len(variants)
    return variants[idx]


def js_str(value):
    """Échappe une chaîne pour une insertion sûre dans du JavaScript
    (gère guillemets, apostrophes, tout caractère spécial automatiquement)."""
    return json.dumps(value, ensure_ascii=False)


sitemap_urls = [
    (f"{SITE_URL}/", "weekly", "1.0"),
    (f"{SITE_URL}/france/", "weekly", "1.0"),
    (f"{SITE_URL}/espagne/", "weekly", "1.0"),
    (f"{SITE_URL}/italie/", "weekly", "1.0"),
    (f"{SITE_URL}/guide/", "monthly", "0.8"),
]

generated = []

for v in VILLES:
    pays = v["pays"]
    cfg = PAYS_CFG[pays]
    ville = v["nom"]
    slug = v["slug"]

    intro = v.get("intro") or pick_variant(cfg["intro_generic_variants"], slug).format(ville=ville)
    why = v.get("why") or cfg["why_generic_tpl"]
    url = f"{SITE_URL}/{pays}/{cfg['dossier']}/{slug}/"
    url_pays = f"{SITE_URL}/{pays}/"

    benefits = cfg["benefits"]

    html = TEMPLATE
    replacements = {
        "%%LANG%%": cfg["lang"],
        "%%TITLE%%": cfg["title_tpl"].format(ville=ville),
        "%%META_DESC%%": cfg["meta_desc_tpl"].format(ville=ville),
        "%%CANONICAL_URL%%": url,
        "%%BREADCRUMB_HOME%%": cfg["breadcrumb_home"],
        "%%NOM_PAYS%%": cfg["nom_pays"],
        "%%URL_PAYS%%": url_pays,
        "%%VILLE%%": ville,
        "%%H1%%": cfg["h1_tpl"].format(ville=ville),
        "%%SUBTITLE%%": cfg["subtitle"],
        "%%BADGE_GRATUIT%%": cfg["badge_gratuit"],
        "%%BADGE_SANS_COMPTE%%": cfg["badge_sans_compte"],
        "%%BADGE_DONNEES_OFFICIELLES%%": cfg["badge_donnees"],
        "%%HERO_LABEL%%": cfg["hero_label"],
        "%%CTA_TOP_TXT%%": cfg["cta_top_txt"],
        "%%H2_LIVE%%": cfg["h2_live_tpl"].format(ville=ville, fuel_label=cfg["fuel_label"]),
        "%%LOADING_TXT%%": cfg["loading_txt"],
        "%%H2_BENEFITS%%": cfg["h2_benefits"],
        "%%BENEFIT_1%%": benefits[0],
        "%%BENEFIT_2%%": benefits[1],
        "%%BENEFIT_3%%": benefits[2],
        "%%BENEFIT_4%%": benefits[3],
        "%%CTA_BOTTOM_TXT%%": cfg["cta_bottom_txt"],
        "%%H2_WHY%%": cfg["h2_why"],
        "%%INTRO%%": intro,
        "%%WHY_TXT%%": why,
        "%%CTA_FINAL_TXT%%": cfg["cta_final_txt"],
        "%%FOOTER_TXT%%": cfg["footer_txt"],
        "%%LAT%%": str(v["lat"]),
        "%%LON%%": str(v["lon"]),
        "%%FUEL_MAP_JSON%%": json.dumps(cfg["fuel_map"], ensure_ascii=False),
        # Tokens injectés en tant que chaînes JS déjà échappées (voir js_str) :
        "%%ROUTE_JS%%": js_str(cfg["route"]),
        "%%FUEL_DEFAUT_JS%%": js_str(cfg["fuel_defaut"]),
        "%%FUEL_LABEL_JS%%": js_str(cfg["fuel_label"]),
        "%%HERO_SUFFIX_JS%%": js_str(cfg["hero_suffix"]),
        "%%NO_DATA_TXT_JS%%": js_str(cfg["no_data_txt"]),
        "%%ERROR_TXT_JS%%": js_str(cfg["error_txt"]),
    }

    for token, value in replacements.items():
        html = html.replace(token, value)

    remaining = [t for t in replacements if t in html]
    if remaining:
        raise SystemExit(f"ERREUR : tokens non remplacés dans {pays}/{slug} : {remaining}")

    out_dir = os.path.join(ROOT, pays, cfg["dossier"], slug)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    generated.append(out_path)
    sitemap_urls.append((url, "monthly", "0.7"))
    print(f"Généré : {pays}/{cfg['dossier']}/{slug}/index.html")

# Régénération complète du sitemap (racine + pays + guide + toutes les villes)
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for loc, freq, prio in sitemap_urls:
    sitemap += f"  <url>\n    <loc>{loc}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>\n"
sitemap += "</urlset>\n"

with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
    f.write(sitemap)

print(f"\n{len(generated)} page(s) ville générée(s). sitemap.xml mis à jour ({len(sitemap_urls)} URLs).")
