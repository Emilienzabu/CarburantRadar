# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 07/10/2026 00:15 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 419 |
| Pages villes (France) | 181 dont 180 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 78 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 143 |
| — dont Gazole | 58 |
| — dont SP95 | 2 |
| — dont SP98 | 32 |
| — dont E10 | 43 |
| — dont E85 | 7 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1265 villes, 159 hubs |
| URLs dans le sitemap | 1703 |
| Stations analysées (jeu de données) | 9842 |
| Jours d'historique enregistrés | 8 (du 2026-09-30 au 2026-10-07) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11495 stations exploitables ; données du 06/10/2026 22:44 UTC.
- Pages villes : 456 dont 455 indexables (353 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- Source : CSV du MIMIT ; 21456 stations exploitables ; données du 05/10/2026 08:09 UTC.
- Pages villes : 809 dont 809 indexables (706 ajoutées automatiquement) ; pages provinces : 107.

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 419 / 419 |
| Meta descriptions | 419 / 419 |
| H1 | 419 / 419 |
| Canonicals | 419 / 419 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4247 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 2

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 179 | 6 |
| Cergy | 100 | 55 | 6 |
| Clichy | 100 | 189 | 6 |
| Drancy | 100 | 146 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |
| Abbeville | 47 | 7 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 42 % (min 28 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 26 % (min 15 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 37 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

