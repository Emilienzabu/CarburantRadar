# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 10/11/2026 14:19 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 428 |
| Pages villes (France) | 182 dont 179 indexables et 3 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 151 |
| — dont Gazole | 62 |
| — dont SP95 | 2 |
| — dont SP98 | 29 |
| — dont E10 | 49 |
| — dont E85 | 9 |
| — dont GPL | 0 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 206 villes, 2 hubs |
| URLs dans le sitemap | 487 |
| Stations analysées (jeu de données) | 9829 |
| Jours d'historique enregistrés | 30 (du 2026-10-09 au 2026-11-10) |

## Espagne (pages enrichies)

- **Source indisponible, pages historiques conservées** : RuntimeError: RuntimeError: Téléchargement impossible (<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1011)>) ; provinces en échec : ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52'] ; cache indisponible (https://carburantradar.fr/donnees/espagne-precios.json.gz : HTTP Error 404: Not Found)
- Diagnostic : {'national_error': '<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1011)>', 'provinces_failed': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52']}

## Italie (pages enrichies)

- **Source indisponible, pages historiques conservées** : RuntimeError: RuntimeError: Téléchargement impossible de prezzo_alle_8.csv (<urlopen error timed out>) ; cache indisponible (https://carburantradar.fr/donnees/italie-prezzi.json.gz : HTTP Error 404: Not Found)
- Diagnostic : {}

## IndexNow (Bing, Yandex, Naver, Seznam)

- 487 URLs signalées ; réponses HTTP : api.indexnow.org 200 (200 ou 202 = accepté).

## Correctifs appliqués aux applications

- france : véhicules et classement par coût total : appliqué
- espagne : véhicules et classement par coût total : appliqué
- italie : véhicules et classement par coût total : appliqué

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 428 / 428 |
| Meta descriptions | 428 / 428 |
| H1 | 428 / 428 |
| Canonicals | 428 / 428 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 3
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 19
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4311 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 3

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
| Boulogne-Billancourt | 39 | 4 | 3 |
| Troyes | 40 | 5 | 3 |
| La Rochelle | 44 | 4 | 4 |
| Angoulême | 45 | 5 | 4 |
| Ajaccio | 45 | 15 | 2 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 50 % (min 39 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 35 % (min 24 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 33 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

