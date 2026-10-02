"""Rendu des pages Espagne : villes, provinces, hub (textes en espagnol, chiffres issus des données officielles)."""
from datetime import timezone

from geo import fr_price, fr_eur, fr_km, fr_cents, plural, join_fr
from render_common import SITE_URL, esc, rel, breadcrumb, item_list, faq_ld, faq_html, fit_desc, shell
from stats_fr import RADIUS_KM, NEIGHBOR_MAX, commune_ranking

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Madrid")
except Exception:
    _TZ = timezone.utc

PAYS = "espagne"
DOSSIER = "precio-carburante"
BASE = f"/{PAYS}/"
HUB = f"/{PAYS}/{DOSSIER}/"
SOURCE_URL = "https://geoportalgasolineras.es/"
LABEL = {"gazole": "Gasóleo A", "sp95": "Gasolina 95 E5", "e10": "Gasolina 95 E10", "sp98": "Gasolina 98 E5",
         "e85": "Bioetanol (E85)", "gplc": "GLP"}
EL = {"gazole": "el gasóleo A", "sp95": "la gasolina 95 E5", "e10": "la gasolina 95 E10", "sp98": "la gasolina 98 E5",
      "e85": "el bioetanol E85", "gplc": "el GLP"}
DEL = {"gazole": "del gasóleo A", "sp95": "de la gasolina 95 E5", "e10": "de la gasolina 95 E10", "sp98": "de la gasolina 98 E5",
       "e85": "del bioetanol E85", "gplc": "del GLP"}
REF_ORDER = ["gazole", "sp95", "e10", "sp98", "e85", "gplc"]
EUR_L = "&nbsp;€/L"


def ref_fuels(fuels, k=3, min_n=1):
    return [f for f in REF_ORDER if f in fuels and fuels[f]["n"] >= min_n][:k]


def fuel_names(fuels):
    return join_fr([LABEL[f] for f in REF_ORDER if f in fuels], "y")


def fmt_dt(d):
    d = d.astimezone(_TZ)
    return d.strftime("%d/%m/%Y") + " a las " + d.strftime("%H:%M")


def where(c):
    return f"en el municipio de {c['nom']}" if c["scope"] == "commune" else f"en un radio de {RADIUS_KM} km alrededor de {c['nom']}"


def where_short(c):
    return f"en el municipio de {c['nom']}" if c["scope"] == "commune" else f"alrededor de {c['nom']}"


def cmp_phrase(diff):
    if abs(diff) < 0.0005:
        return "prácticamente idéntica"
    word = "superior" if diff > 0 else "inferior"
    return f"{word} en {fr_cents(abs(diff))} {'céntimo' if fr_cents(abs(diff)) == '1,0' else 'céntimos'} por litro"


def label(s):
    adr = s["adr"] or "Dirección no indicada"
    loc = " ".join(x for x in (s["cp"], s["ville"]) if x)
    base = f"{adr}, {loc}" if loc else adr
    return f"{s['brand']} — {base}" if s.get("brand") else base


def bc(cur, items):
    nav, ld = breadcrumb(cur, items)
    return nav.replace("Fil d'Ariane", "Ruta de navegación"), ld


def stations_list(items, cur):
    out = ['<ol class="stations">']
    for price, dist, s in items:
        meta = []
        if dist is not None and dist > 0:
            meta.append(f"a {fr_km(dist)} del centro")
        if s["a24"]:
            meta.append("abierta 24 horas")
        link = f'<a href="https://www.google.com/maps/dir/?api=1&amp;destination={s["lat"]},{s["lon"]}" rel="noopener">Cómo llegar</a>'
        out.append(f'<li><div class="s-top"><span class="s-name">{esc(label(s))}</span><span class="s-price">{fr_price(price)}{EUR_L}</span></div>'
                   f'<div class="s-meta">{esc(" · ".join(meta))}</div><div class="s-links">{link}</div></li>')
    out.append("</ol>")
    return "\n".join(out)


def source_line(latest):
    return (f'<p class="updated">Datos de precios actualizados el {fmt_dt(latest)} (última actualización registrada en el conjunto de datos). '
            f'Precios procedentes de los datos públicos del Ministerio para la Transición Ecológica y el Reto Demográfico, publicados en '
            f'<a href="{SOURCE_URL}" rel="noopener">geoportalgasolineras.es</a>; CarburantRadar no es la fuente original de los precios. '
            f'Las tablas de esta página se recalculan una vez al día.</p>')


def footer(cfg, cur):
    return (f'<h2>{esc(cfg["h2_benefits"])}</h2>\n<ul>\n' + "\n".join(f"<li>{esc(x)}</li>" for x in cfg["benefits"]) + "\n</ul>\n"
            f'<a class="cta-primary" href="{rel(cur, BASE)}">{esc(cfg["cta_final_txt"])}</a>')


def _names(cities, k=10):
    head = [c["nom"] for c in cities[:k]]
    return ", ".join(head) + f" y {len(cities) - k} más" if len(cities) > k else join_fr(head, "y")


# ------------------------------------------------------------------ ciudad

def city_texts(c, ctx):
    nom, F = c["nom"], c["fuels"]
    dep = ctx["dep_info"].get(c["dep_code"])
    nat = ctx["nat"]
    intro = []
    if c["n_rad"] == 0:
        return ([f"El conjunto de datos oficial no registra ninguna gasolinera en un radio de {RADIUS_KM} km alrededor de {nom}: "
                 "no hay precios disponibles para esta zona por ahora."], [], [], [])
    s1 = f"El conjunto de datos oficial registra {plural(c['n_rad'], 'gasolinera', 'gasolineras')} en un radio de {RADIUS_KM} km alrededor de {nom}"
    if c["n_commune"] and c["n_commune"] != c["n_rad"]:
        s1 += f", de las cuales {c['n_commune']} en el propio municipio"
    elif c["n_commune"]:
        s1 += ", todas situadas en el municipio"
    intro.append(s1 + ".")
    if dep:
        reg = dep.get("reg_name")
        intro.append(f"Provincia: {dep['name']}." + (f" Comunidad autónoma: {reg}." if reg else ""))
    if F:
        rf = ref_fuels(F, 1)[0]
        st = F[rf]
        s = (f"{plural(len(F), 'combustible se registra', 'combustibles se registran')}: {fuel_names(F)}. "
             f"Para {EL[rf]}, el precio más bajo es de {fr_price(st['min'])} €/L y el precio medio de {fr_price(st['avg'])} €/L "
             f"sobre {plural(st['n'], 'gasolinera', 'gasolineras')} {where(c)}")
        if st["n"] >= 3 and st["max"] > st["min"]:
            s += f", con una diferencia de {fr_cents(st['max'] - st['min'])} céntimos por litro entre la más barata y la más cara"
        intro.append(s + ".")
    else:
        intro.append("No hay precios disponibles en los datos para esta zona por ahora.")
    nb = c.get("neighbors_shown", [])
    if nb:
        intro.append("Las ciudades cercanas cubiertas por CarburantRadar más próximas son " + join_fr([n["nom"] for n in nb[:3]], "y") + ".")

    comps = []
    for f in ref_fuels(F, 3, min_n=3):
        st = F[f]
        t = (f"{LABEL[f]}: el precio más bajo registrado {where_short(c)} es de {fr_price(st['min'])} €/L, "
             f"frente a una media local de {fr_price(st['avg'])} €/L sobre {st['n']} gasolineras.")
        d = dep["stats"]["fuels"].get(f) if dep else None
        if d and d["n"] >= ctx["min_dep_compare"]:
            t += (f" La media de las gasolineras de la provincia de {dep['name']} es de {fr_price(d['avg'])} €/L ({d['n']} gasolineras): "
                  f"la media local es {cmp_phrase(st['avg'] - d['avg'])}.")
            c.setdefault("compare_dep", True)
        n = nat.get(f)
        if n:
            t += (f" Para el conjunto de gasolineras del conjunto de datos, la media nacional es de {fr_price(n['avg'])} €/L "
                  f"({n['n']} gasolineras); la media local es {cmp_phrase(st['avg'] - n['avg'])}.")
        comps.append(t)

    eco = []
    for f in ref_fuels(F, 2, min_n=3):
        st = F[f]
        gap = round(st["max"] - st["min"], 3)
        if gap > 0:
            eco.append(f"{LABEL[f]}: entre la gasolinera más barata ({fr_price(st['min'])} €/L) y la más cara ({fr_price(st['max'])} €/L) de la zona, "
                       f"la diferencia es de {fr_cents(gap)} céntimos por litro, es decir, {fr_eur(gap * 40)} € en un depósito de 40 L "
                       f"y {fr_eur(gap * 50)} € en uno de 50 L.")

    faq = []
    rf = ref_fuels(F, 1)
    cap = where_short(c)[0].upper() + where_short(c)[1:]
    if rf:
        f = "gazole" if "gazole" in F else rf[0]
        st = F[f]
        faq.append((f"¿Cuál es el precio {DEL[f]} en {nom}?",
                    f"{cap}, {EL[f]} más barato se registra a {fr_price(st['min'])} €/L, con una media de {fr_price(st['avg'])} €/L "
                    f"sobre {plural(st['n'], 'gasolinera', 'gasolineras')}."))
    if F:
        parts = []
        for f in ref_fuels(F, 3):
            p, d, s = F[f]["cheapest"][0]
            parts.append(f"para {EL[f]}, {label(s)} ({fr_price(p)} €/L)")
        faq.append((f"¿Cuál es la gasolinera más barata en {nom}?",
                    f"En los datos actuales, {join_fr(parts, 'y')}. La gasolinera puede variar según el combustible."))
        faq.append((f"¿Qué combustibles hay disponibles en {nom}?",
                    "Se registran precios para: " + join_fr([f"{LABEL[f]} ({plural(F[f]['n'], 'gasolinera', 'gasolineras')})" for f in REF_ORDER if f in F], "y")
                    + f", {where(c)}."))
        faq.append((f"¿Cuántas gasolineras hay alrededor de {nom}?",
                    f"{plural(c['n_rad'], 'gasolinera está registrada', 'gasolineras están registradas')} en un radio de {RADIUS_KM} km"
                    + (f", de las cuales {c['n_commune']} en el municipio" if c["n_commune"] else "") + "."))
        f0 = ref_fuels(F, 2, min_n=3)
        if f0:
            gap = round(F[f0[0]]["max"] - F[f0[0]]["min"], 3)
            if gap > 0:
                faq.append((f"¿Cómo encontrar una gasolinera más barata en {nom}?",
                            f"Compara las gasolineras de la zona con CarburantRadar: para {EL[f0[0]]}, la diferencia entre la más barata y la más cara "
                            f"llega a {fr_cents(gap)} céntimos por litro, es decir, {fr_eur(gap * 40)} € en 40 L, sin contar el desvío para llegar a la gasolinera."))
    return intro, comps, eco, faq


def title_desc_city(c):
    nom, F = c["nom"], c["fuels"]
    t = f"Precio gasolina y diésel en {nom}: gasolineras más baratas" if c["n_scope"] >= 15 else f"Precio del carburante en {nom}: gasolineras y tarifas"
    if len(t) + 17 <= 62:
        t += " | CarburantRadar"
    parts = []
    if F:
        parts.append(f"Compara los precios de {join_fr([LABEL[f] for f in REF_ORDER if f in F], 'y')} en {nom}.")
        parts.append(f"{plural(c['n_scope'], 'gasolinera registrada', 'gasolineras registradas')} {where(c)}.")
        rf = ref_fuels(F, 1)[0]
        parts.append(f"{LABEL[rf]} desde {fr_price(F[rf]['min'])} €/L.")
        parts.append("Consulta las gasolineras más baratas y las tarifas disponibles.")
    else:
        parts.append(f"Precio del carburante en {nom}: los datos de precios no están disponibles para esta zona por ahora.")
    return t, fit_desc(parts)


def render_city(c, ctx):
    cfg, v, nom = ctx["cfg"], c["v"], c["nom"]
    cur = f"{HUB}{c['slug']}/"
    dep = ctx["dep_info"].get(c["dep_code"]) if ctx["dep_pages"].get(c["dep_code"]) else None
    crumbs = [("Inicio", "/"), ("España", BASE)]
    if dep:
        crumbs.append((dep["name"], f"{BASE}{dep['slug']}/"))
    crumbs.append((nom, cur))
    nav, bc_ld = bc(cur, crumbs)
    intro, comps, eco, faq = city_texts(c, ctx)
    title, desc = title_desc_city(c)
    F = c["fuels"]
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f"<h1>Precio del carburante en {esc(nom)}</h1>", f'<div class="subtitle">{esc(cfg["subtitle"])}</div>',
            f'<div class="badges"><div class="badge">{esc(cfg["badge_gratuit"])}</div><div class="badge">{esc(cfg["badge_sans_compte"])}</div>'
            f'<div class="badge">{esc(cfg["badge_donnees"])}</div></div>\n</header>']
    rf = ref_fuels(F, 1)
    if rf:
        p, d, s = F[rf[0]]["cheapest"][0]
        body.append(f'<div class="hero-price"><div class="label">Precio más bajo registrado hoy</div><div class="price">{fr_price(p)} €</div>'
                    f'<div class="fuel">{esc(LABEL[rf[0]])} — el litro más barato {esc(where_short(c))}</div>'
                    f'<div class="station">{esc(label(s))}</div></div>')
    body.append(f'<a class="cta-primary" href="{rel(cur, BASE)}">{esc(cfg["cta_top_txt"])}</a>')

    m = ["<main>", f'<section aria-labelledby="intro"><h2 id="intro">El carburante en {esc(nom)} en cifras</h2>']
    m.extend(f"<p>{esc(t)}</p>" for t in intro)
    if v.get("intro"):
        m.append(f"<p>{esc(v['intro'])}</p>")
    if v.get("why"):
        m.append(f"<p>{esc(v['why'])}</p>")
    m.append("</section>")
    if F:
        rows = []
        for f in REF_ORDER:
            if f in F:
                st = F[f]
                rows.append(f'<tr><th scope="row">{esc(LABEL[f])}</th><td class="min">{fr_price(st["min"])}</td><td>{fr_price(st["avg"])}</td>'
                            f'<td class="max">{fr_price(st["max"])}</td><td>{st["n"]}</td></tr>')
        m.append(f'<section aria-labelledby="resumen"><h2 id="resumen">Resumen de precios en {esc(nom)}</h2><div class="tablewrap"><table>'
                 f'<caption>Precios en €/L de las gasolineras situadas {esc(where(c))}</caption><thead><tr><th scope="col">Combustible</th>'
                 '<th scope="col">Más bajo</th><th scope="col">Medio</th><th scope="col">Más alto</th><th scope="col">Gasolineras</th></tr></thead><tbody>'
                 + "".join(rows) + "</tbody></table></div></section>")
        m.append(f'<section aria-labelledby="baratas"><h2 id="baratas">Las gasolineras más baratas en {esc(nom)}</h2>')
        for f in REF_ORDER:
            if f in F:
                m.append(f"<h3>{esc(LABEL[f])}</h3>")
                m.append(stations_list(F[f]["cheapest"][:3], cur))
        m.append('<p class="note">Los datos oficiales indican la marca (rótulo) y la dirección de cada gasolinera.</p></section>')
        if comps:
            m.append(f'<section aria-labelledby="comparacion"><h2 id="comparacion">Comparación de precios alrededor de {esc(nom)}</h2>')
            m.extend(f"<p>{esc(t)}</p>" for t in comps)
            m.append("</section>")
        if eco:
            m.append(f'<section aria-labelledby="ahorro"><h2 id="ahorro">¿Cuánto se ahorra en un depósito en {esc(nom)}?</h2>')
            m.extend(f"<p>{esc(t)}</p>" for t in eco)
            m.append(f'<p class="note">Esta diferencia es teórica: no incluye el coste del desvío para llegar a la gasolinera más barata, que puede reducir '
                     f'o incluso anular el ahorro. El modo Trayecto de <a href="{rel(cur, BASE)}">la aplicación CarburantRadar</a> equilibra precio y desvío.</p></section>')
    nb = c.get("neighbors_shown", [])
    if nb:
        m.append(f'<section aria-labelledby="cercanas"><h2 id="cercanas">Precio del carburante en las ciudades cercanas a {esc(nom)}</h2><ul class="plain">')
        for n in nb:
            rf2 = ref_fuels(n["fuels"], 1)
            extra = f" · {LABEL[rf2[0]]} desde {fr_price(n['fuels'][rf2[0]]['min'])} €/L" if rf2 else ""
            m.append(f'<li><a href="{rel(cur, HUB + n["slug"] + "/")}">Precio del carburante en {esc(n["nom"])}</a> — a {fr_km(n["dist"])}{esc(extra)}</li>')
        m.append("</ul></section>")
    geo = []
    if dep:
        geo.append(f'<p>Consulta los precios medios de la provincia de <a href="{rel(cur, BASE + dep["slug"] + "/")}">{esc(dep["name"])}</a>.</p>')
    others = c.get("others_dep", [])
    if others:
        geo.append(f'<h3>Otras ciudades de la provincia{" de " + esc(dep["name"]) if dep else ""}</h3><ul class="plain">'
                   + "".join(f'<li><a href="{rel(cur, HUB + o["slug"] + "/")}">Precio del carburante en {esc(o["nom"])}</a></li>' for o in others) + "</ul>")
    geo.append(f'<p><a href="{rel(cur, HUB)}">Todas las ciudades cubiertas en España</a></p>')
    m.append('<section aria-labelledby="geo"><h2 id="geo">Explorar por zona geográfica</h2>' + "\n".join(geo) + "</section>")
    if faq:
        m.append(faq_html(faq, f"Preguntas frecuentes sobre el carburante en {nom}"))
    m.append(source_line(ctx["latest"]))
    m.append("</main>")
    body.extend(m)
    body.append(footer(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    ld = [bc_ld] + ([faq_ld(faq)] if faq else [])
    robots = "index, follow" if c["indexable"] else "noindex, follow"
    return shell(lang="es", title=title, desc=desc, canonical=SITE_URL + cur, robots=robots, cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body))


# ------------------------------------------------------------------ provincia y hub

def _table(st, caption):
    rows = [f'<tr><th scope="row">{esc(LABEL[f])}</th><td class="min">{fr_price(st["fuels"][f]["min"])}</td><td>{fr_price(st["fuels"][f]["avg"])}</td>'
            f'<td class="max">{fr_price(st["fuels"][f]["max"])}</td><td>{st["fuels"][f]["n"]}</td></tr>' for f in REF_ORDER if f in st["fuels"]]
    return (f'<div class="tablewrap"><table><caption>{esc(caption)}</caption><thead><tr><th scope="col">Combustible</th><th scope="col">Más bajo</th>'
            '<th scope="col">Medio</th><th scope="col">Más alto</th><th scope="col">Gasolineras</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def _city_li(cur, c):
    rf = ref_fuels(c["fuels"], 1)
    extra = f" — {LABEL[rf[0]]} desde {fr_price(c['fuels'][rf[0]]['min'])} €/L" if rf else ""
    return (f'<li><a href="{rel(cur, HUB + c["slug"] + "/")}">Precio del carburante en {esc(c["nom"])}</a>'
            f' — {plural(c["n_scope"], "gasolinera", "gasolineras")}{esc(extra)}</li>')


def render_dep(info, cities, ctx):
    cfg = ctx["cfg"]
    cur = f"{BASE}{info['slug']}/"
    nav, bc_ld = bc(cur, [("Inicio", "/"), ("España", BASE), (info["name"], cur)])
    st, F, name = info["stats"], info["stats"]["fuels"], info["name"]
    rf = ref_fuels(F, 1)
    title = f"Precio del carburante en la provincia de {name}: medias y gasolineras"
    if len(title) + 17 <= 66:
        title += " | CarburantRadar"
    intro = [f"El conjunto de datos oficial registra {plural(st['n'], 'gasolinera', 'gasolineras')} en la provincia de {name}"
             + (f" (comunidad autónoma: {info['reg_name']})" if info.get("reg_name") else "") + "."]
    if F and rf:
        intro.append(f"Se registran precios para {fuel_names(F)}. Para {EL[rf[0]]}, el precio más bajo de la provincia es de {fr_price(F[rf[0]]['min'])} €/L "
                     f"y la media de {fr_price(F[rf[0]]['avg'])} €/L sobre {F[rf[0]]['n']} gasolineras.")
    intro.append(f"{plural(len(cities), 'ciudad está cubierta', 'ciudades están cubiertas')} por una página de CarburantRadar en esta provincia: {_names(cities)}.")
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f"<h1>Precio del carburante en la provincia de {esc(name)}</h1>", f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            f'<section aria-labelledby="intro"><h2 id="intro">El carburante en la provincia de {esc(name)} en cifras</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append("</section>")
    if F and rf:
        body.append(f'<section aria-labelledby="precios"><h2 id="precios">Precios por combustible en la provincia de {esc(name)}</h2>'
                    + _table(st, f"Precios en €/L registrados en las gasolineras de la provincia de {name}") + "</section>")
        f0 = rf[0]
        body.append(f'<section aria-labelledby="baratas"><h2 id="baratas">Las gasolineras más baratas de la provincia ({esc(LABEL[f0])})</h2>'
                    + stations_list(F[f0]["cheapest"][:5], cur) + "</section>")
        rk = commune_ranking(info["stations"], f0, min_n=3, top=5)
        if rk:
            body.append(f'<section aria-labelledby="municipios"><h2 id="municipios">Municipios donde {EL[f0]} es más barato de media</h2>'
                        f'<p class="note">Municipios de la provincia con al menos 3 gasolineras con precio de {LABEL[f0]}, ordenados por precio medio.</p><ul class="plain">'
                        + "".join(f"<li>{esc(n)} — {fr_price(avg)} €/L de media ({k} gasolineras)</li>" for avg, _, n, k in rk) + "</ul></section>")
    body.append(f'<section aria-labelledby="ciudades"><h2 id="ciudades">Ciudades de la provincia de {esc(name)} cubiertas por CarburantRadar</h2><ul class="plain">'
                + "".join(_city_li(cur, c) for c in cities)
                + f'</ul><p><a href="{rel(cur, HUB)}">Todas las ciudades cubiertas en España</a></p></section>')
    faq = []
    if rf:
        f0 = rf[0]
        s0 = F[f0]
        p, d, s = s0["cheapest"][0]
        faq.append((f"¿Cuál es el precio medio {DEL[f0]} en la provincia de {name}?",
                    f"Según el conjunto de datos oficial, la media {DEL[f0]} es de {fr_price(s0['avg'])} €/L sobre {s0['n']} gasolineras, "
                    f"con un mínimo de {fr_price(s0['min'])} €/L y un máximo de {fr_price(s0['max'])} €/L."))
        faq.append((f"¿Dónde está la gasolinera más barata de la provincia de {name}?",
                    f"Para {EL[f0]}, la gasolinera más barata registrada es {label(s)}, a {fr_price(p)} €/L."))
    faq.append((f"¿Cuántas gasolineras tiene la provincia de {name}?",
                f"{plural(st['n'], 'gasolinera está registrada', 'gasolineras están registradas')} en el conjunto de datos oficial para esta provincia."))
    body.append(faq_html(faq, f"Preguntas frecuentes: carburante en la provincia de {name}"))
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(footer(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Precio del carburante en la provincia de {name}: {plural(st['n'], 'gasolinera registrada', 'gasolineras registradas')}.",
                     (f"{LABEL[rf[0]]} desde {fr_price(F[rf[0]]['min'])} €/L, media {fr_price(F[rf[0]]['avg'])} €/L." if rf else ""),
                     "Gasolineras más baratas y ciudades cubiertas."])
    ld = [bc_ld, faq_ld(faq), item_list(f"Ciudades de la provincia de {name}", [(f"Precio del carburante en {c['nom']}", HUB + c["slug"] + "/") for c in cities])]
    return shell(lang="es", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body))


def render_hub(ctx, cities_idx, dep_list):
    cfg = ctx["cfg"]
    cur = HUB
    nav, bc_ld = bc(cur, [("Inicio", "/"), ("España", BASE), ("Precio por ciudad", cur)])
    nat = ctx["nat"]
    title = "Precio del carburante por ciudad en España: todas las ciudades"
    intro = [f"CarburantRadar detalla el precio del carburante en {plural(len(cities_idx), 'ciudad española', 'ciudades españolas')}, a partir de los datos públicos del Ministerio para la Transición Ecológica y el Reto Demográfico."]
    rf = [f for f in REF_ORDER if f in nat][:1]
    if rf:
        n = nat[rf[0]]
        intro.append(f"En el conjunto de datos, {EL[rf[0]]} se registra de media a {fr_price(n['avg'])} €/L ({n['n']} gasolineras), con un mínimo de {fr_price(n['min'])} €/L.")
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            "<h1>Precio del carburante por ciudad en España</h1>", f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            '<section aria-labelledby="intro"><h2 id="intro">Elige tu ciudad</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append("</section>")
    by_dep = {}
    for c in cities_idx:
        by_dep.setdefault(c["dep_code"] if ctx["dep_pages"].get(c["dep_code"]) else None, []).append(c)
    body.append('<section aria-labelledby="provincias"><h2 id="provincias">Ciudades por provincia</h2>')
    for d in dep_list:
        lst = by_dep.get(d["code"], [])
        if lst:
            body.append(f'<h3><a href="{rel(cur, BASE + d["slug"] + "/")}">{esc(d["name"])}</a></h3><ul class="plain">'
                        + "".join(f'<li><a href="{rel(cur, HUB + c["slug"] + "/")}">Precio del carburante en {esc(c["nom"])}</a></li>' for c in lst) + "</ul>")
    if by_dep.get(None):
        body.append('<h3>Otras ciudades</h3><ul class="plain">'
                    + "".join(f'<li><a href="{rel(cur, HUB + c["slug"] + "/")}">Precio del carburante en {esc(c["nom"])}</a></li>' for c in by_dep[None]) + "</ul>")
    body.append("</section>")
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(footer(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Precio del carburante en {plural(len(cities_idx), 'ciudad', 'ciudades')} de España: gasóleo, gasolina 95 y 98, GLP.",
                     "Elige tu ciudad o tu provincia y compara las gasolineras más baratas."])
    top = sorted(cities_idx, key=lambda c: (-c["n_scope"], c["nom"]))[:100]
    ld = [bc_ld, item_list("Principales ciudades españolas cubiertas", [(f"Precio del carburante en {c['nom']}", HUB + c["slug"] + "/") for c in top])]
    return shell(lang="es", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body))
