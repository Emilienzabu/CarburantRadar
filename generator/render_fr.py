"""Rendu des pages France : villes, ville+carburant, départements, régions, hubs."""
import json
from datetime import timezone

from data_fr import FUELS, FUEL_LABEL, FUEL_SLUG
from geo import fr_price, fr_eur, fr_km, fr_cents, plural, join_fr
from render_common import (SITE_URL, DATASET_URL, esc, rel, breadcrumb, item_list, faq_ld, faq_html,
                           fit_desc, shell, jsonld, strip_tags)
from stats_fr import label, pretty, NEIGHBOR_MAX, RADIUS_KM, commune_ranking

try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")
except Exception:  # tzdata absent : on affiche en UTC
    _PARIS = timezone.utc

FUEL_DE = {"gazole": "du gazole", "sp95": "du SP95", "sp98": "du SP98", "e10": "de l'E10", "e85": "de l'E85", "gplc": "du GPL"}
FUEL_LE = {"gazole": "le gazole", "sp95": "le SP95", "sp98": "le SP98", "e10": "l'E10", "e85": "l'E85", "gplc": "le GPL"}
REF_ORDER = ["gazole", "e10", "sp95", "sp98", "e85", "gplc"]
VOWELS = "AEIOUYÉÈÊËÎÏÔÛÀÂ"
H_ASPIRE_OK = {"Hyères"}  # h muet traité comme voyelle pour l'élision


def _starts_vowel(nom):
    return nom[:1].upper() in VOWELS or nom in H_ASPIRE_OK


def a_ville(nom):
    if nom.startswith("Le "):
        return "au " + nom[3:]
    if nom.startswith("Les "):
        return "aux " + nom[4:]
    return "à " + nom


def de_ville(nom):
    if nom.startswith("Le "):
        return "du " + nom[3:]
    if nom.startswith("Les "):
        return "des " + nom[4:]
    if _starts_vowel(nom):
        return "d'" + nom
    return "de " + nom


def where(c):
    """Portée réelle des chiffres de la page : la commune (>= 3 stations dans le flux) ou un rayon autour du centre."""
    dv = de_ville(c["nom"])
    return f"dans la commune {dv}" if c["scope"] == "commune" else f"dans un rayon de {RADIUS_KM} km autour {dv}"


def where_short(c):
    dv = de_ville(c["nom"])
    return f"dans la commune {dv}" if c["scope"] == "commune" else f"autour {dv}"


def fmt_dt(d):
    d = d.astimezone(_PARIS)
    return d.strftime("%d/%m/%Y") + " à " + d.strftime("%H:%M")


def fmt_date_str(s):
    """'2026-09-29T08:15:00+02:00' -> '29/09/2026' (sans réinterprétation du fuseau)."""
    if s and len(s) >= 10 and s[4] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return None


def cmp_phrase(diff):
    if abs(diff) < 0.0005:
        return "quasiment identique"
    return f"supérieure de {fr_cents(abs(diff))} centime{'s' if abs(diff) * 100 >= 2 else ''} par litre" if diff > 0 \
        else f"inférieure de {fr_cents(abs(diff))} centime{'s' if abs(diff) * 100 >= 2 else ''} par litre"


def ref_fuels(fuels, k=3, min_n=1):
    return [f for f in REF_ORDER if f in fuels and fuels[f]["n"] >= min_n][:k]


def fuel_names(fuels):
    return join_fr([FUEL_LABEL[f] for f in FUELS if f in fuels])


# ------------------------------------------------------------------ blocs communs

def stations_list(items, cur, show_fuel=None):
    out = ['<ol class="stations">']
    for price, dist, s in items:
        meta = []
        if dist is not None and dist > 0:
            meta.append(f"à {fr_km(dist)} du centre")
        d = fmt_date_str(s["m"].get(show_fuel)) if show_fuel else None
        if d:
            meta.append(f"prix relevé le {d}")
        if s["a24"]:
            meta.append("ouverte 24h/24")
        links = []
        if s["id"]:
            links.append(f'<a href="https://www.prix-carburants.gouv.fr/station/{esc(s["id"])}" rel="noopener">Fiche officielle</a>')
        links.append(f'<a href="https://www.google.com/maps/dir/?api=1&amp;destination={s["lat"]},{s["lon"]}" rel="noopener">Itinéraire</a>')
        out.append(
            f'<li><div class="s-top"><span class="s-name">{esc(label(s))}</span>'
            f'<span class="s-price">{fr_price(price)}&nbsp;€/L</span></div>'
            f'<div class="s-meta">{esc(" · ".join(meta))}</div>'
            f'<div class="s-links">{" · ".join(links)}</div></li>')
    out.append("</ol>")
    return "\n".join(out)


def live_block(cfg, v):
    """Bloc dynamique existant (prix en direct via le Worker) : conservé à l'identique."""
    return f"""<script>
(function(){{
  var PROXY="https://carburant-proxy.emilienzabukovec09.workers.dev";
  var ROUTE={json.dumps(cfg["route"], ensure_ascii=False)};
  var LAT={v["lat"]};
  var LON={v["lon"]};
  var PK={json.dumps(cfg["fuel_map"], ensure_ascii=False)};
  var FUEL={json.dumps(cfg["fuel_defaut"], ensure_ascii=False)};
  var FUEL_LABEL={json.dumps(cfg["fuel_label"], ensure_ascii=False)};
  var HERO_SUFFIX={json.dumps(cfg["hero_suffix"], ensure_ascii=False)};
  var NO_DATA_TXT={json.dumps(cfg["no_data_txt"], ensure_ascii=False)};
  var ERROR_TXT={json.dumps(cfg["error_txt"], ensure_ascii=False)};
  var el=document.getElementById("live-data");
  var heroPrice=document.getElementById("hero-price");
  var heroFuel=document.getElementById("hero-fuel");
  var heroStation=document.getElementById("hero-station");
  fetch(PROXY+ROUTE+"?lat="+LAT+"&lon="+LON+"&dist=12&limit=100").then(function(r){{if(!r.ok)throw new Error();return r.json();}})
  .then(function(raw){{
    if(!raw||!Array.isArray(raw.results)||!raw.results.length){{
      el.innerHTML="<div class=\\"live-status\\">"+NO_DATA_TXT+"</div>";
      heroPrice.textContent="—";heroFuel.textContent=NO_DATA_TXT;
      return;
    }}
    var st=[];
    raw.results.forEach(function(r){{
      var px=parseFloat(r[PK[FUEL]]);
      if(isNaN(px)||px<=0)return;
      st.push({{adresse:r.adresse||"",ville:r.ville||"",prix:px}});
    }});
    if(!st.length){{
      el.innerHTML="<div class=\\"live-status\\">"+NO_DATA_TXT+"</div>";
      heroPrice.textContent="—";heroFuel.textContent=NO_DATA_TXT;
      return;
    }}
    st.sort(function(a,b){{return a.prix-b.prix;}});
    var top=st.slice(0,5);
    heroPrice.textContent=top[0].prix.toFixed(3)+" €";
    heroFuel.textContent=FUEL_LABEL+" — "+HERO_SUFFIX;
    heroStation.textContent=(top[0].ville||top[0].adresse||"");
    var html="";
    top.forEach(function(s){{
      html+="<div class=\\"live-row\\"><div><div class=\\"live-name\\">"+(s.ville||s.adresse||"Station")+"</div><div class=\\"live-addr\\">"+(s.adresse||"")+"</div></div><div class=\\"live-price\\">"+s.prix.toFixed(3)+" €</div></div>";
    }});
    el.innerHTML=html;
  }}).catch(function(){{
    el.innerHTML="<div class=\\"live-status\\">"+ERROR_TXT+"</div>";
    heroPrice.textContent="—";heroFuel.textContent=ERROR_TXT;
  }});
}})();
</script>"""


def source_line(latest):
    return (f'<p class="updated">Données des prix mises à jour le {fmt_dt(latest)} (dernière mise à jour de prix '
            f'enregistrée dans le jeu de données). Prix issus des données publiques du gouvernement français, publiées sur '
            f'<a href="{DATASET_URL}" rel="noopener">data.economie.gouv.fr</a> ; CarburantRadar n\'est pas la source originale '
            f'des prix. Les tableaux de cette page sont recalculés une fois par jour : le bloc « en direct » est, lui, '
            f'actualisé à chaque visite.</p>')


def footer_boilerplate(cfg, cur):
    b = cfg["benefits"]
    return (f'<h2>{esc(cfg["h2_benefits"])}</h2>\n<ul>\n' + "\n".join(f"<li>{esc(x)}</li>" for x in b) + "\n</ul>\n"
            f'<a class="cta-primary" href="{rel(cur, "/france/")}">{esc(cfg["cta_final_txt"])}</a>')


# ------------------------------------------------------------------ page ville

def city_texts(c, ctx):
    """Introduction, comparaisons, économies et FAQ : uniquement à partir des données de la ville."""
    nom = c["nom"]
    dv = de_ville(nom)
    F = c["fuels"]
    dep = ctx["dep_info"].get(c["dep_code"])
    reg = ctx["reg_info"].get(c["reg_code"])
    nat = ctx["nat"]
    intro = []
    if c["n_rad"] == 0:
        return ([f"Le jeu de données officiel ne référence aucune station-service dans un rayon de {RADIUS_KM} km autour {dv} : "
                 "aucun prix n'est disponible pour cette zone à ce jour."], [], [], [])
    s1 = f"{plural(c['n_rad'], 'station-service est référencée', 'stations-service sont référencées')} dans un rayon de {RADIUS_KM} km autour {dv}"
    if c["n_commune"] and c["n_commune"] != c["n_rad"]:
        s1 += f", dont {c['n_commune']} dans la commune elle-même"
    elif c["n_commune"] and c["n_commune"] == c["n_rad"]:
        s1 += ", toutes situées dans la commune"
    s1 += "."
    intro.append(s1)
    if dep and reg:
        intro.append(f"Département : {dep['name']} ({dep['code']}), région {reg['name']}.")
    elif dep:
        intro.append(f"Département : {dep['name']} ({dep['code']}).")
    if F:
        names = fuel_names(F)
        rf = ref_fuels(F, 1)[0]
        st = F[rf]
        s = f"{plural(len(F), 'carburant est relevé', 'carburants sont relevés')} : {names}. "
        s += (f"Pour {FUEL_LE[rf]}, le prix le plus bas est de {fr_price(st['min'])} €/L pour un prix moyen de "
              f"{fr_price(st['avg'])} €/L sur {plural(st['n'], 'station', 'stations')} {where(c)}")
        if st["n"] >= 3 and st["max"] > st["min"]:
            s += f", avec un écart de {fr_cents(st['max'] - st['min'])} centimes par litre entre la moins chère et la plus chère"
        s += "."
        intro.append(s)
    else:
        intro.append("Aucun prix n'est disponible dans les données pour cette zone à ce jour.")
    nb = c.get("neighbors_shown", [])
    if nb:
        intro.append("Les villes voisines couvertes par CarburantRadar les plus proches sont "
                     + join_fr([n["nom"] for n in nb[:3]]) + ".")

    # comparaisons
    comps = []
    for f in ref_fuels(F, 3, min_n=3):
        st = F[f]
        t = (f"{FUEL_LABEL[f]} : le prix le plus bas relevé {where_short(c)} est de {fr_price(st['min'])} €/L, "
             f"contre une moyenne locale de {fr_price(st['avg'])} €/L sur {st['n']} stations.")
        d = dep["stats"]["fuels"].get(f) if dep else None
        if d and d["n"] >= ctx["min_dep_compare"]:
            t += (f" La moyenne des stations retenues dans le département {dep['name']} est de {fr_price(d['avg'])} €/L "
                  f"({d['n']} stations) : la moyenne locale y est {cmp_phrase(st['avg'] - d['avg'])}.")
            c.setdefault("compare_dep", True)
        n = nat.get(f)
        if n:
            t += (f" Pour l'ensemble des stations du jeu de données, la moyenne nationale est de {fr_price(n['avg'])} €/L "
                  f"({n['n']} stations) ; la moyenne locale est {cmp_phrase(st['avg'] - n['avg'])}.")
        comps.append(t)

    # économies
    eco = []
    for f in ref_fuels(F, 2, min_n=3):
        st = F[f]
        gap = round(st["max"] - st["min"], 3)
        if gap > 0:
            eco.append(f"{FUEL_LABEL[f]} : entre la station la moins chère ({fr_price(st['min'])} €/L) et la plus chère "
                       f"({fr_price(st['max'])} €/L) de la zone, l'écart est de {fr_cents(gap)} centimes par litre, soit "
                       f"{fr_eur(gap * 40)} € sur un plein de 40 L et {fr_eur(gap * 50)} € sur un plein de 50 L.")

    # FAQ
    faq = []
    rf = ref_fuels(F, 1)
    if "gazole" in F:
        st = F["gazole"]
        faq.append((f"Quel est le prix du gazole {a_ville(nom)} ?",
                    f"{where_short(c)[0].upper() + where_short(c)[1:]}, le gazole le moins cher est relevé à {fr_price(st['min'])} €/L, pour une moyenne de "
                    f"{fr_price(st['avg'])} €/L sur {plural(st['n'], 'station', 'stations')}."))
    elif rf:
        f = rf[0]
        st = F[f]
        faq.append((f"Quel est le prix {FUEL_DE[f]} {a_ville(nom)} ?",
                    f"{where_short(c)[0].upper() + where_short(c)[1:]}, {FUEL_LE[f]} le moins cher est relevé à {fr_price(st['min'])} €/L, pour une moyenne de "
                    f"{fr_price(st['avg'])} €/L sur {plural(st['n'], 'station', 'stations')}."))
    if F:
        parts = []
        for f in ref_fuels(F, 3):
            p, d, s = F[f]["cheapest"][0]
            parts.append(f"pour {FUEL_LE[f]}, {label(s)} ({fr_price(p)} €/L)")
        faq.append((f"Quelle est la station la moins chère {a_ville(nom)} ?",
                    f"Dans les données actuelles, {join_fr(parts, 'et')}. La station peut varier selon le carburant."))
        faq.append((f"Quels carburants sont disponibles {a_ville(nom)} ?",
                    "Des prix sont relevés pour : " + join_fr([f"{FUEL_LABEL[f]} ({plural(F[f]['n'], 'station', 'stations')})"
                                                              for f in FUELS if f in F]) + f", {where(c)}."))
        faq.append((f"Combien de stations-service y a-t-il autour {dv} ?",
                    f"{plural(c['n_rad'], 'station est référencée', 'stations sont référencées')} dans un rayon de {RADIUS_KM} km"
                    + (f", dont {c['n_commune']} dans la commune" if c["n_commune"] else "") + "."))
        if eco:
            f0 = ref_fuels(F, 2, min_n=3)
            gap = round(F[f0[0]]["max"] - F[f0[0]]["min"], 3) if f0 else 0
            if gap > 0:
                faq.append((f"Comment trouver une station moins chère autour {dv} ?",
                            f"Comparez les stations de la zone avec CarburantRadar : pour {FUEL_LE[f0[0]]}, l'écart entre la moins chère "
                            f"et la plus chère atteint {fr_cents(gap)} centimes par litre, soit {fr_eur(gap * 40)} € sur 40 L, hors coût "
                            f"du détour pour rejoindre la station."))
    return intro, comps, eco, faq


def title_desc_city(c, ctx):
    nom = c["nom"]
    if c["n_scope"] >= 15:
        t = f"Prix carburant {nom} : stations les moins chères"
    else:
        t = f"Prix du carburant {a_ville(nom)} : stations et tarifs"
    if len(t) + 17 <= 62:
        t += " | CarburantRadar"
    F = c["fuels"]
    parts = []
    if F:
        parts.append(f"Comparez les prix {'du ' + join_fr([FUEL_LABEL[f] for f in FUELS if f in F])} {a_ville(nom)}.".replace("du Gazole", "du gazole"))
        parts.append(f"{plural(c['n_scope'], 'station référencée', 'stations référencées')} {where(c)}.")
        rf = ref_fuels(F, 1)[0]
        parts.append(f"{FUEL_LABEL[rf]} dès {fr_price(F[rf]['min'])} €/L.")
        parts.append("Consultez les stations les moins chères et les tarifs disponibles.")
    else:
        parts.append(f"Prix du carburant {a_ville(nom)} : les données de prix ne sont pas disponibles pour cette zone à ce jour.")
    return t, fit_desc(parts)


def render_city(c, ctx):
    cfg = ctx["cfg"]
    v = c["v"]
    nom = c["nom"]
    cur = f"/france/prix-carburant/{c['slug']}/"
    dep = ctx["dep_info"].get(c["dep_code"]) if ctx["dep_pages"].get(c["dep_code"]) else None
    reg_code = c["reg_code"]
    reg = ctx["reg_info"].get(reg_code) if ctx["reg_pages"].get(reg_code) else None
    crumbs = [("Accueil", "/"), ("France", "/france/")]
    if reg:
        crumbs.append((reg["name"], f"/france/{reg['slug']}/"))
    if dep:
        crumbs.append((dep["name"], f"/france/{dep['slug']}/"))
    crumbs.append((nom, cur))
    nav, bc_ld = breadcrumb(cur, crumbs)

    intro, comps, eco, faq = city_texts(c, ctx)
    title, desc = title_desc_city(c, ctx)
    F = c["fuels"]
    dv = de_ville(nom)
    body = []
    body.append(f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}')
    body.append(f'<h1>Prix du carburant {a_ville(nom)}</h1>')
    body.append(f'<div class="subtitle">{esc(cfg["subtitle"])}</div>')
    body.append(f'<div class="badges"><div class="badge">{esc(cfg["badge_gratuit"])}</div><div class="badge">{esc(cfg["badge_sans_compte"])}</div>'
                f'<div class="badge">{esc(cfg["badge_donnees"])}</div></div>\n</header>')
    body.append(f'''<div class="hero-price">
    <div class="label">{esc(cfg["hero_label"])}</div>
    <div class="price" id="hero-price">…</div>
    <div class="fuel" id="hero-fuel">{esc(cfg["loading_txt"])}</div>
    <div class="station" id="hero-station"></div>
  </div>
<a class="cta-primary" href="{rel(cur, "/france/")}">{esc(cfg["cta_top_txt"])}</a>
<div class="card">
    <h2 style="margin-top:0">{esc(cfg["h2_live_tpl"].format(ville=nom, fuel_label=cfg["fuel_label"]))}</h2>
    <div id="live-data"><div class="live-status">{esc(cfg["loading_txt"])}</div></div>
  </div>''')

    m = ['<main>']
    m.append(f'<section aria-labelledby="intro"><h2 id="intro">Le carburant autour {dv} en chiffres</h2>')
    for p in intro:
        m.append(f"<p>{esc(p)}</p>")
    if v.get("intro"):
        m.append(f"<p>{esc(v['intro'])}</p>")
    if v.get("why"):
        m.append(f"<p>{esc(v['why'])}</p>")
    m.append("</section>")

    if F:
        # D. résumé des prix
        m.append(f'<section aria-labelledby="resume"><h2 id="resume">Résumé des prix {a_ville(nom)}</h2>')
        rows = []
        for f in FUELS:
            if f not in F:
                continue
            st = F[f]
            name = esc(FUEL_LABEL[f])
            if (f, c["slug"]) in ctx["fuel_pages"]:
                name = f'<a href="{FUEL_SLUG[f]}/">{name}</a>'
            rows.append(f'<tr><th scope="row">{name}</th><td class="min">{fr_price(st["min"])}</td><td>{fr_price(st["avg"])}</td>'
                        f'<td class="max">{fr_price(st["max"])}</td><td>{st["n"]}</td></tr>')
        m.append(f'<div class="tablewrap"><table><caption>Prix en €/L des stations situées {where(c)}</caption>'
                 '<thead><tr><th scope="col">Carburant</th><th scope="col">Le plus bas</th><th scope="col">Moyen</th>'
                 '<th scope="col">Le plus haut</th><th scope="col">Stations</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
        m.append("</section>")

        # E. stations les moins chères
        m.append(f'<section aria-labelledby="stations"><h2 id="stations">Les stations les moins chères {a_ville(nom)}</h2>')
        for f in FUELS:
            if f not in F:
                continue
            m.append(f"<h3>{esc(FUEL_LABEL[f])}</h3>")
            m.append(stations_list(F[f]["cheapest"][:3], cur, f))
        m.append('<p class="note">Le jeu de données officiel ne mentionne ni le nom ni l\'enseigne des stations : elles sont identifiées par leur adresse.</p></section>')

        if comps:
            m.append(f'<section aria-labelledby="comparaison"><h2 id="comparaison">Comparaison des prix autour {dv}</h2>')
            m.extend(f"<p>{esc(t)}</p>" for t in comps)
            m.append("</section>")
        if eco:
            m.append(f'<section aria-labelledby="economies"><h2 id="economies">Combien économiser sur un plein {a_ville(nom)} ?</h2>')
            m.extend(f"<p>{esc(t)}</p>" for t in eco)
            m.append(f'<p class="note">Cet écart est théorique : il ne comprend pas le coût du détour pour rejoindre la station la moins chère, '
                     f'qui peut réduire voire annuler le gain. Le mode Trajet de <a href="{rel(cur, "/france/")}">l\'application CarburantRadar</a> '
                     f'arbitre entre prix et détour.</p></section>')

    # H. villes voisines
    nb = c.get("neighbors_shown", [])
    if nb:
        m.append(f'<section aria-labelledby="voisines"><h2 id="voisines">Prix du carburant dans les villes proches {dv}</h2><ul class="plain">')
        for n in nb:
            extra = []
            rf = ref_fuels(n["fuels"], 1)
            if rf:
                extra.append(f"{FUEL_LABEL[rf[0]]} dès {fr_price(n['fuels'][rf[0]]['min'])} €/L")
            m.append(f'<li><a href="{rel(cur, "/france/prix-carburant/" + n["slug"] + "/")}">Prix du carburant {esc(a_ville(n["nom"]))}</a>'
                     f' — à {fr_km(n["dist"])}{" · " + esc(", ".join(extra)) if extra else ""}</li>')
        m.append("</ul></section>")

    # I. département / région / autres villes
    geo = []
    if dep:
        geo.append(f'<p>Retrouvez les prix moyens du département <a href="{rel(cur, "/france/" + dep["slug"] + "/")}">{esc(dep["name"])}</a>'
                   + (f' et de la région <a href="{rel(cur, "/france/" + reg["slug"] + "/")}">{esc(reg["name"])}</a>' if reg else "") + ".</p>")
    elif reg:
        geo.append(f'<p>Retrouvez les prix de la région <a href="{rel(cur, "/france/" + reg["slug"] + "/")}">{esc(reg["name"])}</a>.</p>')
    others = c.get("others_dep", [])
    if others:
        geo.append(f'<h3>Autres villes du département{" " + esc(dep["name"]) if dep else ""}</h3><ul class="plain">'
                   + "".join(f'<li><a href="{rel(cur, "/france/prix-carburant/" + o["slug"] + "/")}">Prix du carburant {esc(a_ville(o["nom"]))}</a></li>' for o in others)
                   + "</ul>")
    geo.append(f'<p><a href="{rel(cur, "/france/prix-carburant/")}">Toutes les villes couvertes en France</a></p>')
    m.append('<section aria-labelledby="geo"><h2 id="geo">Explorer par zone géographique</h2>' + "\n".join(geo) + "</section>")

    if faq:
        m.append(faq_html(faq, f"Questions fréquentes sur le carburant {a_ville(nom)}"))
    m.append(source_line(ctx["latest"]))
    m.append("</main>")
    body.append("\n".join(m))
    body.append(footer_boilerplate(cfg, cur))
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')

    ld = [bc_ld]
    if faq:
        ld.append(faq_ld(faq))
    if nb:
        ld.append(item_list(f"Villes proches {dv}", [(f"Prix du carburant {a_ville(n['nom'])}", "/france/prix-carburant/" + n["slug"] + "/") for n in nb]))
    robots = "index, follow" if c["indexable"] else "noindex, follow"
    return shell(lang="fr", title=title, desc=desc, canonical=SITE_URL + cur, robots=robots, cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body), script=live_block(cfg, v)), title, desc


# ------------------------------------------------------------------ page ville + carburant

def render_fuel_page(c, f, ctx):
    cfg = ctx["cfg"]
    nom = c["nom"]
    dv = de_ville(nom)
    st = c["fuels"][f]
    cur = f"/france/prix-carburant/{c['slug']}/{FUEL_SLUG[f]}/"
    city_path = f"/france/prix-carburant/{c['slug']}/"
    dep = ctx["dep_info"].get(c["dep_code"]) if ctx["dep_pages"].get(c["dep_code"]) else None
    crumbs = [("Accueil", "/"), ("France", "/france/")]
    if dep:
        crumbs.append((dep["name"], f"/france/{dep['slug']}/"))
    crumbs += [(nom, city_path), (FUEL_LABEL[f], cur)]
    nav, bc_ld = breadcrumb(cur, crumbs)
    title = f"{FUEL_LABEL[f]} {a_ville(nom)} : prix et stations les moins chères"
    if len(title) + 17 <= 62:
        title += " | CarburantRadar"
    gap = round(st["max"] - st["min"], 3)
    d = ctx["dep_info"].get(c["dep_code"])
    dstat = d["stats"]["fuels"].get(f) if d else None
    nat = ctx["nat"].get(f)

    intro = [f"{plural(st['n'], 'station propose', 'stations proposent')} {FUEL_LE[f]} avec un prix relevé {where(c)}. "
             f"Le prix le plus bas est de {fr_price(st['min'])} €/L, le prix moyen de {fr_price(st['avg'])} €/L et le plus élevé de {fr_price(st['max'])} €/L."]
    if gap > 0:
        intro.append(f"L'écart entre la station la moins chère et la plus chère est de {fr_cents(gap)} centimes par litre.")
    cmp_txt = []
    if dstat and dstat["n"] >= ctx["min_dep_compare"]:
        cmp_txt.append(f"Dans le département {d['name']}, la moyenne {FUEL_DE[f]} est de {fr_price(dstat['avg'])} €/L ({dstat['n']} stations) : "
                       f"la moyenne locale est {cmp_phrase(st['avg'] - dstat['avg'])}.")
    if nat:
        cmp_txt.append(f"La moyenne nationale du jeu de données est de {fr_price(nat['avg'])} €/L ({nat['n']} stations) : "
                       f"la moyenne locale est {cmp_phrase(st['avg'] - nat['avg'])}.")
    nb = [n for n in c.get("neighbors_shown", []) if f in n["fuels"]][:5]
    top = st["cheapest"][:10]
    p1, d1, s1 = top[0]
    faq = [(f"Quel est le prix {FUEL_DE[f]} {a_ville(nom)} ?",
            f"{where_short(c)[0].upper() + where_short(c)[1:]}, {FUEL_LE[f]} est relevé entre {fr_price(st['min'])} et {fr_price(st['max'])} €/L, pour une moyenne de {fr_price(st['avg'])} €/L "
            f"sur {st['n']} stations."),
           (f"Où trouver {FUEL_LE[f]} le moins cher {a_ville(nom)} ?",
            f"La station la moins chère relevée est {label(s1)}, à {fr_price(p1)} €/L, à {fr_km(d1)} du centre {dv}.")]
    if gap > 0:
        faq.append((f"Combien économise-t-on sur un plein {FUEL_DE[f]} {a_ville(nom)} ?",
                    f"Entre la station la moins chère et la plus chère de la zone, l'écart est de {fr_eur(gap * 40)} € sur 40 L et {fr_eur(gap * 50)} € sur 50 L, "
                    f"hors coût du détour."))

    body = [f'<div class="wrap">\n<header>\n<a class="brand" href="{rel(cur, "/")}"><span>⛽</span> CarburantRadar</a>\n{nav}',
            f'<h1>Prix {FUEL_DE[f]} {a_ville(nom)}</h1>',
            f'<div class="subtitle">{esc(cfg["subtitle"])}</div>\n</header>',
            '<main>', f'<section aria-labelledby="resume"><h2 id="resume">{esc(FUEL_LABEL[f])} autour {dv} en chiffres</h2>']
    body.extend(f"<p>{esc(t)}</p>" for t in intro)
    body.append(f'<div class="tablewrap"><table><caption>Prix {FUEL_DE[f]} en €/L, stations situées {where(c)}</caption><thead><tr>'
                '<th scope="col">Le plus bas</th><th scope="col">Moyen</th><th scope="col">Le plus haut</th><th scope="col">Stations</th></tr></thead><tbody>'
                f'<tr><td class="min">{fr_price(st["min"])}</td><td>{fr_price(st["avg"])}</td><td class="max">{fr_price(st["max"])}</td><td>{st["n"]}</td></tr></tbody></table></div></section>')
    body.append(f'<section aria-labelledby="stations"><h2 id="stations">Les stations les moins chères pour {FUEL_LE[f]} {a_ville(nom)}</h2>')
    body.append(stations_list(top, cur, f))
    body.append('<p class="note">Le jeu de données officiel ne mentionne ni le nom ni l\'enseigne des stations : elles sont identifiées par leur adresse.</p></section>')
    if cmp_txt:
        body.append(f'<section aria-labelledby="comparaison"><h2 id="comparaison">Comparaison</h2>' + "".join(f"<p>{esc(t)}</p>" for t in cmp_txt) + "</section>")
    if gap > 0:
        body.append(f'<section aria-labelledby="economies"><h2 id="economies">Économie potentielle sur un plein</h2><p>{esc(f"Entre la station la moins chère et la plus chère de la zone : {fr_eur(gap * 40)} € sur un plein de 40 L, {fr_eur(gap * 50)} € sur 50 L.")}</p>'
                    f'<p class="note">Écart théorique, hors coût du détour pour rejoindre la station.</p></section>')
    if nb:
        body.append(f'<section aria-labelledby="voisines"><h2 id="voisines">{esc(FUEL_LABEL[f])} dans les villes proches {dv}</h2><ul class="plain">'
                    + "".join(f'<li><a href="{rel(cur, "/france/prix-carburant/" + n["slug"] + "/")}">{esc(FUEL_LABEL[f])} {esc(a_ville(n["nom"]))}</a> — '
                              f'dès {fr_price(n["fuels"][f]["min"])} €/L · à {fr_km(n["dist"])}</li>' for n in nb) + "</ul></section>")
    others = [g for g in FUELS if g != f and (g, c["slug"]) in ctx["fuel_pages"]]
    links = [f'<li><a href="{rel(cur, city_path)}">Tous les carburants {a_ville(nom)}</a></li>']
    links += [f'<li><a href="{rel(cur, city_path + FUEL_SLUG[g] + "/")}">Prix {FUEL_DE[g]} {a_ville(nom)}</a></li>' for g in others]
    body.append('<section aria-labelledby="autres"><h2 id="autres">Autres carburants</h2><ul class="plain">' + "".join(links) + "</ul></section>")
    body.append(faq_html(faq, f"Questions fréquentes : {FUEL_LE[f]} {a_ville(nom)}"))
    body.append(source_line(ctx["latest"]))
    body.append("</main>")
    body.append(f'<a class="cta-primary" href="{rel(cur, "/france/")}">{esc(cfg["cta_final_txt"])}</a>')
    body.append(f'<footer><a href="{rel(cur, "/")}">CarburantRadar</a> — {esc(cfg["footer_txt"])}</footer>\n</div>')
    desc = fit_desc([f"Prix {FUEL_DE[f]} {a_ville(nom)} : dès {fr_price(st['min'])} €/L, moyenne {fr_price(st['avg'])} €/L sur {st['n']} stations.",
                     "Classement des stations les moins chères et économie possible sur un plein."])
    ld = [bc_ld, faq_ld(faq)]
    return shell(lang="fr", title=title, desc=desc, canonical=SITE_URL + cur, robots="index, follow", cur=cur,
                 head_extra="\n".join(ld), body="\n".join(body)), title, desc
