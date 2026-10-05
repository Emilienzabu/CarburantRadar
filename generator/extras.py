"""Sections de données propres à chaque ville, communes aux trois pays (textes fr / es / it) :

  - répartition des prix (quartiles, part des stations sous la moyenne nationale) ;
  - classement de la ville parmi les villes couvertes (au niveau national et du département / de la province) ;
  - équipements des stations (France : services renseignés dans le flux officiel) ;
  - répartition par enseigne et prix moyen par enseigne (Espagne, Italie : le jeu de données indique la marque) ;
  - écart self-service / servito (Italie).

Tout est calculé à partir du jeu de données officiel ; une section n'est écrite que si les données la rendent significative.
"""
import statistics
from collections import Counter, defaultdict

from geo import fr_price, fr_cents, plural, join_fr
from render_common import esc

MIN_FUEL_STATIONS = 5     # stations avec un prix pour parler de répartition ou de classement
MIN_RANK_CITIES = 3       # villes comparables pour un classement départemental
MIN_BRAND = 3             # stations d'une même enseigne pour comparer les prix moyens
ORDER = {"fr": ["gazole", "e10", "sp95", "sp98"], "es": ["gazole", "sp95", "e10", "sp98", "gplc"], "it": ["gazole", "sp95", "gplc"]}

T = {
    "fr": {
        "and": "et", "pct": "{p} %", "ref": "pour {fuel}", "rank_h": "Classement de {nom} parmi les villes couvertes",
        "dist_h": "Répartition des prix {de_fuel} {a_nom}",
        "dist": "Pour {el}, la moitié des stations {where} le relèvent à moins de {med} €/L (médiane) ; un quart sont sous {q1} €/L et un quart au-dessus de {q3} €/L. "
                "{k} stations sur {n} ({pct}) sont sous la moyenne nationale de {nat} €/L.",
        "rank": "Parmi les {N} villes couvertes par CarburantRadar où {el} est relevé dans au moins {m} stations, {nom} est n° {r} (n° 1 = la moins chère, d'après le prix moyen){dep}.",
        "rank_dep": " ; dans le département {dep_label}, elle est n° {r2} sur {N2}",
        "svc_h": "Équipements des stations {de_nom}",
        "svc": "Sur les {n} stations {where} dont les services sont renseignés dans le jeu de données officiel, les équipements les plus fréquents sont : {items}.",
        "svc_item": "{what} ({k} stations, {p})",
        "svc_names": {"toilets": "toilettes publiques", "wash": "lavage", "shop": "boutique alimentaire", "food": "restauration",
                      "air": "station de gonflage", "atm": "distributeur de billets", "wifi": "wifi", "ev": "bornes de recharge électrique",
                      "camper": "aire pour camping-cars"},
        "a24": "{k} fonctionnent 24 h/24.",
        "svc_note": "Services déclarés par les exploitants dans le jeu de données officiel.",
    },
    "es": {
        "and": "y", "pct": "{p} %", "ref": "para {fuel}", "rank_h": "Clasificación de {nom} entre las ciudades cubiertas",
        "dist_h": "Distribución de los precios {de_fuel} en {nom}",
        "dist": "Para {el}, la mitad de las gasolineras {where} lo registran por debajo de {med} €/L (mediana); una cuarta parte está por debajo de {q1} €/L y otra cuarta parte por encima de {q3} €/L. "
                "{k} de {n} gasolineras ({pct}) están por debajo de la media nacional de {nat} €/L.",
        "rank": "Entre las {N} ciudades cubiertas por CarburantRadar donde {el} se registra en al menos {m} gasolineras, {nom} ocupa el puesto n.º {r} (n.º 1 = la más barata, según el precio medio){dep}.",
        "rank_dep": "; en la provincia de {dep_label}, ocupa el puesto n.º {r2} de {N2}",
        "brand_h": "Marcas de las gasolineras en {nom}",
        "brand": "Las marcas más presentes {where} son {items}.",
        "brand_cmp": "Para {el}, entre las marcas con al menos {m} gasolineras con precio, la más barata de media es {lo} ({lo_p} €/L, {lo_n} gasolineras) y la más cara {hi} ({hi_p} €/L, {hi_n} gasolineras): {diff} céntimos por litro de diferencia.",
        "brand_note": "La marca (rótulo) procede de los datos oficiales del Ministerio.",
    },
    "it": {
        "and": "e", "pct": "{p}%", "ref": "per {fuel}", "rank_h": "Posizione di {nom} tra le città coperte",
        "dist_h": "Distribuzione dei prezzi {de_fuel} {a_nom}",
        "dist": "Per {el}, la metà dei distributori {where} lo rileva sotto {med} €/L (mediana); un quarto è sotto {q1} €/L e un quarto sopra {q3} €/L. "
                "{k} distributori su {n} ({pct}) sono sotto la media nazionale di {nat} €/L.",
        "rank": "Tra le {N} città coperte da CarburantRadar in cui {el} è rilevato in almeno {m} distributori, {nom} è al n. {r} (n. 1 = la più economica, in base al prezzo medio){dep}.",
        "rank_dep": "; in provincia di {dep_label}, è al n. {r2} su {N2}",
        "brand_h": "Bandiere dei distributori {a_nom}",
        "brand": "Le bandiere più presenti {where} sono {items}.",
        "brand_cmp": "Per {el}, tra le bandiere con almeno {m} distributori con un prezzo, la più economica in media è {lo} ({lo_p} €/L, {lo_n} distributori) e la più cara {hi} ({hi_p} €/L, {hi_n} distributori): {diff} centesimi al litro di differenza.",
        "brand_note": "La bandiera (marchio) proviene dai dati ufficiali del MIMIT.",
        "self_h": "Self-service o servito {a_nom}",
        "self": "Per {el}, sui {n} distributori {where} che espongono sia il prezzo self sia quello servito, il self costa in media {sp} €/L e il servito {vp} €/L: {diff} centesimi al litro di differenza.",
        "self_only": " {k} distributori su {n} espongono solo il prezzo servito.",
        "self_note": "Dove un distributore espone entrambi i prezzi, le pagine usano il prezzo self.",
    },
}
EL = {
    "fr": {"gazole": "le gazole", "sp95": "le SP95", "sp98": "le SP98", "e10": "l'E10", "e85": "l'E85", "gplc": "le GPL"},
    "es": {"gazole": "el gasóleo A", "sp95": "la gasolina 95 E5", "e10": "la gasolina 95 E10", "sp98": "la gasolina 98 E5", "e85": "el bioetanol E85", "gplc": "el GLP"},
    "it": {"gazole": "il gasolio", "sp95": "la benzina", "sp98": "la SP98", "e10": "l'E10", "e85": "il metano", "gplc": "il GPL"},
}
DE = {
    "fr": {"gazole": "du gazole", "sp95": "du SP95", "sp98": "du SP98", "e10": "de l'E10", "e85": "de l'E85", "gplc": "du GPL"},
    "es": {"gazole": "del gasóleo A", "sp95": "de la gasolina 95 E5", "e10": "de la gasolina 95 E10", "sp98": "de la gasolina 98 E5", "e85": "del bioetanol E85", "gplc": "del GLP"},
    "it": {"gazole": "del gasolio", "sp95": "della benzina", "sp98": "della SP98", "e10": "dell'E10", "e85": "del metano", "gplc": "del GPL"},
}


def _pct(lang, p):
    return T[lang]["pct"].format(p=p)


def _stations(c):
    from enrich import _commune_stations
    return _commune_stations(c)


def annotate(cities, dep_info, nat, lang):
    """Calcule pour chaque ville les classements (national et départemental) et les données de contexte utilisées par les sections."""
    idx = [c for c in cities if c.get("indexable")]
    for f in ORDER[lang]:
        ok = [c for c in idx if f in c["fuels"] and c["fuels"][f]["n"] >= MIN_FUEL_STATIONS]
        ranked = sorted(ok, key=lambda c: (c["fuels"][f]["avg"], c["slug"]))
        by_dep = defaultdict(list)
        for c in ranked:
            by_dep[c["dep_code"]].append(c)
        for pos, c in enumerate(ranked, 1):
            x = c.setdefault("x", {"rank": {}})
            dep = by_dep[c["dep_code"]]
            dpos = [d["slug"] for d in dep].index(c["slug"]) + 1
            x["rank"][f] = {"nat": (pos, len(ranked)), "dep": (dpos, len(dep)) if len(dep) >= MIN_RANK_CITIES and c["dep_code"] else None}
    for c in cities:
        x = c.setdefault("x", {"rank": {}})
        d = dep_info.get(c["dep_code"])
        x["dep_label"] = d["name"] if d else ""
        x["nat_avg"] = {f: nat[f]["avg"] for f in nat}


def _where(lang, c):
    from enrich import _commune_stations  # noqa: F401  (import tardif pour éviter les cycles)
    if lang == "fr":
        from render_fr import where_short
    elif lang == "es":
        from render_es import where_short
    else:
        from render_it import where_short
    return where_short(c)


def _a_nom(c, lang):
    if lang == "fr":
        from render_fr import a_ville
        return a_ville(c["nom"])
    if lang == "it":
        from render_it import a_
        return a_(c["nom"])
    return c["nom"]


def _de_nom(c):
    from render_fr import de_ville
    return de_ville(c["nom"])


def dist_block(c, lang):
    t, x = T[lang], c.get("x") or {}
    sts = _stations(c)
    if not sts:
        sts = [s for _, s in c["near"]]
    for f in ORDER[lang]:
        vals = sorted(s["p"][f] for s in sts if f in s["p"])
        if len(vals) < MIN_FUEL_STATIONS:
            continue
        q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
        nat = (x.get("nat_avg") or {}).get(f)
        if nat is None:
            continue
        under = sum(1 for v in vals if v < nat)
        parts = [t["dist"].format(el=EL[lang][f], where=_where(lang, c), med=fr_price(med), q1=fr_price(q1), q3=fr_price(q3), k=under, n=len(vals),
                                  pct=_pct(lang, round(100 * under / len(vals))), nat=fr_price(nat))]
        r = (x.get("rank") or {}).get(f)
        if r:
            dep = ""
            if r.get("dep") and x.get("dep_label"):
                dep = t["rank_dep"].format(dep_label=x["dep_label"], r2=r["dep"][0], N2=r["dep"][1])
            parts.append(t["rank"].format(N=r["nat"][1], el=EL[lang][f], m=MIN_FUEL_STATIONS, nom=c["nom"], r=r["nat"][0], dep=dep))
        h = t["dist_h"].format(de_fuel=DE[lang][f], a_nom=_a_nom(c, lang), nom=c["nom"])
        return f'<section aria-labelledby="repartition"><h2 id="repartition">{esc(h)}</h2>' + "".join(f"<p>{esc(p)}</p>" for p in parts) + "</section>\n"
    return ""


SVC_KEYS = [("toilets", ("toilette",)), ("wash", ("lavage",)), ("shop", ("boutique alimentaire",)), ("food", ("restauration",)),
            ("air", ("gonflage",)), ("atm", ("dab", "distributeur automatique de billets")), ("wifi", ("wifi",)),
            ("ev", ("borne", "recharge")), ("camper", ("camping",))]


def svc_block(c, lang):
    if lang != "fr":
        return ""
    t = T["fr"]
    sts = [s for s in _stations(c) if s.get("svc")]
    if len(sts) < MIN_FUEL_STATIONS:
        return ""
    cnt = Counter()
    for s in sts:
        seen = set()
        for sv in s["svc"]:
            for key, pats in SVC_KEYS:
                if any(p in sv for p in pats):
                    seen.add(key)
        cnt.update(seen)
    items = [(cnt[k], k) for k, _ in SVC_KEYS if cnt[k] > 0]
    items.sort(key=lambda it: (-it[0], it[1]))
    items = items[:5]
    if not items:
        return ""
    n = len(sts)
    txt = [t["svc_item"].format(k=k, p=_pct("fr", round(100 * k / n)), what=t["svc_names"][key]) for k, key in items]
    p1 = t["svc"].format(n=n, where=_where("fr", c), items=join_fr(txt, "et"))
    a24 = sum(1 for s in _stations(c) if s.get("a24"))
    if a24:
        p1 += " " + t["a24"].format(k=a24)
    h = t["svc_h"].format(de_nom=_de_nom(c))
    return (f'<section aria-labelledby="equipements"><h2 id="equipements">{esc(h)}</h2><p>{esc(p1)}</p>'
            f'<p class="note">{esc(t["svc_note"])}</p></section>\n')


def brand_block(c, lang):
    if lang not in ("es", "it"):
        return ""
    t = T[lang]
    sts = [s for s in _stations(c) if s.get("brand")]
    if len(sts) < MIN_FUEL_STATIONS:
        return ""
    cnt = Counter(s["brand"] for s in sts)
    top = cnt.most_common(5)
    if len(cnt) < 2:
        return ""
    p1 = t["brand"].format(where=_where(lang, c), items=join_fr([f"{b} ({n})" for b, n in top], t["and"]))
    paras = [p1]
    for f in ORDER[lang]:
        by = defaultdict(list)
        for s in sts:
            if f in s["p"]:
                by[s["brand"]].append(s["p"][f])
        rows = [(sum(v) / len(v), b, len(v)) for b, v in by.items() if len(v) >= MIN_BRAND]
        if len(rows) >= 2:
            rows.sort()
            (lo_p, lo, lo_n), (hi_p, hi, hi_n) = rows[0], rows[-1]
            if hi_p - lo_p >= 0.0005:
                paras.append(t["brand_cmp"].format(el=EL[lang][f], m=MIN_BRAND, lo=lo, lo_p=fr_price(lo_p), lo_n=lo_n, hi=hi, hi_p=fr_price(hi_p),
                                                   hi_n=hi_n, diff=fr_cents(hi_p - lo_p)))
                break
    h = t["brand_h"].format(nom=c["nom"], a_nom=_a_nom(c, lang))
    return (f'<section aria-labelledby="marcas"><h2 id="marcas">{esc(h)}</h2>' + "".join(f"<p>{esc(p)}</p>" for p in paras)
            + f'<p class="note">{esc(t["brand_note"])}</p></section>\n')


def self_block(c, lang):
    if lang != "it":
        return ""
    t = T["it"]
    sts = _stations(c) or [s for _, s in c["near"]]
    for f in ORDER["it"]:
        both = [s for s in sts if f in s.get("pself", {}) and f in s.get("pserv", {})]
        if len(both) < 3:
            continue
        sp = sum(s["pself"][f] for s in both) / len(both)
        vp = sum(s["pserv"][f] for s in both) / len(both)
        if vp - sp < 0.0005:
            continue
        only = sum(1 for s in sts if f in s.get("pserv", {}) and f not in s.get("pself", {}))
        n_all = sum(1 for s in sts if f in s["p"])
        txt = t["self"].format(el=EL["it"][f], n=len(both), where=_where("it", c), sp=fr_price(sp), vp=fr_price(vp), diff=fr_cents(vp - sp))
        if only:
            txt += t["self_only"].format(k=only, n=n_all)
        return (f'<section aria-labelledby="self"><h2 id="self">{esc(t["self_h"].format(nom=c["nom"], a_nom=_a_nom(c, "it")))}</h2><p>{esc(txt)}</p>'
                f'<p class="note">{esc(t["self_note"])}</p></section>\n')
    return ""


def sections(c, lang):
    return dist_block(c, lang) + svc_block(c, lang) + brand_block(c, lang) + self_block(c, lang)
