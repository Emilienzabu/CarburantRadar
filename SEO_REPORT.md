# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 03/10/2026 09:50 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 420 |
| Pages villes (France) | 181 dont 180 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 78 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 144 |
| — dont Gazole | 57 |
| — dont SP95 | 2 |
| — dont SP98 | 32 |
| — dont E10 | 43 |
| — dont E85 | 9 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 555 villes, 52 hubs |
| URLs dans le sitemap | 886 |
| Stations analysées (jeu de données) | 9830 |
| Jours d'historique enregistrés | 4 (du 2026-09-30 au 2026-10-03) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11469 stations exploitables ; données du 03/10/2026 08:15 UTC.
- Pages villes : 452 dont 451 indexables (349 ajoutées automatiquement) ; pages provinces : 50.

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 420 / 420 |
| Meta descriptions | 420 / 420 |
| H1 | 420 / 420 |
| Canonicals | 420 / 420 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4290 ; moyenne par page : 10.2
- Pages orphelines indexables : 0 ; pages noindex non liées : 2

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 179 | 6 |
| Cergy | 100 | 54 | 6 |
| Clichy | 100 | 189 | 6 |
| Drancy | 100 | 146 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |
| Belfort | 46 | 6 | 6 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 33 % (min 22 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 25 % (min 15 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 36 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 4
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /guide/ : FAQPage JSON-LD ne correspond pas au contenu visible
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

