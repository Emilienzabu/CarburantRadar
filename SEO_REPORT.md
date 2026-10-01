# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 01/10/2026 07:30 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 422 |
| Pages villes (France) | 176 dont 175 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 73 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 151 |
| — dont Gazole | 58 |
| — dont SP95 | 2 |
| — dont SP98 | 34 |
| — dont E10 | 47 |
| — dont E85 | 9 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 206 villes, 2 hubs |
| URLs dans le sitemap | 634 |
| Stations analysées (jeu de données) | 9804 |
| Jours d'historique enregistrés | 2 (du 2026-09-30 au 2026-10-01) |

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 422 / 422 |
| Meta descriptions | 422 / 422 |
| H1 | 422 / 422 |
| Canonicals | 422 / 422 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 19
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4250 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 1

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 178 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 188 | 6 |
| Drancy | 100 | 144 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Gourdon (46) | 46 | 6 | 4 |
| Abbeville | 47 | 7 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 33 % (min 21 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 24 % (min 14 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 37 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 4
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /guide/ : FAQPage JSON-LD ne correspond pas au contenu visible
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

