"""Sections de données propres à chaque ville (contenu unique) : prix par code postal, autoroute / hors autoroute.

Tout vient du jeu de données officiel ; une section n'est écrite que si les données la rendent significative.
"""
from collections import defaultdict

from data_fr import FUEL_LABEL
from geo import fr_price, fr_cents, plural, norm_name, same_commune
from render_common import esc
from render_fr import FUEL_LE, REF_ORDER, de_ville, where_short

MIN_PER_CP = 2        # stations avec un prix par code postal pour apparaître dans le tableau
MAX_CP_ROWS = 12
MIN_AUTOROUTE = 1     # stations d'autoroute avec un prix pour comparer
MIN_OTHER = 3         # autres stations avec un prix pour comparer


def _commune_stations(c):
    """Stations de la commune (portée « commune » uniquement)."""
    if c["scope"] != "commune":
        return []
    mem = c["v"].get("_members")
    if mem is not None:
        return list(mem)
    cn = norm_name(c["nom"])
    return [s for _, s in c["near"] if same_commune(norm_name(s["ville"]), cn)]


def cp_section(c):
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
        (a_lo, _, n_lo, cp_lo), (a_hi, _, n_hi, cp_hi) = stats[0], stats[-1]
        if a_hi - a_lo < 0.0005:
            continue
        tr = "".join(f'<tr><th scope="row">{esc(cp)}</th><td class="min">{fr_price(mn)}</td><td>{fr_price(avg)}</td><td>{n}</td></tr>'
                     for avg, mn, n, cp in stats)
        text = (f"Pour {FUEL_LE[f]}, le code postal {cp_lo} est le moins cher en moyenne ({fr_price(a_lo)} €/L sur {plural(n_lo, 'station', 'stations')}) "
                f"et le {cp_hi} le plus cher ({fr_price(a_hi)} €/L sur {plural(n_hi, 'station', 'stations')}) : "
                f"{fr_cents(a_hi - a_lo)} centimes par litre d'écart entre ces deux zones {where_short(c)}.")
        unit = {"gazole": "gazole", "sp95": "SP95", "sp98": "SP98", "e10": "E10", "e85": "E85", "gplc": "GPL"}[f]
        return (f'<section aria-labelledby="codes-postaux"><h2 id="codes-postaux">Prix par code postal : {esc(FUEL_LABEL[f])}</h2>'
                f"<p>{esc(text)}</p>"
                f'<div class="tablewrap"><table><caption>{esc(FUEL_LABEL[f])} : prix en €/L par code postal, stations de la commune</caption>'
                '<thead><tr><th scope="col">Code postal</th><th scope="col">Le plus bas</th><th scope="col">Moyen</th>'
                f'<th scope="col">Stations</th></tr></thead><tbody>{tr}</tbody></table></div>'
                f'<p class="note">Seuls les codes postaux comptant au moins {MIN_PER_CP} stations avec un prix pour {esc(unit)} sont affichés.</p></section>\n')
    return ""


def autoroute_section(c):
    near = c["near"]
    if not any(s.get("pop") == "A" for _, s in near):
        return ""
    for f in [x for x in REF_ORDER if x in c["fuels"]]:
        auto = [s["p"][f] for _, s in near if s.get("pop") == "A" and f in s["p"]]
        other = [s["p"][f] for _, s in near if s.get("pop") != "A" and f in s["p"]]
        if len(auto) < MIN_AUTOROUTE or len(other) < MIN_OTHER:
            continue
        a, o = sum(auto) / len(auto), sum(other) / len(other)
        diff = a - o
        if abs(diff) < 0.0005:
            rel = "au même niveau"
        else:
            rel = f"{fr_cents(abs(diff))} centimes par litre {'de plus' if diff > 0 else 'de moins'}"
        if len(auto) == 1:
            head = f"Pour {FUEL_LE[f]}, la station située sur autoroute relève {fr_price(a)} €/L"
        else:
            head = (f"Pour {FUEL_LE[f]}, {len(auto)} stations situées sur autoroute relèvent un prix moyen de {fr_price(a)} €/L")
        text = (f"{head}, contre {fr_price(o)} €/L en moyenne pour les {len(other)} autres stations de la zone : "
                f"{rel}. Le jeu de données officiel distingue les stations d'autoroute des stations sur route.")
        return ('<section aria-labelledby="autoroute"><h2 id="autoroute">Autoroute ou route : l\'écart de prix autour {}</h2>'.format(esc(de_ville(c["nom"])))
                + f"<p>{esc(text)}</p></section>\n")
    return ""


def city_extras(c):
    return cp_section(c) + autoroute_section(c)
