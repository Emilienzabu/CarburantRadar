"""Sections de données des pages villes France, présentées en tableaux (mêmes données et mêmes seuils qu'avant, moins de phrases-modèles).

Remplace pour la France : extras.dist_block / svc_block, enrich.cp_section / autoroute_section et le texte d'évolution de history.
L'Espagne et l'Italie gardent extras.sections (textes es / it).
"""
import statistics
from collections import Counter, defaultdict

from data_fr import FUEL_LABEL
from enrich import _commune_stations, MIN_PER_CP, MAX_CP_ROWS, MIN_AUTOROUTE, MIN_OTHER
from extras import MIN_FUEL_STATIONS, ORDER, EL, DE, SVC_KEYS, T, _pct
from geo import fr_price, fr_cents
from render_common import esc
from render_fr import REF_ORDER, a_ville, de_ville, where_short, _signed

FR = T["fr"]


def _kv_table(caption, rows):
    body = "".join(f'<tr><th scope="row">{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in rows)
    return f'<div class="tablewrap"><table><caption>{esc(caption)}</caption><tbody>{body}</tbody></table></div>'


def dist_table(c):
    """Répartition des prix (quartiles, part sous la moyenne nationale, classements) pour le premier carburant éligible."""
    x = c.get("x") or {}
    sts = _commune_stations(c) or [s for _, s in c["near"]]
    for f in ORDER["fr"]:
        vals = sorted(s["p"][f] for s in sts if f in s["p"])
        if len(vals) < MIN_FUEL_STATIONS:
            continue
        q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
        nat = (x.get("nat_avg") or {}).get(f)
        if nat is None:
            continue
        under = sum(1 for v in vals if v < nat)
        rows = [("Médiane", f"{fr_price(med)} €/L"), ("1er quartile", f"{fr_price(q1)} €/L"), ("3e quartile", f"{fr_price(q3)} €/L"),
                ("Moyenne nationale", f"{fr_price(nat)} €/L"),
                ("Stations sous la moyenne nationale", f"{under} sur {len(vals)} ({_pct('fr', round(100 * under / len(vals)))})")]
        r = (x.get("rank") or {}).get(f)
        if r:
            rows.append(("Classement national", f"n° {r['nat'][0]} sur {r['nat'][1]}"))
            if r.get("dep") and x.get("dep_label"):
                rows.append((f"Classement dans le département {x['dep_label']}", f"n° {r['dep'][0]} sur {r['dep'][1]}"))
        h = FR["dist_h"].format(de_fuel=DE["fr"][f], a_nom=a_ville(c["nom"]), nom=c["nom"])
        note = f"Classements : villes couvertes où {EL['fr'][f]} est relevé dans au moins {MIN_FUEL_STATIONS} stations ; n° 1 = la moins chère (prix moyen)."
        return (f'<section aria-labelledby="repartition"><h2 id="repartition">{esc(h)}</h2>'
                + _kv_table(f"Prix {DE['fr'][f]} en €/L, stations {where_short(c)}", rows)
                + f'<p class="note">{esc(note)}</p></section>\n')
    return ""


def svc_table(c):
    sts = [s for s in _commune_stations(c) if s.get("svc")]
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
    items = sorted(((cnt[k], k) for k, _ in SVC_KEYS if cnt[k] > 0), key=lambda it: (-it[0], it[1]))[:5]
    if not items:
        return ""
    n = len(sts)
    body = "".join(f'<tr><th scope="row">{esc(FR["svc_names"][key][:1].upper() + FR["svc_names"][key][1:])}</th><td>{k}</td>'
                   f'<td>{_pct("fr", round(100 * k / n))}</td></tr>' for k, key in items)
    a24 = sum(1 for s in _commune_stations(c) if s.get("a24"))
    h = FR["svc_h"].format(de_nom=de_ville(c["nom"]))
    return (f'<section aria-labelledby="equipements"><h2 id="equipements">{esc(h)}</h2>'
            f'<div class="tablewrap"><table><caption>Services des {n} stations {where_short(c)} dont les services sont renseignés</caption>'
            '<thead><tr><th scope="col">Équipement</th><th scope="col">Stations</th><th scope="col">Part</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>"
            + (f"<p>{esc(FR['a24'].format(k=a24))}</p>" if a24 else "")
            + f'<p class="note">{esc(FR["svc_note"])}</p></section>\n')


def autoroute_table(c):
    near = c["near"]
    if not any(s.get("pop") == "A" for _, s in near):
        return ""
    for f in [x for x in REF_ORDER if x in c["fuels"]]:
        auto = [s["p"][f] for _, s in near if s.get("pop") == "A" and f in s["p"]]
        other = [s["p"][f] for _, s in near if s.get("pop") != "A" and f in s["p"]]
        if len(auto) < MIN_AUTOROUTE or len(other) < MIN_OTHER:
            continue
        a, o = sum(auto) / len(auto), sum(other) / len(other)
        rows = (f'<tr><th scope="row">Autoroute</th><td>{len(auto)}</td><td>{fr_price(a)}</td></tr>'
                f'<tr><th scope="row">Autres stations</th><td>{len(other)}</td><td>{fr_price(o)}</td></tr>'
                f'<tr><th scope="row">Écart (autoroute − autres)</th><td></td><td>{_signed(a - o)} c/L</td></tr>')
        return ('<section aria-labelledby="autoroute"><h2 id="autoroute">Autoroute ou route : l\'écart de prix autour {}</h2>'.format(esc(de_ville(c["nom"])))
                + f'<div class="tablewrap"><table><caption>{esc(FUEL_LABEL[f])} : prix moyen en €/L, stations de la zone</caption>'
                '<thead><tr><th scope="col">Zone</th><th scope="col">Stations</th><th scope="col">Prix moyen</th></tr></thead>'
                f"<tbody>{rows}</tbody></table></div>"
                '<p class="note">Le jeu de données officiel distingue les stations d\'autoroute des stations sur route.</p></section>\n')
    return ""


def cp_table(c):
    sts = _commune_stations(c)
    if not sts:
        return ""
    for f in [x for x in REF_ORDER if x in c["fuels"]]:
        g = defaultdict(list)
        for s in sts:
            if f in s["p"] and s["cp"]:
                g[s["cp"]].append(s["p"][f])
        rows = [(cp, v) for cp, v in g.items() if len(v) >= MIN_PER_CP]
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda r: (-len(r[1]), r[0]))[:MAX_CP_ROWS]
        stats = sorted(((round(sum(v) / len(v), 3), min(v), len(v), cp) for cp, v in rows))
        if stats[-1][0] - stats[0][0] < 0.0005:
            continue
        tr = "".join(f'<tr><th scope="row">{esc(cp)}</th><td class="min">{fr_price(mn)}</td><td>{fr_price(avg)}</td><td>{n}</td></tr>'
                     for avg, mn, n, cp in stats)
        return (f'<section aria-labelledby="codes-postaux"><h2 id="codes-postaux">Prix par code postal : {esc(FUEL_LABEL[f])}</h2>'
                f'<div class="tablewrap"><table><caption>{esc(FUEL_LABEL[f])} : prix en €/L par code postal, stations de la commune, '
                f'du moins cher au plus cher en moyenne ; écart entre les extrêmes : {fr_cents(stats[-1][0] - stats[0][0])} centimes par litre</caption>'
                '<thead><tr><th scope="col">Code postal</th><th scope="col">Le plus bas</th><th scope="col">Moyen</th>'
                f'<th scope="col">Stations</th></tr></thead><tbody>{tr}</tbody></table></div>'
                f'<p class="note">Seuls les codes postaux comptant au moins {MIN_PER_CP} stations avec un prix sont affichés.</p></section>\n')
    return ""


def evolution_table(c, hist, series, fr_day):
    """Évolution des moyennes enregistrées (au plus 3 carburants)  ; chaîne vide si l'historique ne permet pas d'affirmer quoi que ce soit."""
    scope = c["scope"][0]
    rows, first_day = [], None
    for f in [x for x in REF_ORDER if x in c["fuels"]][:3]:
        s = series(hist, c["slug"], f, scope)
        if len(s) < 2:
            continue
        (d0, a0, _, _), (d1, a1, _, _) = s[0], s[-1]
        first_day = d0 if first_day is None or d0 < first_day else first_day
        rows.append(f'<tr><th scope="row">{esc(FUEL_LABEL[f])}</th><td>{fr_day(d0)}</td><td>{fr_price(a0)}</td>'
                    f'<td>{fr_day(d1)}</td><td>{fr_price(a1)}</td><td>{_signed(a1 - a0)}</td></tr>')
    if not rows:
        return ""
    return ('<section aria-labelledby="evolution"><h2 id="evolution">Évolution récente des prix moyens</h2>'
            f'<div class="tablewrap"><table><caption>Prix moyen en €/L relevé {esc(where_short(c))} ; variation en centimes par litre</caption>'
            '<thead><tr><th scope="col">Carburant</th><th scope="col">Du</th><th scope="col">Moyenne</th><th scope="col">Au</th>'
            '<th scope="col">Moyenne</th><th scope="col">Variation</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
            f'<p class="note">Historique enregistré par CarburantRadar chaque jour depuis le {fr_day(first_day)} (30 jours au maximum). '
            "Les jours sans relevé n'apparaissent pas.</p></section>\n")


def city_blocks(c, hist, series, fr_day):
    return cp_table(c) + autoroute_table(c) + dist_table(c) + svc_table(c) + evolution_table(c, hist, series, fr_day)
