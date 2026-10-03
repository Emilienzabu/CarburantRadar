"""Rendu des pages Italie : villes, provinces, hub (textes en italien, chiffres issus des données officielles)."""
from datetime import timezone

from geo import fr_price, fr_eur, fr_km, fr_cents, plural, join_fr
from render_common import SITE_URL, esc, rel, breadcrumb, item_list, faq_ld, faq_html, fit_desc, shell
from stats_fr import RADIUS_KM, commune_ranking

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Rome")
except Exception:
    _TZ = timezone.utc

PAYS = "italie"
DOSSIER = "prezzo-carburante"
BASE = f"/{PAYS}/"
HUB = f"/{PAYS}/{DOSSIER}/"
SOURCE_URL = "https://carburanti.mise.gov.it/"
LABEL = {"gazole": "Gasolio", "sp95": "Benzina", "gplc": "GPL", "e85": "Metano (€/kg)", "e10": "E10", "sp98": "SP98"}
EL = {"gazole": "il gasolio", "sp95": "la benzina", "gplc": "il GPL", "e85": "il metano", "e10": "l'E10", "sp98": "la SP98"}
DEL = {"gazole": "del gasolio", "sp95": "della benzina", "gplc": "del GPL", "e85": "del metano", "e10": "dell'E10", "sp98": "della SP98"}
REF_ORDER = ["gazole", "sp95", "gplc", "e85"]
COMP_ORDER = ["gazole", "sp95", "gplc"]       # carburants comparables (au litre) pour les textes de comparaison et d'économie
EUR_L = "&nbsp;€/L"
EUR_KG = "&nbsp;€/kg"


def unit(f):
    return "€/kg" if f == "e85" else "€/L"


def per(f):
    return "al chilo" if f == "e85" else "al litro"


def ref_fuels(fuels, k=3, min_n=1, order=REF_ORDER):
    return [f for f in order if f in fuels and fuels[f]["n"] >= min_n][:k]


def fuel_names(fuels):
    return join_fr([LABEL[f] for f in REF_ORDER if f in fuels], "e")


def a_(nom):
    return ("ad " if nom[:1].lower() == "a" else "a ") + nom


def fmt_dt(d):
    d = d.astimezone(_TZ)
    return d.strftime("%d/%m/%Y") + " alle " + d.strftime("%H:%M")


def where(c):
    return f"nel comune di {c['nom']}" if c["scope"] == "commune" else f"in un raggio di {RADIUS_KM} km intorno a {c['nom']}"


def where_short(c):
    return f"nel comune di {c['nom']}" if c["scope"] == "commune" else f"intorno a {c['nom']}"


def cmp_phrase(diff):
    if abs(diff) < 0.0005:
        return "praticamente identica"
    word = "superiore" if diff > 0 else "inferiore"
    return f"{word} di {fr_cents(abs(diff))} {'centesimo' if fr_cents(abs(diff)) == '1,0' else 'centesimi'} al litro"


def label(s):
    adr = s["adr"] or "Indirizzo non indicato"
    base = f"{adr}, {s['ville']}" if s["ville"] else adr
    return f"{s['brand']} — {base}" if s.get("brand") else base


def bc(cur, items):
    nav, ld = breadcrumb(cur, items)
    return nav.replace("Fil d'Ariane", "Percorso di navigazione"), ld


def stations_list(items, cur, f):
    out = ['<ol class="stations">']
    eur = EUR_KG if f == "e85" else EUR_L
    for price, dist, s in items:
        meta = []
        if dist is not None and dist > 0:
            meta.append(f"a {fr_km(dist)} dal centro")
        link = f'<a href="https://www.google.com/maps/dir/?api=1&amp;destination={s["lat"]},{s["lon"]}" rel="noopener">Come arrivare</a>'
        out.append(f'<li><div class="s-top"><span class="s-name">{esc(label(s))}</span><span class="s-price">{fr_price(price)}{eur}</span></div>'
                   f'<div class="s-meta">{esc(" · ".join(meta))}</div><div class="s-links">{link}</div></li>')
    out.append("</ol>")
    return "\n".join(out)


def source_line(latest):
    return (f'<p class="updated">Dati dei prezzi aggiornati il {fmt_dt(latest)} (ultimo aggiornamento registrato nel dataset). '
            f'Prezzi provenienti dai dati pubblici del Ministero delle Imprese e del Made in Italy (MIMIT), Osservatorio prezzi carburanti, '
            f'consultabili su <a href="{SOURCE_URL}" rel="noopener">carburanti.mise.gov.it</a>; CarburantRadar non è la fonte originale dei prezzi. '
            f'Per ogni carburante si usa il prezzo self-service quando è disponibile, altrimenti il prezzo servito. '
            f'Le tabelle di questa pagina vengono ricalcolate una volta al giorno.</p>')


def footer(cfg, cur):
    return (f'<h2>{esc(cfg["h2_benefits"])}</h2>\n<ul>\n' + "\n".join(f"<li>{esc(x)}</li>" for x in cfg["benefits"]) + "\n</ul>\n"
            f'<a class="cta-primary" href="{rel(cur, BASE)}">{esc(cfg["cta_final_txt"])}</a>')


def _names(cities, k=10):
    head = [c["nom"] for c in cities[:k]]
    return ", ".join(head) + f" e altre {len(cities) - k}" if len(cities) > k else join_fr(head, "e")


# ------------------------------------------------------------------ città

def city_texts(c, ctx):
    nom, F = c["nom"], c["fuels"]
    dep = ctx["dep_info"].get(c["dep_code"])
    nat = ctx["nat"]
    intro = []
    if c["n_rad"] == 0:
        return ([f"Il dataset ufficiale non registra alcun distributore in un raggio di {RADIUS_KM} km intorno a {nom}: "
                 "al momento non ci sono prezzi disponibili per questa zona."], [], [], [])
    s1 = f"Il dataset ufficiale registra {plural(c['n_rad'], 'distributore', 'distributori')} in un raggio di {RADIUS_KM} km intorno a {nom}"
    if c["n_commune"] and c["n_commune"] != c["n_rad"]:
        s1 += f", di cui {c['n_commune']} nel comune stesso"
    elif c["n_commune"]:
        s1 += ", tutti situati nel comune"
    intro.append(s1 + ".")
    if dep:
        intro.append(f"Provincia: {dep['name']} ({dep['code']}).")
    if F:
        rf = ref_fuels(F, 1)[0]
        st = F[rf]
        s = (f"{plural(len(F), 'carburante è rilevato', 'carburanti sono rilevati')}: {fuel_names(F)}. "
             f"Per {EL[rf]}, il prezzo più basso è di {fr_price(st['min'])} {unit(rf)} e il prezzo medio di {fr_price(st['avg'])} {unit(rf)} "
             f"su {plural(st['n'], 'distributore', 'distributori')} {where(c)}")
        if st["n"] >= 3 and st["max"] > st["min"]:
            s += f", con una differenza di {fr_cents(st['max'] - st['min'])} centesimi {per(rf)} tra il più economico e il più caro"
        intro.append(s + ".")
    else:
        intro.append("Al momento non ci sono prezzi disponibili nei dati per questa zona.")
    nb = c.get("neighbors_shown", [])
    if nb:
        intro.append("Le città vicine coperte da CarburantRadar più vicine sono " + join_fr([n["nom"] for n in nb[:3]], "e") + ".")

    comps = []
    for f in ref_fuels(F, 3, min_n=3, order=COMP_ORDER):
        st = F[f]
        t = (f"{LABEL[f]}: il prezzo più basso rilevato {where_short(c)} è di {fr_price(st['min'])} €/L, "
             f"contro una media locale di {fr_price(st['avg'])} €/L su {st['n']} distributori.")
        d = dep["stats"]["fuels"].get(f) if dep else None
        if d and d["n"] >= ctx["min_dep_compare"]:
            t += (f" La media dei distributori della provincia di {dep['name']} è di {fr_price(d['avg'])} €/L ({d['n']} distributori): "
                  f"la media locale è {cmp_phrase(st['avg'] - d['avg'])}.")
        n = nat.get(f)
        if n:
            t += (f" Su tutti i distributori del dataset, la media nazionale è di {fr_price(n['avg'])} €/L "
                  f"({n['n']} distributori); la media locale è {cmp_phrase(st['avg'] - n['avg'])}.")
        comps.append(t)

    eco = []
    for f in ref_fuels(F, 2, min_n=3, order=COMP_ORDER):
        st = F[f]
        gap = round(st["max"] - st["min"], 3)
        if gap > 0:
            eco.append(f"{LABEL[f]}: tra il distributore più economico ({fr_price(st['min'])} €/L) e il più caro ({fr_price(st['max'])} €/L) della zona, "
                       f"la differenza è di {fr_cents(gap)} centesimi al litro, cioè {fr_eur(gap * 40)} € su un pieno da 40 L "
                       f"e {fr_eur(gap * 50)} € su uno da 50 L.")

    faq = []
    rf = ref_fuels(F, 1)
    cap = where_short(c)[0].upper() + where_short(c)[1:]
    if rf:
        f = "gazole" if "gazole" in F else rf[0]
        st = F[f]
        faq.append((f"Qual è il prezzo {DEL[f]} {a_(nom)}?",
                    f"{cap}, {EL[f]} più economico è rilevato a {fr_price(st['min'])} {unit(f)}, con una media di {fr_price(st['avg'])} {unit(f)} "
                    f"su {plural(st['n'], 'distributore', 'distributori')}."))
    if F:
        parts = []
        for f in ref_fuels(F, 3):
            p, d, s = F[f]["cheapest"][0]
            parts.append(f"per {EL[f]}, {label(s)} ({fr_price(p)} {unit(f)})")
        faq.append((f"Qual è il distributore più economico {a_(nom)}?",
                    f"Nei dati attuali, {join_fr(parts, 'e')}. Il distributore può variare a seconda del carburante."))
        faq.append((f"Quali carburanti sono disponibili {a_(nom)}?",
                    "Sono rilevati i prezzi di: " + join_fr([f"{LABEL[f]} ({plural(F[f]['n'], 'distributore', 'distributori')})" for f in REF_ORDER if f in F], "e")
                    + f", {where(c)}."))
        faq.append((f"Quanti distributori ci sono intorno a {nom}?",
                    f"{plural(c['n_rad'], 'distributore è registrato', 'distributori sono registrati')} in un raggio di {RADIUS_KM} km"
                    + (f", di cui {c['n_commune']} nel comune" if c["n_commune"] else "") + "."))
        f0 = ref_fuels(F, 2, min_n=3, order=COMP_ORDER)
        if f0:
            gap = round(F[f0[0]]["max"] - F[f0[0]]["min"], 3)
            if gap > 0:
                faq.append((f"Come trovare un distributore più economico {a_(nom)}?",
                            f"Confronta i distributori della zona con CarburantRadar: per {EL[f0[0]]}, la differenza tra il più economico e il più caro "
                            f"arriva a {fr_cents(gap)} centesimi al litro, cioè {fr_eur(gap * 40)} € su 40 L, senza contare la deviazione per raggiungere il distributore."))
    return intro, comps, eco, faq


def title_desc_city(c):
    nom, F = c["nom"], c["fuels"]
    t = f"Prezzo benzina e gasolio {a_(nom)}: distributori più economici" if c["n_scope"] >= 15 else f"Prezzo del carburante {a_(nom)}: distributori e tariffe"
    if len(t) + 17 <= 62:
        t += " | CarburantRadar"
    parts = []
    if F:
        parts.append(f"Confronta i prezzi di {join_fr([LABEL[f] for f in REF_ORDER if f in F], 'e')} {a_(nom)}.")
        parts.append(f"{plural(c['n_scope'], 'distributore registrato', 'distributori registrati')} {where(c)}.")
        rf = ref_fuels(F, 1)[0]
        parts.append(f"{LABEL[rf]} da {fr_price(F[rf]['min'])} {unit(rf)}.")
        parts.append("Scopri i distributori più economici e le tariffe disponibili.")
    else:
        parts.append(f"Prezzo del carburante {a_(nom)}: al momento i dati dei prezzi non sono disponibili per questa zona.")
    return t, fit_desc(parts)


def render_city(c, ctx):
    cfg, v, nom = ctx["cfg"], c["v"], c["nom"]
    cur = f"{HUB}{c['slug']}/"
    dep = ctx["dep_info"].get(c["dep_code"]) if ctx["dep_pages"].get(c["dep_code"]) else None
    crumbs = [("Home", "/"), ("Italia", BASE)]
    if dep:
        crumbs.append((dep["name"], f"{BASE}{dep['slug']}/"))
    crumbs.append((nom, cur))
    nav, bc_ld = bc(cur, crumbs)
    intro, comps, eco, faq = city_texts(c, ctx)
    title, desc = title_desc_city(c)
    F = c["fuels"]
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f"<h1>Prezzo del carburante {esc(a_(nom))}</h1>", f'<div class="subtitle">{esc(cfg["subtitle"])}</div>',
            f'<div class="badges"><div class="badge">{esc(cfg["badge_gratuit"])}</div><div class="badge">{esc(cfg["badge_sans_compte"])}</div>'
            f'<div class="badge">{esc(cfg["badge_donnees"])}</div></div>\n</header>']
    rf = ref_fuels(F, 1)
    if rf:
        p, d, s = F[rf[0]]["cheapest"][0]
        body.append(f'<div class="hero-price"><div class="label">Prezzo più basso rilevato oggi</div><div class="price">{fr_price(p)} €</div>'
                    f'<div class="fuel">{esc(LABEL[rf[0]])} — {"il chilo" if rf[0] == "e85" else "il litro"} più economico {esc(where_short(c))}</div>'
                    f'<div class="station">{esc(label(s))}</div></div>')
    body.append(f'<a class="cta-primary" href="{rel(cur, BASE)}">{esc(cfg["cta_top_txt"])}</a>')

    m = ["<main>", f'<section aria-labelledby="intro"><h2 id="intro">Il carburante {esc(a_(nom))} in cifre</h2>']
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
        m.append(f'<section aria-labelledby="riepilogo"><h2 id="riepilogo">Riepilogo dei prezzi {esc(a_(nom))}</h2><div class="tablewrap"><table>'
                 f'<caption>Prezzi in €/L dei distributori situati {esc(where(c))}</caption><thead><tr><th scope="col">Carburante</th>'
                 '<th scope="col">Più basso</th><th scope="col">Medio</th><th scope="col">Più alto</th><th scope="col">Distributori</th></tr></thead><tbody>'
                 + "".join(rows) + "</tbody></table></div></section>")
        m.append(f'<section aria-labelledby="economici"><h2 id="economici">I distributori più economici {esc(a_(nom))}</h2>')
        for f in REF_ORDER:
            if f in F:
                m.append(f"<h3>{esc(LABEL[f])}</h3>")
                m.append(stations_list(F[f]["cheapest"][:3], cur, f))
        m.append('<p class="note">I dati ufficiali indicano la bandiera (marchio) e l\'indirizzo di ogni distributore.</p></section>')
        if comps:
            m.append(f'<section aria-labelledby="confronto"><h2 id="confronto">Confronto dei prezzi intorno a {esc(nom)}</h2>')
            m.extend(f"<p>{esc(t)}</p>" for t in comps)
            m.append("</section>")
        if eco:
            m.append(f'<section aria-labelledby="risparmio"><h2 id="risparmio">Quanto si risparmia su un pieno {esc(a_(nom))}?</h2>')
            m.extend(f"<p>{esc(t)}</p>" for t in eco)
            m.append(f'<p class="note">Questa differenza è teorica: non include il costo della deviazione per raggiungere il distributore più economico, che può ridurre '
                     f'o persino annullare il risparmio. La modalità Percorso dell\'<a href="{rel(cur, BASE)}">app CarburantRadar</a> bilancia prezzo e deviazione.</p></section>')
    nb = c.get("neighbors_shown", [])
    if nb:
        m.append(f'<section aria-labelledby="vicine"><h2 id="vicine">Prezzo del carburante nelle città vicine a {esc(nom)}</h2><ul class="plain">')
        for n in nb:
            rf2 = ref_fuels(n["fuels"], 1)
            extra = f" · {LABEL[rf2[0]]} da {fr_price(n['fuels'][rf2[0]]['min'])} {unit(rf2[0])}" if rf2 else ""
            m.append(f'<li><a href="{rel(cur, HUB + n["slug"] + "/")}">Prezzo del carburante {esc(a_(n["nom"]))}</a> — a {fr_km(n["dist"])}{esc(extra)}</li>')
        m.append("</ul></section>")
    geo = []
    if dep:
        geo.append(f'<p>Consulta i prezzi medi della provincia di <a href="{rel(cur, BASE + dep["slug"] + "/")}">{esc(dep["name"])}</a>.</p>')
    others = c.get("others_dep", [])
    if others:
        geo.append(f'<h3>Altre città della provincia{" di " + esc(dep["name"]) if dep else ""}</h3><ul class="plain">'
                   + "".join(f'<li><a href="{rel(cur, HUB + o["slug"] + "/")}">Prezzo del carburante {esc(a_(o["nom"]))}</a></li>' for o in others) + "</ul>")
    geo.append(f'<p><a href="{rel(cur, HUB)}">Tutte le città coperte in Italia</a></p>')
    m.append('<section aria-labelledby="geo"><h2 id="geo">Esplora per zona geografica</h2>' + "\n".join(geo) + "</section>")
    if faq:
        m.append(faq_html(faq, f"Domande frequenti sul carburante {a_(nom)}"))
    m.append(source_line(ctx["latest"]))
    m.append("</main>")
    body.extend(m)
    body.append(footer(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    ld = [bc_ld] + ([faq_ld(faq)] if faq else [])
    robots = "index, follow" if c["indexable"] else "noindex, follow"
    return shell(lang="it", title=title, desc=desc, canonical=SITE_URL + cur, robots=robots, cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body))


# ------------------------------------------------------------------ provincia e hub

def _table(st, caption):
    rows = [f'<tr><th scope="row">{esc(LABEL[f])}</th><td class="min">{fr_price(st["fuels"][f]["min"])}</td><td>{fr_price(st["fuels"][f]["avg"])}</td>'
            f'<td class="max">{fr_price(st["fuels"][f]["max"])}</td><td>{st["fuels"][f]["n"]}</td></tr>' for f in REF_ORDER if f in st["fuels"]]
    return (f'<div class="tablewrap"><table><caption>{esc(caption)}</caption><thead><tr><th scope="col">Carburante</th><th scope="col">Più basso</th>'
            '<th scope="col">Medio</th><th scope="col">Più alto</th><th scope="col">Distributori</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def _city_li(cur, c):
    rf = ref_fuels(c["fuels"], 1)
    extra = f" — {LABEL[rf[0]]} da {fr_price(c['fuels'][rf[0]]['min'])} {unit(rf[0])}" if rf else ""
    return (f'<li><a href="{rel(cur, HUB + c["slug"] + "/")}">Prezzo del carburante {esc(a_(c["nom"]))}</a>'
            f' — {plural(c["n_scope"], "distributore", "distributori")}{esc(extra)}</li>')


def render_dep(info, cities, ctx):
    cfg = ctx["cfg"]
    cur = f"{BASE}{info['slug']}/"
    nav, bc_ld = bc(cur, [("Home", "/"), ("Italia", BASE), (info["name"], cur)])
    st, F, name = info["stats"], info["stats"]["fuels"], info["name"]
    rf = ref_fuels(F, 1)
    title = f"Prezzo del carburante in provincia di {name}: medie e distributori"
    if len(title) + 17 <= 66:
        title += " | CarburantRadar"
    intro = [f"Il dataset ufficiale registra {plural(st['n'], 'distributore', 'distributori')} nella provincia di {name} ({info['code']})."]
    if F and rf:
        intro.append(f"Sono rilevati i prezzi di {fuel_names(F)}. Per {EL[rf[0]]}, il prezzo più basso della provincia è di {fr_price(F[rf[0]]['min'])} {unit(rf[0])} "
                     f"e la media di {fr_price(F[rf[0]]['avg'])} {unit(rf[0])} su {F[rf[0]]['n']} distributori.")
    intro.append(f"{plural(len(cities), 'città è coperta', 'città sono coperte')} da una pagina CarburantRadar in questa provincia: {_names(cities)}.")
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f"<h1>Prezzo del carburante in provincia di {esc(name)}</h1>", f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            f'<section aria-labelledby="intro"><h2 id="intro">Il carburante in provincia di {esc(name)} in cifre</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append("</section>")
    if F and rf:
        body.append(f'<section aria-labelledby="prezzi"><h2 id="prezzi">Prezzi per carburante in provincia di {esc(name)}</h2>'
                    + _table(st, f"Prezzi in €/L rilevati nei distributori della provincia di {name}") + "</section>")
        f0 = rf[0]
        body.append(f'<section aria-labelledby="economici"><h2 id="economici">I distributori più economici della provincia ({esc(LABEL[f0])})</h2>'
                    + stations_list(F[f0]["cheapest"][:5], cur, f0) + "</section>")
        rk = commune_ranking(info["stations"], f0, min_n=3, top=5)
        if rk:
            body.append(f'<section aria-labelledby="comuni"><h2 id="comuni">Comuni dove {EL[f0]} costa meno in media</h2>'
                        f'<p class="note">Comuni della provincia con almeno 3 distributori con un prezzo per {LABEL[f0]}, ordinati per prezzo medio.</p><ul class="plain">'
                        + "".join(f"<li>{esc(n)} — {fr_price(avg)} {unit(f0)} in media ({k} distributori)</li>" for avg, _, n, k in rk) + "</ul></section>")
    body.append(f'<section aria-labelledby="citta"><h2 id="citta">Città della provincia di {esc(name)} coperte da CarburantRadar</h2><ul class="plain">'
                + "".join(_city_li(cur, c) for c in cities)
                + f'</ul><p><a href="{rel(cur, HUB)}">Tutte le città coperte in Italia</a></p></section>')
    faq = []
    if rf:
        f0 = rf[0]
        s0 = F[f0]
        p, d, s = s0["cheapest"][0]
        faq.append((f"Qual è il prezzo medio {DEL[f0]} in provincia di {name}?",
                    f"Secondo il dataset ufficiale, la media {DEL[f0]} è di {fr_price(s0['avg'])} {unit(f0)} su {s0['n']} distributori, "
                    f"con un minimo di {fr_price(s0['min'])} {unit(f0)} e un massimo di {fr_price(s0['max'])} {unit(f0)}."))
        faq.append((f"Dov'è il distributore più economico in provincia di {name}?",
                    f"Per {EL[f0]}, il distributore più economico rilevato è {label(s)}, a {fr_price(p)} {unit(f0)}."))
    faq.append((f"Quanti distributori ci sono in provincia di {name}?",
                f"{plural(st['n'], 'distributore è registrato', 'distributori sono registrati')} nel dataset ufficiale per questa provincia."))
    body.append(faq_html(faq, f"Domande frequenti: carburante in provincia di {name}"))
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(footer(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Prezzo del carburante in provincia di {name}: {plural(st['n'], 'distributore registrato', 'distributori registrati')}.",
                     (f"{LABEL[rf[0]]} da {fr_price(F[rf[0]]['min'])} {unit(rf[0])}, media {fr_price(F[rf[0]]['avg'])} {unit(rf[0])}." if rf else ""),
                     "Distributori più economici e città coperte."])
    ld = [bc_ld, faq_ld(faq), item_list(f"Città della provincia di {name}", [(f"Prezzo del carburante {a_(c['nom'])}", HUB + c["slug"] + "/") for c in cities])]
    return shell(lang="it", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body))


def render_hub(ctx, cities_idx, dep_list):
    cfg = ctx["cfg"]
    cur = HUB
    nav, bc_ld = bc(cur, [("Home", "/"), ("Italia", BASE), ("Prezzo per città", cur)])
    nat = ctx["nat"]
    title = "Prezzo del carburante per città in Italia: tutte le città"
    intro = [f"CarburantRadar dettaglia il prezzo del carburante in {plural(len(cities_idx), 'città italiana', 'città italiane')}, a partire dai dati pubblici del Ministero delle Imprese e del Made in Italy."]
    rf = [f for f in REF_ORDER if f in nat][:1]
    if rf:
        n = nat[rf[0]]
        intro.append(f"Nel dataset, {EL[rf[0]]} è rilevato in media a {fr_price(n['avg'])} {unit(rf[0])} ({n['n']} distributori), con un minimo di {fr_price(n['min'])} {unit(rf[0])}.")
    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            "<h1>Prezzo del carburante per città in Italia</h1>", f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>', "<main>",
            '<section aria-labelledby="intro"><h2 id="intro">Scegli la tua città</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append("</section>")
    by_dep = {}
    for c in cities_idx:
        by_dep.setdefault(c["dep_code"] if ctx["dep_pages"].get(c["dep_code"]) else None, []).append(c)
    body.append('<section aria-labelledby="province"><h2 id="province">Città per provincia</h2>')
    for d in dep_list:
        lst = by_dep.get(d["code"], [])
        if lst:
            body.append(f'<h3><a href="{rel(cur, BASE + d["slug"] + "/")}">{esc(d["name"])}</a></h3><ul class="plain">'
                        + "".join(f'<li><a href="{rel(cur, HUB + c["slug"] + "/")}">Prezzo del carburante {esc(a_(c["nom"]))}</a></li>' for c in lst) + "</ul>")
    if by_dep.get(None):
        body.append('<h3>Altre città</h3><ul class="plain">'
                    + "".join(f'<li><a href="{rel(cur, HUB + c["slug"] + "/")}">Prezzo del carburante {esc(a_(c["nom"]))}</a></li>' for c in by_dep[None]) + "</ul>")
    body.append("</section>")
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(footer(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Prezzo del carburante in {plural(len(cities_idx), 'città', 'città')} italiane: benzina, gasolio, GPL e metano.",
                     "Scegli la tua città o la tua provincia e confronta i distributori più economici."])
    top = sorted(cities_idx, key=lambda c: (-c["n_scope"], c["nom"]))[:100]
    ld = [bc_ld, item_list("Principali città italiane coperte", [(f"Prezzo del carburante {a_(c['nom'])}", HUB + c["slug"] + "/") for c in top])]
    return shell(lang="it", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body))
