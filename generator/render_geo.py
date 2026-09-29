"""Pages départements, régions et hubs (France ; Espagne/Italie : hubs simples)."""
from data_fr import FUELS, FUEL_LABEL
from geo import fr_price, fr_cents, plural, join_fr
from render_common import (SITE_URL, esc, rel, breadcrumb, item_list, faq_ld, faq_html, fit_desc, shell, jsonld)
from render_fr import (FUEL_LE, FUEL_DE, REF_ORDER, ref_fuels, source_line, stations_list, footer_boilerplate,
                       a_ville, fmt_dt)
from stats_fr import commune_ranking, pretty


def _table(stats, caption):
    rows = []
    for f in FUELS:
        st = stats["fuels"].get(f)
        if st:
            rows.append(f'<tr><th scope="row">{esc(FUEL_LABEL[f])}</th><td class="min">{fr_price(st["min"])}</td><td>{fr_price(st["avg"])}</td>'
                        f'<td class="max">{fr_price(st["max"])}</td><td>{st["n"]}</td></tr>')
    return (f'<div class="tablewrap"><table><caption>{esc(caption)}</caption><thead><tr><th scope="col">Carburant</th>'
            '<th scope="col">Le plus bas</th><th scope="col">Moyen</th><th scope="col">Le plus haut</th><th scope="col">Stations</th></tr></thead>'
            "<tbody>" + "".join(rows) + "</tbody></table></div>")


def _city_li(cur, c):
    rf = ref_fuels(c["fuels"], 1)
    extra = f" — {FUEL_LABEL[rf[0]]} dès {fr_price(c['fuels'][rf[0]]['min'])} €/L" if rf else ""
    return (f'<li><a href="{rel(cur, "/france/prix-carburant/" + c["slug"] + "/")}">Prix du carburant {esc(a_ville(c["nom"]))}</a>'
            f' — {plural(c["n_scope"], "station", "stations")}{esc(extra)}</li>')


def render_dep(info, cities, ctx):
    cfg = ctx["cfg"]
    cur = f"/france/{info['slug']}/"
    reg = ctx["reg_info"].get(info["reg_code"]) if ctx["reg_pages"].get(info["reg_code"]) else None
    crumbs = [("Accueil", "/"), ("France", "/france/")]
    if reg:
        crumbs.append((reg["name"], f"/france/{reg['slug']}/"))
    crumbs.append((info["name"], cur))
    nav, bc_ld = breadcrumb(cur, crumbs)
    st = info["stats"]
    F = st["fuels"]
    rf = ref_fuels(F, 1)
    name = info["name"]
    regname = ctx["reg_info"][info["reg_code"]]["name"] if info["reg_code"] in ctx["reg_info"] else None
    title = f"Prix du carburant département {name} ({info['code']}) : moyennes et stations"
    if len(title) + 17 <= 66:
        title += " | CarburantRadar"
    intro = [f"Le jeu de données officiel référence {plural(st['n'], 'station-service', 'stations-service')} dans le département {name} ({info['code']})"
             + (f", en région {regname}" if regname else "") + "."]
    if F:
        intro.append(f"Des prix sont relevés pour {join_fr([FUEL_LABEL[f] for f in FUELS if f in F])}. "
                     + (f"Pour {FUEL_LE[rf[0]]}, le prix le plus bas du département est de {fr_price(F[rf[0]]['min'])} €/L et la moyenne de "
                        f"{fr_price(F[rf[0]]['avg'])} €/L sur {F[rf[0]]['n']} stations." if rf else ""))
    intro.append(f"{plural(len(cities), 'ville est couverte', 'villes sont couvertes')} par une page CarburantRadar dans ce département : "
                 + join_fr([c["nom"] for c in cities]) + ".")
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f'<h1>Prix du carburant dans le département {esc(name)}</h1>',
            f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            f'<section aria-labelledby="intro"><h2 id="intro">Le carburant dans le département {esc(name)} en chiffres</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append("</section>")
    if F:
        body.append(f'<section aria-labelledby="prix"><h2 id="prix">Prix par carburant dans le département {esc(name)}</h2>'
                    + _table(st, f"Prix en €/L relevés dans les stations du département {name}") + "</section>")
        f0 = rf[0]
        body.append(f'<section aria-labelledby="stations"><h2 id="stations">Les stations les moins chères du département ({esc(FUEL_LABEL[f0])})</h2>'
                    + stations_list(F[f0]["cheapest"][:5], cur, f0)
                    + '<p class="note">Le jeu de données officiel ne mentionne ni le nom ni l\'enseigne des stations : elles sont identifiées par leur adresse.</p></section>')
        rk = commune_ranking(info["stations"], f0, min_n=3, top=5)
        if rk:
            body.append(f'<section aria-labelledby="communes"><h2 id="communes">Communes où {FUEL_LE[f0]} est le moins cher en moyenne</h2>'
                        f'<p class="note">Communes du département comptant au moins 3 stations avec un prix {FUEL_DE[f0]}, classées par prix moyen.</p><ul class="plain">'
                        + "".join(f"<li>{esc(n)} — {fr_price(avg)} €/L en moyenne ({k} stations)</li>" for avg, _, n, k in rk) + "</ul></section>")
    body.append(f'<section aria-labelledby="villes"><h2 id="villes">Villes du département {esc(name)} couvertes par CarburantRadar</h2><ul class="plain">'
                + "".join(_city_li(cur, c) for c in cities) + "</ul>")
    if reg:
        body.append(f'<p>Voir aussi la région <a href="{rel(cur, "/france/" + reg["slug"] + "/")}">{esc(reg["name"])}</a> et '
                    f'<a href="{rel(cur, "/france/prix-carburant/")}">toutes les villes couvertes en France</a>.</p>')
    body.append("</section>")
    faq = []
    if rf:
        f0 = rf[0]
        s0 = F[f0]
        faq.append((f"Quel est le prix moyen {FUEL_DE[f0]} dans le département {name} ?",
                    f"D'après le jeu de données officiel, la moyenne {FUEL_DE[f0]} est de {fr_price(s0['avg'])} €/L sur {s0['n']} stations, "
                    f"avec un minimum de {fr_price(s0['min'])} €/L et un maximum de {fr_price(s0['max'])} €/L."))
        p, d, s = s0["cheapest"][0]
        from stats_fr import label
        faq.append((f"Où est la station la moins chère dans le département {name} ?",
                    f"Pour {FUEL_LE[f0]}, la station la moins chère relevée est {label(s)}, à {fr_price(p)} €/L."))
    faq.append((f"Combien de stations-service compte le département {name} ?",
                f"{plural(st['n'], 'station est référencée', 'stations sont référencées')} dans le jeu de données officiel pour ce département."))
    faq.append((f"Quelles villes du département {name} sont couvertes ?",
                "Les pages CarburantRadar existent pour : " + join_fr([c["nom"] for c in cities]) + "."))
    body.append(faq_html(faq, f"Questions fréquentes : carburant dans le département {name}"))
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(footer_boilerplate(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Prix du carburant dans le département {name} ({info['code']}) : {plural(st['n'], 'station', 'stations')} référencées.",
                     (f"{FUEL_LABEL[rf[0]]} dès {fr_price(F[rf[0]]['min'])} €/L, moyenne {fr_price(F[rf[0]]['avg'])} €/L." if rf else ""),
                     "Stations les moins chères et villes couvertes."])
    ld = [bc_ld, faq_ld(faq), item_list(f"Villes du département {name}", [(f"Prix du carburant {a_ville(c['nom'])}", "/france/prix-carburant/" + c["slug"] + "/") for c in cities])]
    return shell(lang="fr", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body)), title, desc


def render_region(info, deps, cities, ctx):
    cfg = ctx["cfg"]
    cur = f"/france/{info['slug']}/"
    nav, bc_ld = breadcrumb(cur, [("Accueil", "/"), ("France", "/france/"), (info["name"], cur)])
    st = info["stats"]
    F = st["fuels"]
    rf = ref_fuels(F, 1)
    name = info["name"]
    title = f"Prix du carburant région {name} : moyennes par département"
    if len(title) + 17 <= 66:
        title += " | CarburantRadar"
    intro = [f"Le jeu de données officiel référence {plural(st['n'], 'station-service', 'stations-service')} dans la région {name}."]
    if rf:
        intro.append(f"Pour {FUEL_LE[rf[0]]}, le prix le plus bas de la région est de {fr_price(F[rf[0]]['min'])} €/L et la moyenne de "
                     f"{fr_price(F[rf[0]]['avg'])} €/L sur {F[rf[0]]['n']} stations.")
    intro.append(f"{plural(len(deps), 'département est détaillé', 'départements sont détaillés')} sur CarburantRadar : {join_fr([d['name'] for d in deps])}.")
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f'<h1>Prix du carburant en région {esc(name)}</h1>',
            f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            f'<section aria-labelledby="intro"><h2 id="intro">Le carburant en région {esc(name)} en chiffres</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append("</section>")
    if F:
        body.append(f'<section aria-labelledby="prix"><h2 id="prix">Prix par carburant dans la région {esc(name)}</h2>'
                    + _table(st, f"Prix en €/L relevés dans les stations de la région {name}") + "</section>")
    f0 = rf[0] if rf else None
    body.append(f'<section aria-labelledby="deps"><h2 id="deps">Départements de la région {esc(name)}</h2><ul class="plain">')
    for d in deps:
        s0 = d["stats"]["fuels"].get(f0) if f0 else None
        extra = f" — {FUEL_LABEL[f0]} en moyenne {fr_price(s0['avg'])} €/L" if s0 else ""
        body.append(f'<li><a href="{rel(cur, "/france/" + d["slug"] + "/")}">Prix du carburant département {esc(d["name"])} ({esc(d["code"])})</a>'
                    f' — {plural(d["stats"]["n"], "station", "stations")}{esc(extra)}</li>')
    body.append("</ul></section>")
    if cities:
        body.append(f'<section aria-labelledby="villes"><h2 id="villes">Villes couvertes de la région {esc(name)}</h2><ul class="plain">'
                    + "".join(_city_li(cur, c) for c in cities) + "</ul></section>")
    faq = []
    if rf:
        s0 = F[f0]
        faq.append((f"Quel est le prix moyen {FUEL_DE[f0]} en région {name} ?",
                    f"D'après le jeu de données officiel, la moyenne {FUEL_DE[f0]} est de {fr_price(s0['avg'])} €/L sur {s0['n']} stations, "
                    f"avec un minimum de {fr_price(s0['min'])} €/L."))
    faq.append((f"Combien de stations-service compte la région {name} ?",
                f"{plural(st['n'], 'station est référencée', 'stations sont référencées')} dans le jeu de données officiel."))
    body.append(faq_html(faq, f"Questions fréquentes : carburant en région {name}"))
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(footer_boilerplate(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Prix du carburant en région {name} : {plural(st['n'], 'station', 'stations')} référencées.",
                     (f"{FUEL_LABEL[f0]} dès {fr_price(F[f0]['min'])} €/L, moyenne {fr_price(F[f0]['avg'])} €/L." if rf else ""),
                     "Moyennes par département et villes couvertes."])
    ld = [bc_ld, faq_ld(faq), item_list(f"Départements de la région {name}", [(f"Département {d['name']}", "/france/" + d["slug"] + "/") for d in deps])]
    return shell(lang="fr", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body)), title, desc


def render_hub_fr(ctx, cities_idx, dep_pages_list, reg_pages_list):
    cfg = ctx["cfg"]
    cur = "/france/prix-carburant/"
    nav, bc_ld = breadcrumb(cur, [("Accueil", "/"), ("France", "/france/"), ("Prix par ville", cur)])
    nat = ctx["nat"]
    title = "Prix du carburant par ville en France : toutes les villes couvertes"
    intro = [f"CarburantRadar détaille les prix du carburant pour {plural(len(cities_idx), 'ville française', 'villes françaises')}, à partir des données publiques du gouvernement.",
             ]
    if nat:
        rf = [f for f in REF_ORDER if f in nat][:1]
        if rf:
            intro.append(f"Sur l'ensemble du jeu de données, {FUEL_LE[rf[0]]} est relevé en moyenne à {fr_price(nat[rf[0]]['avg'])} €/L "
                         f"({nat[rf[0]]['n']} stations), avec un minimum à {fr_price(nat[rf[0]]['min'])} €/L.")
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            "<h1>Prix du carburant par ville en France</h1>",
            f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            '<section aria-labelledby="intro"><h2 id="intro">Choisissez votre ville</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append("</section>")
    by_reg = {}
    for c in cities_idx:
        by_reg.setdefault(c["reg_code"] if ctx["reg_pages"].get(c["reg_code"]) else None, []).append(c)
    for rinfo in reg_pages_list:
        lst = by_reg.get(rinfo["code"], [])
        if not lst:
            continue
        body.append(f'<section><h2><a href="{rel(cur, "/france/" + rinfo["slug"] + "/")}">{esc(rinfo["name"])}</a></h2>')
        by_dep = {}
        for c in lst:
            by_dep.setdefault(c["dep_code"] if ctx["dep_pages"].get(c["dep_code"]) else None, []).append(c)
        for dinfo in [d for d in dep_pages_list if d["code"] in by_dep]:
            body.append(f'<h3><a href="{rel(cur, "/france/" + dinfo["slug"] + "/")}">{esc(dinfo["name"])}</a></h3><ul class="plain">'
                        + "".join(f'<li><a href="{rel(cur, "/france/prix-carburant/" + c["slug"] + "/")}">Prix du carburant {esc(a_ville(c["nom"]))}</a></li>' for c in by_dep[dinfo["code"]])
                        + "</ul>")
        if None in by_dep:
            body.append("<h3>Autres villes de la région</h3><ul class=\"plain\">"
                        + "".join(f'<li><a href="{rel(cur, "/france/prix-carburant/" + c["slug"] + "/")}">Prix du carburant {esc(a_ville(c["nom"]))}</a></li>' for c in by_dep[None]) + "</ul>")
        body.append("</section>")
    rest = by_reg.get(None, [])
    if rest:
        body.append('<section><h2>Autres villes</h2><ul class="plain">'
                    + "".join(f'<li><a href="{rel(cur, "/france/prix-carburant/" + c["slug"] + "/")}">Prix du carburant {esc(a_ville(c["nom"]))}</a></li>' for c in rest) + "</ul></section>")
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(footer_boilerplate(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Prix du carburant dans {plural(len(cities_idx), 'ville', 'villes')} de France : gazole, SP95, SP98, E10, E85 et GPL.",
                     "Choisissez votre ville, votre département ou votre région pour voir les stations les moins chères."])
    webapp = jsonld({"@context": "https://schema.org", "@type": "WebApplication", "name": "CarburantRadar",
                     "url": SITE_URL + "/france/", "applicationCategory": "UtilitiesApplication", "operatingSystem": "Web",
                     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}})
    ld = [bc_ld, webapp, item_list("Villes françaises couvertes", [(f"Prix du carburant {a_ville(c['nom'])}", "/france/prix-carburant/" + c["slug"] + "/") for c in cities_idx])]
    return shell(lang="fr", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body)), title, desc


HUB_TXT = {
    "espagne": dict(lang="es", dossier="precio-carburante", nom="España", home="Inicio", h1="Precio del carburante por ciudad en España",
                    title="Precio del carburante por ciudad en España: todas las ciudades", link="Precio del carburante en {ville}",
                    intro="CarburantRadar ofrece el precio del carburante en {n} ciudades españolas. Elige tu ciudad para ver las gasolineras más baratas.",
                    desc="Precio del carburante en {n} ciudades de España: gasóleo, gasolina 95 y 98, GLP. Elige tu ciudad y compara las gasolineras.", h2="Elige tu ciudad"),
    "italie": dict(lang="it", dossier="prezzo-carburante", nom="Italia", home="Home", h1="Prezzo del carburante per città in Italia",
                   title="Prezzo del carburante per città in Italia: tutte le città", link="Prezzo del carburante a {ville}",
                   intro="CarburantRadar mostra il prezzo del carburante in {n} città italiane. Scegli la tua città per vedere i distributori più economici.",
                   desc="Prezzo del carburante in {n} città italiane: benzina, gasolio, GPL, metano. Scegli la tua città e confronta i distributori.", h2="Scegli la tua città"),
}


def render_hub_simple(pays, villes, cfg):
    t = HUB_TXT[pays]
    base = f"/{pays}/"
    cur = f"/{pays}/{t['dossier']}/"
    nav, bc_ld = breadcrumb(cur, [(t["home"], "/"), (t["nom"], base), (t["h1"], cur)])
    n = len(villes)
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f'<h1>{esc(t["h1"])}</h1>\n<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            f'<section aria-labelledby="villes"><h2 id="villes">{esc(t["h2"])}</h2><p>{esc(t["intro"].format(n=n))}</p><ul class="plain">']
    for v in sorted(villes, key=lambda x: x["nom"]):
        body.append(f'<li><a href="{rel(cur, cur + v["slug"] + "/")}">{esc(t["link"].format(ville=v["nom"]))}</a></li>')
    body.append("</ul></section>\n</main>")
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = t["desc"].format(n=n)
    ld = [bc_ld, item_list(t["h1"], [(t["link"].format(ville=v["nom"]), cur + v["slug"] + "/") for v in sorted(villes, key=lambda x: x["nom"])])]
    return shell(lang=t["lang"], title=t["title"], desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body)), t["title"], desc
