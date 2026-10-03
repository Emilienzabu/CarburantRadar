#!/usr/bin/env python3
"""
Générateur CarburantRadar — pages SEO (France enrichie avec les prix officiels ; Espagne/Italie inchangées).

Usage :
    python3 generate.py                      # depuis la racine du dépôt (télécharge les prix officiels)
    python3 generator/generate.py --data F   # utiliser un export JSON local (tests hors ligne)
    python3 generator/generate.py --root D   # écrire dans un autre dossier (tests)

Principes : aucune donnée inventée, sortie déterministe (mêmes données => mêmes pages), échec sans rien écrire
si les données officielles ne peuvent pas être récupérées.
"""
import argparse
import hashlib
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import audit  # noqa: E402
import communes_auto  # noqa: E402
import data_es  # noqa: E402
import data_fr  # noqa: E402
import data_it  # noqa: E402
import pipeline_i18n  # noqa: E402
import render_es  # noqa: E402
import render_it  # noqa: E402
import history as H  # noqa: E402
import stats_fr as S  # noqa: E402
from render_common import SITE_URL  # noqa: E402
from render_fr import render_city, render_fuel_page  # noqa: E402
from render_geo import render_dep, render_region, render_hub_fr, render_hub_simple  # noqa: E402
from data_fr import FUELS, FUEL_SLUG  # noqa: E402


GENERATED = []


def write(root, urlpath, html):
    GENERATED.append(urlpath)
    d = os.path.join(root, urlpath.strip("/"))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(html)


# ---------------------------------------------------------------- Espagne / Italie : pipeline historique inchangé

def pick_variant(variants, slug):
    return variants[int(hashlib.md5(slug.encode("utf-8")).hexdigest(), 16) % len(variants)]


def js_str(value):
    return json.dumps(value, ensure_ascii=False)


def legacy_page(v, cfg, template):
    pays, ville, slug = v["pays"], v["nom"], v["slug"]
    intro = v.get("intro") or pick_variant(cfg["intro_generic_variants"], slug).format(ville=ville)
    why = v.get("why") or cfg["why_generic_tpl"]
    url = f"{SITE_URL}/{pays}/{cfg['dossier']}/{slug}/"
    b = cfg["benefits"]
    rep = {
        "%%LANG%%": cfg["lang"], "%%TITLE%%": cfg["title_tpl"].format(ville=ville),
        "%%META_DESC%%": cfg["meta_desc_tpl"].format(ville=ville), "%%CANONICAL_URL%%": url,
        "%%BREADCRUMB_HOME%%": cfg["breadcrumb_home"], "%%NOM_PAYS%%": cfg["nom_pays"], "%%URL_PAYS%%": f"{SITE_URL}/{pays}/",
        "%%VILLE%%": ville, "%%H1%%": cfg["h1_tpl"].format(ville=ville), "%%SUBTITLE%%": cfg["subtitle"],
        "%%BADGE_GRATUIT%%": cfg["badge_gratuit"], "%%BADGE_SANS_COMPTE%%": cfg["badge_sans_compte"],
        "%%BADGE_DONNEES_OFFICIELLES%%": cfg["badge_donnees"], "%%HERO_LABEL%%": cfg["hero_label"],
        "%%CTA_TOP_TXT%%": cfg["cta_top_txt"], "%%H2_LIVE%%": cfg["h2_live_tpl"].format(ville=ville, fuel_label=cfg["fuel_label"]),
        "%%LOADING_TXT%%": cfg["loading_txt"], "%%H2_BENEFITS%%": cfg["h2_benefits"],
        "%%BENEFIT_1%%": b[0], "%%BENEFIT_2%%": b[1], "%%BENEFIT_3%%": b[2], "%%BENEFIT_4%%": b[3],
        "%%CTA_BOTTOM_TXT%%": cfg["cta_bottom_txt"], "%%H2_WHY%%": cfg["h2_why"], "%%INTRO%%": intro, "%%WHY_TXT%%": why,
        "%%CTA_FINAL_TXT%%": cfg["cta_final_txt"], "%%FOOTER_TXT%%": cfg["footer_txt"],
        "%%LAT%%": str(v["lat"]), "%%LON%%": str(v["lon"]), "%%FUEL_MAP_JSON%%": json.dumps(cfg["fuel_map"], ensure_ascii=False),
        "%%ROUTE_JS%%": js_str(cfg["route"]), "%%FUEL_DEFAUT_JS%%": js_str(cfg["fuel_defaut"]),
        "%%FUEL_LABEL_JS%%": js_str(cfg["fuel_label"]), "%%HERO_SUFFIX_JS%%": js_str(cfg["hero_suffix"]),
        "%%NO_DATA_TXT_JS%%": js_str(cfg["no_data_txt"]), "%%ERROR_TXT_JS%%": js_str(cfg["error_txt"]),
    }
    html = template
    for k, val in rep.items():
        html = html.replace(k, val)
    left = [k for k in rep if k in html]
    if left:
        raise SystemExit(f"ERREUR : tokens non remplacés dans {pays}/{slug} : {left}")
    return html


# ---------------------------------------------------------------- nettoyage des pages qui ne sont plus générées

FUEL_PAGES_INDEXABLE = False   # pages ville+carburant : accessibles et liées, mais noindex (contenu trop proche des pages villes)

MANIFEST = os.path.join("generator", "generated_pages.json")
SWEEP_ROOTS = ["france/prix-carburant", "espagne/precio-carburante", "italie/prezzo-carburante"]


def prune_stale(root):
    """Supprime les pages écrites par un run précédent (manifeste) mais absentes de celui-ci, puis réécrit le manifeste."""
    mp = os.path.join(root, MANIFEST)
    old = json.load(open(mp, encoding="utf-8")) if os.path.isfile(mp) else []
    removed = 0
    for up in sorted(set(old) - set(GENERATED)):
        d = os.path.join(root, up.strip("/"))
        f = os.path.join(d, "index.html")
        if os.path.isfile(f):
            os.remove(f)
            removed += 1
        try:
            os.rmdir(d)
        except OSError:
            pass
    # filet de sécurité : dans les dossiers 100 % générés, toute page non écrite pendant ce run est obsolète
    # (indispensable depuis que les pages HTML ne sont plus commitées : le checkout peut contenir d'anciennes pages)
    keep = {u.strip("/") for u in GENERATED}
    for sub in SWEEP_ROOTS:
        base = os.path.join(root, sub)
        for dirpath, _dirs, files in os.walk(base, topdown=False):
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            if "index.html" in files and rel not in keep:
                os.remove(os.path.join(dirpath, "index.html"))
                removed += 1
            if dirpath != base:
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass
    with open(mp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(sorted(set(GENERATED)), fh, indent=0)
        fh.write("\n")
    if removed:
        print(f"{removed} page(s) obsolète(s) supprimée(s).")


# ---------------------------------------------------------------- sitemap / robots

def write_sitemap(root, entries):
    out = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for loc, freq, prio, lastmod in entries:
        out += f"  <url>\n    <loc>{loc}</loc>\n" + (f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else "") \
               + f"    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>\n"
    out += "</urlset>\n"
    with open(os.path.join(root, "sitemap_1.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    rp = os.path.join(root, "robots.txt")
    txt = open(rp, encoding="utf-8").read() if os.path.isfile(rp) else "User-agent: *\nAllow: /\nDisallow: /admin/\n"
    line = f"Sitemap: {SITE_URL}/sitemap_1.xml"
    txt = re.sub(r"(?im)^sitemap:.*$", line, txt) if re.search(r"(?im)^sitemap:", txt) else txt.rstrip("\n") + "\n\n" + line + "\n"
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)


# ---------------------------------------------------------------- rapport

def write_report(root, ctx, stats, aud, sim):
    info = aud["info"]
    gen = {p: i for p, i in info.items() if i["type"] in ("city", "fuel", "geo", "hub")}
    types = {t: [p for p, i in gen.items() if i["type"] == t] for t in ("city", "fuel", "geo", "hub")}
    dep_paths = {f"/france/{d['slug']}/" for d in stats["dep_list"]}
    reg_paths = {f"/france/{r['slug']}/" for r in stats["reg_list"]}
    L = []
    a = L.append
    a("# SEO_REPORT — pages générées\n")
    a(f"Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : "
      f"{stats['latest_txt']}. Rapport déterministe (aucun horodatage de génération).\n")
    a("## Volumétrie\n")
    a("| Indicateur | Valeur |\n|---|---|")
    a(f"| Pages France générées par le nouveau système | {len(gen)} |")
    a(f"| Pages villes (France) | {len(types['city'])} dont {stats['n_index']} indexables et {stats['n_noindex']} en noindex |")
    a(f"| — dont communes ajoutées automatiquement (hors villes.json) | {stats['n_auto']} |")
    a(f"| Pages départements | {len(dep_paths)} |")
    a(f"| Pages régions | {len(reg_paths)} |")
    a(f"| Pages ville + carburant | {len(types['fuel'])} |")
    for f in FUELS:
        a(f"| — dont {data_fr.FUEL_LABEL[f]} | {sum(1 for x in stats['fuel_pages'] if x[0] == f)} |")
    a(f"| Pages hub (liste des villes France) | {len(types['hub'])} |")
    a(f"| Pages Espagne / Italie (pipeline inchangé) | {sum(1 for i in info.values() if i['type'].startswith('city_'))} villes, "
      f"{sum(1 for i in info.values() if i['type'].startswith('hub_'))} hubs |")
    a(f"| URLs dans le sitemap | {len(aud['sitemap'])} |")
    a(f"| Stations analysées (jeu de données) | {stats['n_stations']} |")
    hd = stats["hist_days"]
    a(f"| Jours d'historique enregistrés | {len(hd)}" + (f" (du {hd[0]} au {hd[-1]})" if hd else "") + " |\n")
    a("## Espagne (pages enrichies)\n")
    es = stats.get("es")
    if es:
        a(f"- Source : API officielle du Ministerio ; {es['n_stations']} stations exploitables ; données du {es['latest'].strftime('%d/%m/%Y %H:%M UTC')}.")
        a(f"- Pages villes : {es['n_cities']} dont {es['n_index']} indexables ({es['n_auto']} ajoutées automatiquement) ; pages provinces : {es['n_dep']}.\n")
    else:
        a(f"- **Source indisponible, pages historiques conservées** : {stats.get('es_err')}")
        a(f"- Diagnostic : {data_es.DIAG}\n")
    a("## Italie (pages enrichies)\n")
    it = stats.get("it")
    if it:
        a(f"- Source : CSV du MIMIT ; {it['n_stations']} stations exploitables ; données du {it['latest'].strftime('%d/%m/%Y %H:%M UTC')}.")
        a(f"- Pages villes : {it['n_cities']} dont {it['n_index']} indexables ({it['n_auto']} ajoutées automatiquement) ; pages provinces : {it['n_dep']}.\n")
    else:
        a(f"- **Source indisponible, pages historiques conservées** : {stats.get('it_err')}")
        a(f"- Diagnostic : {data_it.DIAG}\n")
    a("## Unicité des balises (pages générées France)\n")
    def uniq(key):
        vals = [gen[p][key] for p in gen]
        return f"{len(set(vals))} / {len(vals)}"
    a("| Balise | Valeurs distinctes / pages |\n|---|---|")
    for lab, key in (("Titles", "title"), ("Meta descriptions", "desc"), ("H1", "h1"), ("Canonicals", "canonical")):
        a(f"| {lab} | {uniq(key)} |")
    a("")
    a("## Qualité du contenu\n")
    cities = [c for c in stats["cities"]]
    thin_words = [p for p in gen if gen[p]["words"] < audit.MIN_WORDS and gen[p]["type"] != "hub"]
    a(f"- Pages avec moins de {audit.MIN_WORDS} mots (zone principale) : {len(thin_words)}")
    a(f"- Pages villes avec peu de données (score < {S.MIN_SCORE_INDEX} ou < {S.MIN_STATIONS_INDEX} stations ou < {S.MIN_FUELS_INDEX} carburants → noindex) : {stats['n_noindex']}")
    a(f"- Pages villes sans station : {sum(1 for c in cities if c['n_rad'] == 0)} (rayon de 12 km)")
    a(f"- Pages villes sans prix : {sum(1 for c in cities if not c['fuels'])}")
    a(f"- Pages villes sans ville voisine affichée : {sum(1 for c in cities if not c['neighbors_shown'])}")
    a(f"- Pages villes sans département identifié : {sum(1 for c in cities if not c['dep_code'])}")
    if stats["no_dep"]:
        a("  - " + ", ".join(sorted(stats["no_dep"])))
    a("")
    a("## Maillage interne (pages France générées)\n")
    tot = sum(gen[p]["n_links"] for p in gen)
    a(f"- Liens internes distincts au total : {tot} ; moyenne par page : {tot / max(1, len(gen)):.1f}")
    a(f"- Pages orphelines indexables : {len(aud['orphans'])} ; pages noindex non liées : {len(aud['noindex_orphans'])}\n")
    a("## Pages les plus / moins riches (villes)\n")
    ranked = sorted(cities, key=lambda c: (-c["score"], c["slug"]))
    a("| Plus riches | Score | Stations | Carburants |\n|---|---|---|---|")
    for c in ranked[:5]:
        a(f"| {c['nom']} | {c['score']} | {c['n_scope']} | {len(c['fuels'])} |")
    a("\n| Moins riches | Score | Stations | Carburants |\n|---|---|---|---|")
    for c in ranked[-5:][::-1]:
        a(f"| {c['nom']} | {c['score']} | {c['n_scope']} | {len(c['fuels'])} |")
    a("")
    a("## Doublons de contenu (zone principale, séquences de 6 mots)\n")
    for ty, lab in (("city", "villes"), ("fuel", "ville + carburant"), ("geo", "départements / régions")):
        s = sim.get(ty)
        if not s:
            continue
        vals = list(s["unique_pct"].values())
        a(f"- Pages {lab} : contenu unique moyen {sum(vals) / len(vals):.0f} % (min {min(vals):.0f} %) ; "
          f"paires quasi identiques (Jaccard ≥ {audit.DUP_JACCARD}) : {len(s['dups'])}")
        for j, x, y in s["dups"][:10]:
            a(f"  - {j} : {x} ↔ {y}")
    a("")
    a("## Validation\n")
    a(f"- Erreurs : {len(aud['errors'])} ; avertissements : {len(aud['warnings'])}")
    for e in aud["errors"][:50]:
        a(f"  - ERREUR {e}")
    for w in aud["warnings"][:30]:
        a(f"  - avertissement {w}")
    sp = aud["special"]
    if sp:
        a(f"- Test lien France : `{sp[0]}` + `../../` → `{sp[1]}` ({'OK' if sp[2] and sp[1] == '/france/' else 'ÉCHEC'})")
    a("")
    with open(os.path.join(root, "SEO_REPORT.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- principal

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="export JSON local du flux officiel (sinon téléchargement)")
    ap.add_argument("--data-es", help="export JSON local de l'API espagnole (sinon téléchargement)")
    ap.add_argument("--data-it", help="dossier local contenant les deux CSV du MIMIT (sinon téléchargement)")
    ap.add_argument("--root", help="dossier de sortie (défaut : racine du dépôt)")
    args = ap.parse_args()
    root = os.path.abspath(args.root) if args.root else os.path.dirname(BASE)

    conf = json.load(open(os.path.join(BASE, "villes.json"), encoding="utf-8"))
    pays_cfg, villes = conf["pays"], conf["villes"]
    template = open(os.path.join(BASE, "template.html"), encoding="utf-8").read()

    # 1) données officielles : en cas d'échec on s'arrête AVANT d'écrire quoi que ce soit
    try:
        stations, latest = data_fr.load(args.data)
    except Exception as e:
        print(f"ERREUR : données officielles indisponibles ({e}). Aucune page modifiée.", file=sys.stderr)
        return 2

    fr_cfg = pays_cfg["france"]
    fr_villes = [v for v in villes if v["pays"] == "france"]
    # communes découvertes automatiquement dans le flux (en plus de villes.json) ; pages déjà publiées conservées
    mp = os.path.join(root, MANIFEST)
    prev_slugs = communes_auto.previous_slugs(json.load(open(mp, encoding="utf-8")) if os.path.isfile(mp) else [])
    auto_villes = communes_auto.discover(stations, fr_villes, prev_slugs)
    nat = S.national(stations)
    dep_info, reg_info = S.build_geo(stations)

    # 1 bis) Espagne : mêmes pages riches que la France si la source répond ; sinon pages historiques (et on s'arrête
    # si des pages espagnoles enrichies étaient déjà publiées, pour ne pas les faire disparaître du site)
    es_cfg = pays_cfg["espagne"]
    es_legacy = [v for v in villes if v["pays"] == "espagne"]
    es_res, es_err = None, None
    old_paths = json.load(open(mp, encoding="utf-8")) if os.path.isfile(mp) else []
    es_prev = communes_auto.previous_slugs(old_paths, "espagne", render_es.DOSSIER)
    try:
        from geo import norm_name
        es_stations, es_latest = data_es.load(args.data_es, known={norm_name(v["nom"]) for v in es_legacy})
        es_res = pipeline_i18n.build_country(render_es, es_cfg, es_legacy, es_stations, es_latest, es_prev)
    except Exception as e:  # source espagnole indisponible ou format inattendu
        es_err = f"{type(e).__name__}: {e}"
        if es_prev - {v["slug"] for v in es_legacy}:
            print(f"ERREUR : données espagnoles indisponibles ({es_err}). Aucune page modifiée.", file=sys.stderr)
            return 2

    # 1 ter) Italie : même principe que l'Espagne (CSV du MIMIT)
    it_cfg = pays_cfg["italie"]
    it_legacy = [v for v in villes if v["pays"] == "italie"]
    it_res, it_err = None, None
    it_prev = communes_auto.previous_slugs(old_paths, "italie", render_it.DOSSIER)
    try:
        it_stations, it_latest = data_it.load(args.data_it)
        it_res = pipeline_i18n.build_country(render_it, it_cfg, it_legacy, it_stations, it_latest, it_prev)
    except Exception as e:  # source italienne indisponible ou format inattendu
        it_err = f"{type(e).__name__}: {e}"
        if it_prev - {v["slug"] for v in it_legacy}:
            print(f"ERREUR : données italiennes indisponibles ({it_err}). Aucune page modifiée.", file=sys.stderr)
            return 2

    # 2) villes
    cities = [communes_auto.build_city(v, stations) if v.get("auto") else S.build_city(v, stations)
              for v in fr_villes + auto_villes]
    by_slug = {c["slug"]: c for c in cities}
    cand = S.neighbor_candidates(cities)
    for c in cities:
        viable = lambda o: o["n_scope"] >= S.MIN_STATIONS_INDEX and len(o["fuels"]) >= S.MIN_FUELS_INDEX
        c["neighbors"] = [(d, s) for d, s in cand[c["slug"]] if viable(by_slug[s])]
        dep = dep_info.get(c["dep_code"])
        c["compare_dep"] = bool(dep) and any(f in dep["stats"]["fuels"] and dep["stats"]["fuels"][f]["n"] >= S.MIN_DEP_COMPARE
                                             and c["fuels"][f]["n"] >= 3 for f in c["fuels"])
        S.score_city(c, dep_info, nat)
    # une nouvelle commune automatique trop pauvre n'est pas publiée (pas de pages noindex en masse)
    cities = [c for c in cities if c["indexable"] or not c["v"].get("auto") or c["slug"] in prev_slugs]
    idx = [c for c in cities if c["indexable"]]
    idx_slugs = {c["slug"] for c in idx}
    for c in cities:
        c["neighbors_shown"] = []
        for d, s in cand[c["slug"]]:
            if s in idx_slugs and len(c["neighbors_shown"]) < S.NEIGHBOR_MAX:
                o = by_slug[s]
                c["neighbors_shown"].append({"slug": s, "nom": o["nom"], "dist": d, "fuels": o["fuels"]})
        shown = {n["slug"] for n in c["neighbors_shown"]} | {c["slug"]}
        c["others_dep"] = sorted((o for o in idx if o["dep_code"] and o["dep_code"] == c["dep_code"] and o["slug"] not in shown),
                                 key=lambda o: (-o["n_scope"], o["nom"]))[:10]

    # 3) départements / régions éligibles
    dep_pages = {}
    for code, d in dep_info.items():
        cs = [c for c in idx if c["dep_code"] == code]
        if cs and d["stats"]["n"] >= S.MIN_DEP_STATIONS:
            dep_pages[code] = True
    reg_pages = {}
    for code, r in reg_info.items():
        ds = [d for c_, d in dep_info.items() if dep_pages.get(c_) and d["reg_code"] == code]
        if ds and r["stats"]["n"] >= S.MIN_DEP_STATIONS:
            reg_pages[code] = True
    fuel_pages = {(f, c["slug"]) for c in idx if c["scope"] == "commune" for f in c["fuels"] if c["fuels"][f]["n"] >= S.MIN_FUEL_PAGE}

    ctx = {"cfg": fr_cfg, "dep_info": dep_info, "reg_info": reg_info, "dep_pages": dep_pages, "reg_pages": reg_pages,
           "nat": nat, "latest": latest, "fuel_pages": fuel_pages, "min_dep_compare": S.MIN_DEP_COMPARE}

    # 3 bis) historique : un instantané par jour de données, 30 jours conservés
    day = latest.astimezone(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    hist = H.update(H.load(root), day, H.snapshot(cities))

    # 4) écriture des pages
    lastmod = latest.astimezone(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    entries = [(f"{SITE_URL}/", "weekly", "1.0", None), (f"{SITE_URL}/france/", "weekly", "1.0", None),
               (f"{SITE_URL}/espagne/", "weekly", "1.0", None), (f"{SITE_URL}/italie/", "weekly", "1.0", None),
               (f"{SITE_URL}/guide/", "monthly", "0.8", None)]

    dep_list = [dep_info[k] for k in sorted(dep_pages, key=lambda k: dep_info[k]["name"])]
    reg_list = [reg_info[k] for k in sorted(reg_pages, key=lambda k: reg_info[k]["name"])]

    html, _, _ = render_hub_fr(ctx, sorted(idx, key=lambda c: c["nom"]), dep_list, reg_list)
    write(root, "/france/prix-carburant/", html)
    entries.append((f"{SITE_URL}/france/prix-carburant/", "weekly", "0.9", lastmod))

    for r in reg_list:
        deps = [d for d in dep_list if d["reg_code"] == r["code"]]
        cs = sorted((c for c in idx if c["reg_code"] == r["code"]), key=lambda c: (-c["n_scope"], c["nom"]))
        html, _, _ = render_region(r, deps, cs, ctx)
        write(root, f"/france/{r['slug']}/", html)
        entries.append((f"{SITE_URL}/france/{r['slug']}/", "daily", "0.8", lastmod))
    for d in dep_list:
        cs = sorted((c for c in idx if c["dep_code"] == d["code"]), key=lambda c: (-c["n_scope"], c["nom"]))
        html, _, _ = render_dep(d, cs, ctx)
        write(root, f"/france/{d['slug']}/", html)
        entries.append((f"{SITE_URL}/france/{d['slug']}/", "daily", "0.8", lastmod))
    for c in cities:
        html, _, _ = render_city(c, ctx)
        html = H.inject(html, H.city_section(c, hist))
        write(root, f"/france/prix-carburant/{c['slug']}/", html)
        if c["indexable"]:
            entries.append((f"{SITE_URL}/france/prix-carburant/{c['slug']}/", "daily", "0.7", lastmod))
    for (f, slug) in sorted(fuel_pages, key=lambda x: (x[1], FUELS.index(x[0]))):
        html, _, _ = render_fuel_page(by_slug[slug], f, ctx)
        html = H.inject(html, H.fuel_section(by_slug[slug], f, hist))
        if not FUEL_PAGES_INDEXABLE:
            marker = '<meta name="robots" content="index, follow">'
            if marker not in html:
                raise SystemExit(f"ERREUR : meta robots introuvable dans la page carburant {slug}/{f}")
            html = html.replace(marker, '<meta name="robots" content="noindex, follow">', 1)
        write(root, f"/france/prix-carburant/{slug}/{FUEL_SLUG[f]}/", html)
        if FUEL_PAGES_INDEXABLE:
            entries.append((f"{SITE_URL}/france/prix-carburant/{slug}/{FUEL_SLUG[f]}/", "daily", "0.6", lastmod))

    # Espagne : pages enrichies (données officielles) quand la source répond
    if es_res:
        for urlpath, html in es_res["pages"]:
            write(root, urlpath, html)
        entries.extend(es_res["entries"])

    # Italie : pages enrichies quand la source répond
    if it_res:
        for urlpath, html in it_res["pages"]:
            write(root, urlpath, html)
        entries.extend(it_res["entries"])

    # Espagne / Italie (repli) : pages historiques + hub
    for pays in ("espagne", "italie"):
        if pays == "espagne" and es_res:
            continue
        if pays == "italie" and it_res:
            continue
        cfg = pays_cfg[pays]
        vs = [v for v in villes if v["pays"] == pays]
        html, _, _ = render_hub_simple(pays, vs, cfg)
        write(root, f"/{pays}/{cfg['dossier']}/", html)
        entries.append((f"{SITE_URL}/{pays}/{cfg['dossier']}/", "monthly", "0.6", None))
        for v in vs:
            write(root, f"/{pays}/{cfg['dossier']}/{v['slug']}/", legacy_page(v, cfg, template))
            entries.append((f"{SITE_URL}/{pays}/{cfg['dossier']}/{v['slug']}/", "monthly", "0.7", None))

    write_sitemap(root, entries)
    H.save(root, hist)
    prune_stale(root)

    # 5) audit + rapport
    aud = audit.audit(root)
    sim = audit.similarity(aud["info"])
    latest_txt = latest.astimezone(__import__("datetime").timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    stats = {"latest_txt": latest_txt, "n_index": len(idx), "n_noindex": len(cities) - len(idx), "fuel_pages": fuel_pages,
             "dep_list": dep_list, "reg_list": reg_list, "cities": cities, "n_stations": len(stations),
             "no_dep": [c["nom"] for c in cities if not c["dep_code"]], "hist_days": sorted(hist["days"]),
             "n_auto": sum(1 for c in cities if c["v"].get("auto")), "es": es_res["info"] if es_res else None, "es_err": es_err,
             "it": it_res["info"] if it_res else None, "it_err": it_err}
    write_report(root, ctx, stats, aud, sim)
    print(f"{len(cities)} villes FR ({len(idx)} indexables), {len(dep_list)} départements, {len(reg_list)} régions, "
          f"{len(fuel_pages)} pages carburant, {len(entries)} URLs au sitemap.")
    print(f"Audit : {len(aud['errors'])} erreur(s), {len(aud['warnings'])} avertissement(s). Rapport : SEO_REPORT.md")
    for e in aud["errors"][:40]:
        print("ERREUR", e)
    return 1 if aud["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
