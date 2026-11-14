# Intégration partielle de l'archive ChatGPT du 14 novembre 2026

Source : `CarburantRadar_pour_Claude_mobile_GitHub.zip` (SHA-256 `c97b46fc6b82303277ac9f451e360f82d6c74875a0877c7c9ecece01ba03b0c9`), dossier `carburantradar_osrm_circuit_breaker/`.
Branche : `claude/integration-chatgpt-osrm-2026-11-14`, **empilée sur la branche de la PR #39** (`claude/radar-v76-2026-11-12`). Cette PR contient donc aussi les commits de la PR #39 tant que celle-ci n'est pas fusionnée.

## Ce qui est intégré ici (lot 1)

| Fichier | Rôle |
|---|---|
| `radar-v76/prototype/snapshot-v2-client.js` | client navigateur du contrat `/v2/france` (pagination, checksum, curseurs) |
| `radar-v76/prototype/radar-real-provider.js` | accepte `snapshotV2Url` (désactivé par défaut, proxy historique inchangé) |
| `radar-v76/prototype/radar-real-provider.v2.test.js` | 3 tests du fournisseur |
| `radar-v76/tools/build-browser.js` | embarque `snapshot-v2-client` et `station-pages` dans le bundle navigateur |

SHA-256 de référence (archive) : `build-browser.js` 7e75c50e…f28c7 ; `radar-real-provider.js` 0a0c3ea1…4fd ; `snapshot-v2-client.js` f48f4213…9707 ; `radar-real-provider.v2.test.js` 8deb7338…1c42.
Ces quatre fichiers ont été recopiés par le connecteur GitHub (écriture par contenu texte, sans vérification de hachage côté dépôt) : à contrôler avec `sha256sum` avant fusion.

## Ce qui N'EST PAS intégré (BLOQUÉ ou reporté)

1. **`france/index.html`** (archive : 187 789 o ; `main` : 177 361 o) : coût réel, Top 10, OSRM (timeout, retry, 429, cache, cooldown), correctif du changement de carburant, coordonnées invalides, chargement V2 opt-in. Le connecteur n'écrit qu'un fichier complet par contenu texte ; recopier ~188 Ko sans pouvoir vérifier le résultat par hachage est un risque de corruption de la page de production. De plus, aucune comparaison exacte avec la version actuelle de `main` n'a été possible (le connecteur ne renvoie pas le contenu au bac à sable) : risque d'écraser des changements plus récents. **À faire avec un accès fichier réel** (PC, Claude Code, ou envoi du fichier par l'interface web de GitHub sur une branche), avec fusion à trois voies.
2. **`radar-v76/prototype/radar-interface.html`** (champ d'URL V2) et manifestes `MANIFEST.sha256.json` / `MANIFEST.upstream.sha256.json` : non poussés (le manifeste doit être régénéré après le lot complet).
3. **`radar-v76/v2/`** : `snapshot-worker.mjs` modifié (importe les modules `pr39-*.mjs`), 8 modules `pr39-*.mjs`, `snapshot-v2-client.cjs`, migrations `0100`–`0102`, tests `cost-public-ui`, `snapshot-v2-client`, `snapshot` et `helpers` mis à jour. À ne pas déployer sans staging D1/R2. `step103.mjs`, `step104.mjs`, `snapshot-worker.original.mjs` sont des artefacts d'audit : à ne pas intégrer.
4. **`.github/workflows/*`** : le connecteur n'y a pas accès (protection volontaire). Les copies de l'archive ne sont pas comparées.
5. **`video/`** de l'archive : copie ancienne ; `main` contient des travaux plus récents (PR #34, #35). Ne pas écraser.
6. Pages générées (`france/*/`, `espagne/`, `italie/`, sitemaps) et `CarburantRadar.apk` : données régénérées par le workflow, hors périmètre.
7. `france/v2-ui-contract.test.cjs` (archive) est **périmé** : son expression régulière ne trouve plus `chargerStationsRadar` (variables ajoutées avant `function load(`). Il n'est pas appelé par `run-tests.sh`. À corriger au moment de l'intégration de `france/index.html`.

## Preuves (copie de l'archive, bac à sable, Node 22.23)

- `sh radar-v76/run-tests.sh` : 544 tests prototype + 86 tests V2 = **630/630**, 0 échec ; audit d'intégration : `releaseReady=false` (attendu).
- Scripts JavaScript en ligne de `france/index.html` de l'archive : syntaxe valide (le bloc JSON-LD n'est pas du JS).
- `france/v2-ui-contract.test.cjs` : **ÉCHEC** (test périmé, voir point 7).
- **Non exécuté** : tests sur cette branche (aucun workflow ne les lance, aucune exécution possible depuis le connecteur), navigateur/Android, OSRM réel, Cloudflare D1/R2, Espagne/Italie.

## Retour arrière

Supprimer la branche ou ne pas fusionner : ajout de fichiers isolés dans `radar-v76/`, aucun fichier de production touché.
