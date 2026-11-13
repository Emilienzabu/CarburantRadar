# radar-v76 — intégration isolée du prototype « radar » (étape 76)

**Statut : prototype isolé, NON branché sur l'application, NON déployé.** Rien ici ne modifie `france/`, `espagne/`, `italie/`, `service-worker.js`, les workflows ni les Workers Cloudflare.

| Dossier | Contenu |
|---|---|
| `prototype/` | Copie **fidèle** de l'archive `carburantradar_etape76.zip` (78 fichiers, SHA-256 dans `MANIFEST.sha256.json`). Les 3 bundles `*.browser.js` ne sont pas versionnés : `tools/build-browser.js` les régénère à l'identique. |
| `v2/` | Code **nouveau** : `snapshot-worker.mjs` (snapshot France immuable), `garage-api.mjs` (garage par compte), `migrations/` (D1), `test/`. |
| `docs/` | `INTEGRATION_V2.md` (constats + conception), `PROXY_WORKER_CHANGES.md`, `ROLLBACK.md`, `STAGING_REQUIREMENTS.md`. |

Lancer : `./run-tests.sh` (Node ≥ 22.5, sans réseau).

⚠️ GitHub Pages sert tout le dépôt : après fusion dans `main`, ce dossier (dont `prototype/radar-interface.html`) serait **public**. Voir `docs/INTEGRATION_V2.md` §7 avant toute fusion.
