# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 18/10/2026 11:17 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 406 |
| Pages villes (France) | 182 dont 179 indexables et 3 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 129 |
| — dont Gazole | 55 |
| — dont SP95 | 2 |
| — dont SP98 | 27 |
| — dont E10 | 38 |
| — dont E85 | 7 |
| — dont GPL | 0 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1269 villes, 159 hubs |
| URLs dans le sitemap | 1706 |
| Stations analysées (jeu de données) | 9804 |
| Jours d'historique enregistrés | 19 (du 2026-09-30 au 2026-10-18) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11422 stations exploitables ; données du 18/10/2026 09:45 UTC.
- Pages villes : 458 dont 457 indexables (355 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- **Source indisponible : 919 pages indexables de la veille réutilisées** : RuntimeError: RuntimeError: Téléchargement impossible de prezzo_alle_8.csv (<urlopen error timed out>) ; cache indisponible (cache trop ancien (3.1 j))

## IndexNow (Bing, Yandex, Naver, Seznam)

- 1706 URLs signalées ; réponses HTTP : api.indexnow.org 200 (200 ou 202 = accepté).

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 406 / 406 |
| Meta descriptions | 406 / 406 |
| H1 | 406 / 406 |
| Canonicals | 406 / 406 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 3
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4087 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 4

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 169 | 6 |
| Cergy | 100 | 52 | 6 |
| Clichy | 100 | 177 | 6 |
| Drancy | 100 | 139 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| Roubaix | 43 | 3 | 4 |
| Ivry-sur-Seine | 43 | 3 | 4 |
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Orléans | 45 | 5 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 49 % (min 38 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 31 % (min 17 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 35 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

