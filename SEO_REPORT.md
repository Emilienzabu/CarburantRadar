# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 01/10/2026 13:39 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 424 |
| Pages villes (France) | 177 dont 176 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 74 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 152 |
| — dont Gazole | 59 |
| — dont SP95 | 2 |
| — dont SP98 | 31 |
| — dont E10 | 49 |
| — dont E85 | 10 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 206 villes, 2 hubs |
| URLs dans le sitemap | 636 |
| Stations analysées (jeu de données) | 9820 |
| Jours d'historique enregistrés | 2 (du 2026-09-30 au 2026-10-01) |

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 424 / 424 |
| Meta descriptions | 424 / 424 |
| H1 | 424 / 424 |
| Canonicals | 424 / 424 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 19
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4284 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 1

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 179 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 189 | 6 |
| Drancy | 100 | 146 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Gourdon (46) | 46 | 6 | 4 |
| Abbeville | 47 | 7 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 33 % (min 23 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 24 % (min 12 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 37 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 4
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /guide/ : FAQPage JSON-LD ne correspond pas au contenu visible
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

