# Ce qu'il faut pour lancer un environnement de test RÉEL

Rien de ceci n'a été créé ni déployé. Tout se fait sur des ressources de TEST, jamais sur `DB_STATS`, `DB_ITALIE`, `USERS`, `SUBS`.

## A. Ressources Cloudflare à créer (par Émilien)
1. D1 `carburant-radar-test` : appliquer `v2/migrations/0001_snapshot_v2.sql` puis `0002_garage.sql`.
2. Bucket R2 `carburant-snapshots-test`.
3. Worker `carburant-radar-v2-test` avec `v2/snapshot-worker.mjs`, liaisons `DB_RADAR`, `SNAPSHOTS`, secret `RADAR_ADMIN_SECRET` (valeur jamais collée dans le dépôt ni le chat), variable `ALLOWED_ORIGINS` (origine de test).
4. Plan : confirmer plan gratuit/payant (limite CPU 10 ms et 50 sous-requêtes à vérifier).
5. Déclencheur planifié : à activer seulement après le premier rafraîchissement manuel réussi.

## B. Fournitures
* Code actuel de `carburant-proxy` + `wrangler.toml` (sans secrets) — voir PROXY_WORKER_CHANGES.md.
* Accord pour un `git clone` de lecture / exécution des étapes ci-dessous depuis un poste ou un bac à sable autorisant `data.economie.gouv.fr`.

## C. Séquence de validation (chaque étape = une preuve pour `release-gate.js`, `environment:"real"`)
| Preuve du gate | Étape |
|---|---|
| immutableSource / completeStationCoverage | Rafraîchissement manuel ; comparer export/total/stations rejetées ; relancer 3 fois ; **d'abord** valider le format réel de `exports/json` (HYPOTHÈSE) |
| snapshotPublication | Publier, relire, épingler, rafraîchir pendant une pagination |
| rollback | Exécuter docs/ROLLBACK.md §A sur la base de test |
| performance | Mesurer CPU/latence du rafraîchissement et d'une requête à froid |
| proxyCompatibility / garageAccountSync | Brancher le garage (option A) sur un compte de TEST dédié |
| routingReal | OSRM auto-hébergé ou service autorisé (pas le serveur de démonstration) |
| browserReal / androidReal | Chromium et appareil Android sur `radar-interface.html` en mode réel |

Le dossier `prototype/` fournit `browser-check.js`, `preview-server.js` et `radar-interface.html` pour les deux dernières lignes.
