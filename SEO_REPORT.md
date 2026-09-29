# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 30/09/2026 00:15 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 298 |
| Pages villes (France) | 103 dont 102 indexables et 1 en noindex |
| Pages départements | 58 |
| Pages régions | 13 |
| Pages ville + carburant | 123 |
| — dont Gazole | 45 |
| — dont SP95 | 2 |
| — dont SP98 | 28 |
| — dont E10 | 34 |
| — dont E85 | 13 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 206 villes, 2 hubs |
| URLs dans le sitemap | 510 |
| Stations analysées (jeu de données) | 9801 |

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 298 / 298 |
| Meta descriptions | 298 / 298 |
| H1 | 298 / 298 |
| Canonicals | 298 / 298 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 24
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 2722 ; moyenne par page : 9.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 1

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 177 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 187 | 6 |
| Drancy | 100 | 144 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Nancy | 45 | 5 | 4 |
| Grenoble | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 36 % (min 24 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 25 % (min 15 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 46 % (min 39 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 4
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /guide/ : FAQPage JSON-LD ne correspond pas au contenu visible
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

