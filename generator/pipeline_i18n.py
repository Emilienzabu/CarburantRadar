"""Construction des pages d'un pays étranger (Espagne, puis Italie) : mêmes règles de qualité que la France.

Réutilise stats_fr (statistiques, score d'indexation, voisines) et communes_auto (découverte des communes),
avec le module de rendu du pays (render_es, ...). Ne touche pas au disque : renvoie les pages et les entrées de sitemap.
"""
import datetime as dt

import communes_auto
import stats_fr as S


def build_country(R, cfg, legacy, stations, latest, prev_slugs):
    nat = S.national(stations)
    dep_info, reg_info = S.build_geo(stations)
    for d in dep_info.values():
        if d["slug"] == R.DOSSIER:
            d["slug"] += "-provincia"
        rn = reg_info.get(d["reg_code"])
        d["reg_name"] = rn["name"] if rn else ""
    auto = communes_auto.discover(stations, legacy, prev_slugs, pays=R.PAYS,
                                  dep_label=lambda code: dep_info[code]["name"] if code in dep_info else code)
    cities = [communes_auto.build_city(v, stations) if v.get("auto") else S.build_city(v, stations) for v in legacy + auto]
    by_slug = {c["slug"]: c for c in cities}
    cand = S.neighbor_candidates(cities)
    for c in cities:
        viable = lambda o: o["n_scope"] >= S.MIN_STATIONS_INDEX and len(o["fuels"]) >= S.MIN_FUELS_INDEX
        c["neighbors"] = [(d, s) for d, s in cand[c["slug"]] if viable(by_slug[s])]
        dep = dep_info.get(c["dep_code"])
        c["compare_dep"] = bool(dep) and any(f in dep["stats"]["fuels"] and dep["stats"]["fuels"][f]["n"] >= S.MIN_DEP_COMPARE
                                             and c["fuels"][f]["n"] >= 3 for f in c["fuels"])
        S.score_city(c, dep_info, nat)
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
    dep_pages = {}
    for code, d in dep_info.items():
        if any(c["dep_code"] == code for c in idx) and d["stats"]["n"] >= S.MIN_DEP_STATIONS:
            dep_pages[code] = True
    dep_list = [dep_info[k] for k in sorted(dep_pages, key=lambda k: dep_info[k]["name"])]
    ctx = {"cfg": cfg, "dep_info": dep_info, "dep_pages": dep_pages, "nat": nat, "latest": latest, "min_dep_compare": S.MIN_DEP_COMPARE}

    lastmod = latest.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")
    base, hub = R.BASE, R.HUB
    site = "https://emilienzabu.github.io/CarburantRadar"
    pages, entries = [], []
    pages.append((hub, R.render_hub(ctx, sorted(idx, key=lambda c: c["nom"]), dep_list)))
    entries.append((site + hub, "weekly", "0.9", lastmod))
    for d in dep_list:
        cs = sorted((c for c in idx if c["dep_code"] == d["code"]), key=lambda c: (-c["n_scope"], c["nom"]))
        pages.append((f"{base}{d['slug']}/", R.render_dep(d, cs, ctx)))
        entries.append((f"{site}{base}{d['slug']}/", "daily", "0.8", lastmod))
    for c in cities:
        pages.append((f"{hub}{c['slug']}/", R.render_city(c, ctx)))
        if c["indexable"]:
            entries.append((f"{site}{hub}{c['slug']}/", "daily", "0.7", lastmod))
    info = {"n_stations": len(stations), "n_cities": len(cities), "n_index": len(idx), "n_auto": sum(1 for c in cities if c["v"].get("auto")),
            "n_dep": len(dep_list), "latest": latest}
    return {"pages": pages, "entries": entries, "info": info, "cities": cities}
