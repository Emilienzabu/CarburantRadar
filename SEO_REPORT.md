# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 10/10/2026 12:46 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 429 |
| Pages villes (France) | 182 dont 181 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 152 |
| — dont Gazole | 60 |
| — dont SP95 | 2 |
| — dont SP98 | 36 |
| — dont E10 | 46 |
| — dont E85 | 7 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1269 villes, 159 hubs |
| URLs dans le sitemap | 1708 |
| Stations analysées (jeu de données) | 9816 |
| Jours d'historique enregistrés | 11 (du 2026-09-30 au 2026-10-10) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11509 stations exploitables ; données du 10/10/2026 11:16 UTC.
- Pages villes : 458 dont 457 indexables (355 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- Source : CSV du MIMIT ; 21470 stations exploitables ; données du 09/10/2026 08:02 UTC.
- Pages villes : 811 dont 811 indexables (708 ajoutées automatiquement) ; pages provinces : 107.

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 429 / 429 |
| Meta descriptions | 429 / 429 |
| H1 | 429 / 429 |
| Canonicals | 429 / 429 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4348 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 2

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 76 | 6 |
| Asnières-sur-Seine | 100 | 178 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 187 | 6 |
| Drancy | 100 | 143 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |
| Abbeville | 47 | 7 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 49 % (min 35 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 27 % (min 16 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 36 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

