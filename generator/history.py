"""Historique des prix moyens : un instantané par jour, enregistré par CarburantRadar lui-même.

Rien n'est reconstitué ni extrapolé : une évolution n'est affichée que si au moins deux jours réellement enregistrés,
avec la même portée (commune ou rayon), sont disponibles. Le fichier est conservé dans le dépôt par l'Action.
"""
import json
import os

from geo import fr_price, fr_cents
from render_common import esc
from render_fr import FUEL_LE, where_short, where
import fr_blocks

HISTORY_DAYS = 30                                   # nombre de jours conservés
HISTORY_PATH = os.path.join("france", "prix-carburant", "history.json")


def load(root):
    p = os.path.join(root, HISTORY_PATH)
    try:
        h = json.load(open(p, encoding="utf-8"))
        if isinstance(h, dict) and isinstance(h.get("days"), dict):
            return h
    except (OSError, ValueError):
        pass
    return {"version": 1, "days": {}}


def snapshot(cities):
    """{slug: {carburant: [portée, nb_stations, moyenne, minimum]}} pour les villes disposant de prix."""
    out = {}
    for c in cities:
        row = {f: [c["scope"][0], st["n"], st["avg"], st["min"]] for f, st in c["fuels"].items()}
        if row:
            out[c["slug"]] = row
    return out


def update(hist, day, snap, keep=HISTORY_DAYS):
    hist["days"][day] = snap
    for old in sorted(hist["days"])[:-keep]:
        del hist["days"][old]
    return hist


def save(root, hist):
    p = os.path.join(root, HISTORY_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(hist, f, sort_keys=True, separators=(",", ":"))
        f.write("\n")


def series(hist, slug, fuel, scope):
    """[(jour, moyenne, minimum, nb)] triés, uniquement les jours de même portée."""
    rows = []
    for day in sorted(hist["days"]):
        e = hist["days"][day].get(slug, {}).get(fuel)
        if e and e[0] == scope:
            rows.append((day, e[2], e[3], e[1]))
    return rows


def fr_day(day):
    return f"{day[8:10]}/{day[5:7]}/{day[0:4]}"


def _delta(diff):
    if abs(diff) < 0.0005:
        return "stable"
    word = "en hausse" if diff > 0 else "en baisse"
    return f"{word} de {fr_cents(abs(diff))} centime{'s' if abs(diff) * 100 >= 2 else ''} par litre"


def city_section(c, hist):
    """Blocs HTML d'une page ville : sections de données (code postal, autoroute, répartition, équipements) puis « évolution » si l'historique le permet."""
    return fr_blocks.city_blocks(c, hist, series, fr_day)


def fuel_section(c, f, hist):
    """Bloc HTML pour une page ville + carburant : tableau des jours enregistrés."""
    s = series(hist, c["slug"], f, c["scope"][0])
    if len(s) < 2:
        return ""
    rows = "".join(f'<tr><th scope="row">{fr_day(d)}</th><td>{fr_price(a)}</td><td class="min">{fr_price(m)}</td><td>{n}</td></tr>'
                   for d, a, m, n in reversed(s[-15:]))
    (d0, a0, _, _), (d1, a1, _, _) = s[0], s[-1]
    intro = (f"Depuis le {fr_day(d0)}, la moyenne {where_short(c)} pour {FUEL_LE[f]} est passée de {fr_price(a0)} à {fr_price(a1)} €/L, "
             f"soit {_delta(a1 - a0)}.")
    return ('<section aria-labelledby="evolution"><h2 id="evolution">Évolution récente du prix moyen</h2>'
            f"<p>{esc(intro)}</p>"
            f'<div class="tablewrap"><table><caption>Prix en €/L relevés {esc(where(c))}, un relevé par jour enregistré</caption><thead><tr>'
            '<th scope="col">Jour</th><th scope="col">Moyen</th><th scope="col">Le plus bas</th><th scope="col">Stations</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>"
            '<p class="note">Historique enregistré par CarburantRadar (30 jours au maximum) ; les jours sans relevé n\'apparaissent pas.</p></section>\n')


def inject(html, block):
    """Insère le bloc avant la FAQ (ou avant la mention de source)."""
    if not block:
        return html
    for marker in ('<section class="faq"', '<p class="updated">'):
        if marker in html:
            return html.replace(marker, block + marker, 1)
    return html
