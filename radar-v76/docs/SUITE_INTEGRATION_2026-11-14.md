# Suite de l'intégration (2026-11-14) : constats, capacités du connecteur, plan

Complete [INTEGRATION_ARCHIVE_2026-11-14.md](INTEGRATION_ARCHIVE_2026-11-14.md). Statuts : VÉRIFIÉ = test ou lecture réellement exécuté ; À CONFIRMER = non prouvé.

## 1. Vérification des 4 fichiers de la PR #40 — VÉRIFIÉ
Relus depuis la branche, recopiés dans le bac à sable, SHA-256 identiques à l'archive : `build-browser.js`, `radar-real-provider.js`, `radar-real-provider.v2.test.js`, `snapshot-v2-client.js`.

## 2. Test périmé `v2-ui-contract.test.cjs` — corrigé, en attente
Cause : l'expression régulière attendait `function load(` juste après `chargerStationsRadar`. Correction : fin de fonction = première accolade en colonne 0. Aucune assertion supprimée ni affaiblie ; l'absence de la fonction fait maintenant échouer le test avec un message explicite.
Preuves (bac à sable, page `france/index.html` de l'archive) : 5 tests sur 5 réussis ; en retirant volontairement le contrôle de doublon puis le contrôle HTTPS, le test échoue (2 mutations sur 2 détectées).
Le fichier est déposé dans `radar-v76/pending-france/` : il lit `index.html` de son propre dossier et doit être déplacé dans `france/` **en même temps** que la page intégrée (la page actuelle de `main` n'a pas cette fonction : il y échouerait).

## 3. Comparaison PR #39 / PR #40 / `main` (par tailles de fichiers et contenus lus)
- Branche #39 et `main` : `france/index.html` (177 361 o), `admin/`, `generator/*` (sauf `generated_pages.json`), `video/*` : mêmes tailles. `main` est plus récent uniquement sur des données régénérées (`SEO_REPORT.md`, `generated_pages.json`). À CONFIRMER octet par octet.
- PR #40 = #39 + 6 fichiers (4 code, 2 docs) + ce document + le test en attente. Aucun fichier de `main` hors `radar-v76/` n'est modifié.
- `espagne/index.html` et `italie/index.html` : l'archive n'y contient aucune des fonctions Radar/OSRM/V2 (0 occurrence) ; rien à intégrer pour ces deux pays.

## 4. RISQUE MAJEUR pour `france/index.html` — VÉRIFIÉ (local)
`generator/app_patches.py` injecte au déploiement (tout ou rien, texte exact) la fonction « véhicules + classement par coût total » dans `france/index.html`. Le `SEO_REPORT.md` de `main` indique « appliqué » pour la France. Appliqué à la page de l'archive (qui réécrit ces zones : classement, libellé du rang, bloc carte, sélection des 10 stations) : statut **« NON appliqué »**, 5 points d'accroche introuvables. Conséquence : copier tel quel la page de l'archive **supprimerait en production la fonction multi-véhicules et le véhicule par défaut** (garage) sur la France, et laisserait deux logiques de classement concurrentes (OSRM de l'archive, `app_vehicles.js`).
L'intégration n'est donc pas un simple remplacement : elle exige une fusion à trois voies basée sur la page **actuelle de `main`**, où la configuration véhicule de l'archive (`radarVehicleConfig`, réservoir/consommation uniques) lit le véhicule par défaut du garage.

## 5. Worker V2 — préparation (rien déployé)
- `snapshot-worker.mjs` de l'archive importe 4 modules `pr39-*.mjs` ; `pr39-maintenance.mjs` en importe 5. Le déploiement historique par copier-coller ne gère pas les imports.
- Bundle monofichier testé (esbuild, bac à sable) : 28 929 o, exporte `default { fetch, scheduled }` et 24 exports nommés ; SHA-256 `1a5ad10adee88bb1b8ff50389c92b4e739d69558a7598a70af2db140a089c96c`. Commande : `npx esbuild radar-v76/v2/snapshot-worker.mjs --bundle --format=esm --platform=neutral --outfile=snapshot-worker.bundle.mjs`. Non committé (dérivable).
- Ordre des migrations D1 de test : `0001`, `0002`, `0100`, `0101`, `0102`. `pr39-maintenance.mjs` cite par erreur une « migration 0003 » inexistante (commentaire).
- Les 15 fichiers V2 à ajouter (modules `pr39-*`, `snapshot-worker.mjs` modifié, `snapshot-v2-client.cjs`, migrations, 3 tests + `helpers.mjs`) ne sont pas encore poussés : voir la section 6.
- Suite de tests V2 de l'archive : 86/86 (bac à sable). Staging D1/R2 : non fait.

## 6. Capacités réelles du connecteur `carburant-mcp` — VÉRIFIÉ par usage
Peut : lire un fichier ou un dossier (par morceaux avec `start`/`max_chars`, sur n'importe quelle branche) ; créer une branche depuis une autre ; pousser un commit de fichiers **texte complets** (création, remplacement, suppression) sur une branche autre que `main` ; ouvrir une PR vers `main` ; lire l'état et les journaux des exécutions Actions ; lancer uniquement le workflow « Générer les pages villes » (non utilisé, non autorisé).
Peut donc : déposer un fichier temporaire sur une branche et ouvrir une PR contenant des fichiers temporaires.
Ne peut pas : appliquer un correctif partiel à un fichier (pas de diff, pas d'ajout en fin de fichier : tout fichier est réécrit en entier par mon texte, sans contrôle de hachage côté dépôt) ; lire des fichiers binaires ou un ZIP ; lister les branches, PR, commits ou diff ; commenter, fusionner ou fermer une PR ; toucher `.github/` ; accéder à Cloudflare (D1, R2, Workers, secrets) ; exécuter des tests sur GitHub sans workflow existant ; publier ou déployer.
Conséquence : pas d'intégration « par petits blocs » d'un gros fichier ; seul un fichier **complet** peut être poussé. Pour une page de 188 Ko, le seul chemin sûr est une fusion calculée et hachée dans le bac à sable à partir de la **page actuelle de `main`** (envoyée comme pièce jointe), puis déposée sur la branche en conservant les octets.

## 7. Aucune fusion, aucun déploiement, aucun workflow lancé.
