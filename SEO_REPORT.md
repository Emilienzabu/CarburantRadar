# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 14/11/2026 13:09 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 454 |
| Pages villes (France) | 184 dont 181 indexables et 3 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 81 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 175 |
| — dont Gazole | 67 |
| — dont SP95 | 2 |
| — dont SP98 | 45 |
| — dont E10 | 52 |
| — dont E85 | 9 |
| — dont GPL | 0 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 562 villes, 52 hubs |
| URLs dans le sitemap | 894 |
| Stations analysées (jeu de données) | 9833 |
| Jours d'historique enregistrés | 30 (du 2026-10-13 au 2026-11-14) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11497 stations exploitables ; données du 14/11/2026 12:21 UTC.
- Pages villes : 459 dont 458 indexables (356 ajoutées automatiquement) ; pages provinces : 50.

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
| Titles | 454 / 454 |
| Meta descriptions | 454 / 454 |
| H1 | 454 / 454 |
| Canonicals | 454 / 454 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 3
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 19
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4630 ; moyenne par page : 10.2
- Pages orphelines indexables : 0 ; pages noindex non liées : 4

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 76 | 6 |
| Asnières-sur-Seine | 100 | 177 | 6 |
| Cergy | 100 | 53 | 6 |
| Clichy | 100 | 185 | 6 |
| Drancy | 100 | 143 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| Troyes | 35 | 5 | 4 |
| Ivry-sur-Seine | 43 | 3 | 4 |
| La Rochelle | 44 | 4 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 51 % (min 39 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 33 % (min 22 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 45 % (min 33 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

