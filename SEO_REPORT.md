# SEO_REPORT — pages générées

Données : jeu officiel « Prix des carburants en France — flux instantané v2 », dernière mise à jour de prix enregistrée : 17/10/2026 10:58 UTC. Rapport déterministe (aucun horodatage de génération).

## Volumétrie

| Indicateur | Valeur |
|---|---|
| Pages France générées par le nouveau système | 426 |
| Pages villes (France) | 182 dont 180 indexables et 2 en noindex |
| — dont communes ajoutées automatiquement (hors villes.json) | 79 |
| Pages départements | 81 |
| Pages régions | 13 |
| Pages ville + carburant | 149 |
| — dont Gazole | 59 |
| — dont SP95 | 2 |
| — dont SP98 | 33 |
| — dont E10 | 47 |
| — dont E85 | 7 |
| — dont GPL | 1 |
| Pages hub (liste des villes France) | 1 |
| Pages Espagne / Italie (pipeline inchangé) | 1269 villes, 159 hubs |
| URLs dans le sitemap | 1707 |
| Stations analysées (jeu de données) | 9814 |
| Jours d'historique enregistrés | 18 (du 2026-09-30 au 2026-10-17) |

## Espagne (pages enrichies)

- Source : API officielle du Ministerio ; 11492 stations exploitables ; données du 15/10/2026 10:08 UTC.
- **API indisponible : dernier jeu de données valide en cache utilisé (2.0 j)** : RuntimeError: Téléchargement impossible (<urlopen error [Errno 104] Connection reset by peer>) ; provinces en échec : ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52']
- Pages villes : 458 dont 457 indexables (355 ajoutées automatiquement) ; pages provinces : 50.

## Italie (pages enrichies)

- Source : CSV du MIMIT ; 21453 stations exploitables ; données du 15/10/2026 08:01 UTC.
- **Source indisponible : dernier jeu de données valide en cache utilisé (2.1 j)** : RuntimeError: Téléchargement impossible de prezzo_alle_8.csv (<urlopen error timed out>)
- Pages villes : 811 dont 811 indexables (708 ajoutées automatiquement) ; pages provinces : 107.

## IndexNow (Bing, Yandex, Naver, Seznam)

- 1707 URLs signalées ; réponses HTTP : api.indexnow.org 200 (200 ou 202 = accepté).

## Unicité des balises (pages générées France)

| Balise | Valeurs distinctes / pages |
|---|---|
| Titles | 426 / 426 |
| Meta descriptions | 426 / 426 |
| H1 | 426 / 426 |
| Canonicals | 426 / 426 |

## Qualité du contenu

- Pages avec moins de 250 mots (zone principale) : 0
- Pages villes avec peu de données (score < 45 ou < 3 stations ou < 2 carburants → noindex) : 2
- Pages villes sans station : 0 (rayon de 12 km)
- Pages villes sans prix : 0
- Pages villes sans ville voisine affichée : 18
- Pages villes sans département identifié : 0

## Maillage interne (pages France générées)

- Liens internes distincts au total : 4305 ; moyenne par page : 10.1
- Pages orphelines indexables : 0 ; pages noindex non liées : 3

## Pages les plus / moins riches (villes)

| Plus riches | Score | Stations | Carburants |
|---|---|---|---|
| Allauch | 100 | 75 | 6 |
| Asnières-sur-Seine | 100 | 177 | 6 |
| Cergy | 100 | 52 | 6 |
| Clichy | 100 | 186 | 6 |
| Drancy | 100 | 144 | 6 |

| Moins riches | Score | Stations | Carburants |
|---|---|---|---|
| Roubaix | 43 | 3 | 4 |
| La Rochelle | 44 | 4 | 4 |
| Troyes | 45 | 5 | 4 |
| Orléans | 45 | 5 | 4 |
| Angoulême | 45 | 5 | 4 |

## Doublons de contenu (zone principale, séquences de 6 mots)

- Pages villes : contenu unique moyen 49 % (min 37 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages ville + carburant : contenu unique moyen 29 % (min 18 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0
- Pages départements / régions : contenu unique moyen 44 % (min 37 %) ; paires quasi identiques (Jaccard ≥ 0.5) : 0

## Validation

- Erreurs : 0 ; avertissements : 3
  - avertissement /espagne/ : 5 balises H1
  - avertissement /france/ : 5 balises H1
  - avertissement /italie/ : 5 balises H1
- Test lien France : `/france/prix-carburant/avignon/` + `../../` → `/france/` (OK)

