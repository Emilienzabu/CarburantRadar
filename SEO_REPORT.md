# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 04/10/2026 22:00 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 391 |
| Pages villes (France) | 181 dont 179 indexables et 2 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 78 |
| Pages départements | 80 |
| Pages régions | 13 |
| Pages ville + carburant | 116 |
| — dont Gazole | 51 |
| — dont SP95 | 2 |
| — dont SP98 | 24 |
| — dont E10 | 31 |
| — dont E85 | 7 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1264 villes, 159 hubs |
| URLs dans le sitemap | 1700 |
| Stations analysées (jeu de données) | 9829 |
| Jours d'historique enregistrés | 5 (du 2026-09-30 au 2026-10-04) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11464 stations exploitables ; données du 04/10/2026 20:43 UTC.
- Pages villes : 455 dont 454 indexables (352 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- Source : CSV du MIMIT ; 21459 stations exploitables ; données du 03/10/2026 08:02 UTC.
- Pages villes : 809 dont 809 indexables (706 ajoutées automatiquement) ; pages provinces : 107.

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 391 / 391 |
| Meta descriptions | 391 / 391 |
| H1 | 391 / 391 |
| Canonicals | 391 / 391 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 2
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 3975 ; moyenne par page : 10.2
- Pages orphelines indexables : 0 ; pages noindex non liées : 3

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
| Troyes | 40 | 5 | 3 |
| La Rochelle | 44 | 4 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |
| Belfort | 46 | 6 | 6 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 33 % (min 23 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 29 % (min 18 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 35 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 4
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /guide/ : FAQPage JSON-LD ne correspond pas au contenu visible
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

