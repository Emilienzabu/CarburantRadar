# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 06/11/2026 13:38 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 431 |
| Pages villes (France) | 182 dont 181 indexables et 1 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 154 |
| — dont Gazole | 65 |
| — dont SP95 | 2 |
| — dont SP98 | 31 |
| — dont E10 | 47 |
| — dont E85 | 9 |
| — dont GPL | 0 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 558 villes, 52 hubs |
| URLs dans le sitemap | 890 |
| Stations analysées (jeu de données) | 9828 |
| Jours d'historique enregistrés | 30 (du 2026-10-05 au 2026-11-06) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11474 stations exploitables ; données du 06/11/2026 13:05 UTC.
- Pages villes : 455 dont 454 indexables (352 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- **Source indisponible, pages historiques conservées** : RuntimeError: RuntimeError: Téléchargement impossible de prezzo_alle_8.csv (<urlopen error timed out>) ; cache indisponible (https://carburantradar.fr/donnees/italie-prezzi.json.gz : HTTP Error 404: Not Found)
- Diagnostic : {}

## IndexNow (Bing, Yandex, Naver, Seznam)

- 385 URLs signalées ; réponses HTTP : api.indexnow.org 200 (200 ou 202 = accepté).

## Correctifs appliqués aux applications

- france : véhicules et classement par coût total : appliqué
- espagne : véhicules et classement par coût total : appliqué
- italie : véhicules et classement par coût total : appliqué

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 431 / 431 |
| Meta descriptions | 431 / 431 |
| H1 | 431 / 431 |
| Canonicals | 431 / 431 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 1
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4351 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 2

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 76 | 6 |
| Asnières-sur-Seine | 100 | 177 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 186 | 6 |
| Drancy | 100 | 143 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |
| Thonon-les-Bains | 46 | 6 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 50 % (min 40 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 34 % (min 24 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 45 % (min 34 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

