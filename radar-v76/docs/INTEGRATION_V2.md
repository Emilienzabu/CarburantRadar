# Intégration V2 — constats sur le prototype V76 et conception retenue

Étiquettes : **VÉRIFIÉ** (reproduit par un test ou une mesure dans ce dépôt) · **DOCUMENTATION** (limite publiée par Cloudflare/ODS, non vérifiée sur le compte) · **HYPOTHÈSE** (non vérifiable depuis le bac à sable : `data.economie.gouv.fr` n'est pas dans les domaines autorisés).

## 1. Constats sur le prototype (au-delà des 541 tests, qui utilisent des fournisseurs simulés)

| # | Constat | Statut | Preuve |
|---|---|---|---|
| C1 | **Deux contrats V2 incompatibles.** `proxy-contract.js` exige `complete=false` + curseur chaîne sur les pages intermédiaires ; `snapshot-france.js`/`radar-snapshot-bridge.js` envoient `complete=true` sur chaque page + curseur numérique. `normalizeV2Page` rejette les pages du second. | VÉRIFIÉ | `integration.test.mjs` C1 |
| C2 | `snapshot-france.js` : **une seule ligne invalide (prix ≤ 0, coordonnées absentes) fait échouer tout le jeu** ; l'ancien snapshot reste servi indéfiniment. | VÉRIFIÉ | C2 |
| C3 | `snapshot-persistence.js` reconstruit, re-hache et re-trie les ~9 800 stations à **chaque requête** : 332 ms mesurés (Node) contre 1,2 ms avec cache d'isolat. | VÉRIFIÉ | C3 |
| C4 | `worker-france-v2.js` enchaîne jusqu'à 95 sous-requêtes (>50, limite Workers gratuite) et son identifiant `single-response-N` n'est **pas** une version de snapshot. | VÉRIFIÉ (nombre d'appels) / DOCUMENTATION (limite 50) | C4 |
| C5 | `source-snapshot-loader.js` pagine par `offset` avec `maxRecords=15000` : l'API Explore v2.1 plafonne `offset+limit` à 10 000 (jeu actuel ≈ 9 826, marge ~2 %). | DOCUMENTATION / HYPOTHÈSE | — |
| C6 | Tous les modules sont CommonJS et `snapshot-*` utilisent `node:crypto` synchrone : inutilisables tels quels dans un Worker (ESM, WebCrypto asynchrone). | VÉRIFIÉ (lecture) | — |
| C7 | `snapshot-persistence.js` : la « version épinglée » exige que le **client** fournisse un manifeste ; aucune rétention de versions n'existe. | VÉRIFIÉ (lecture) | — |
| C8 | Le CAS est une abstraction : **KV n'offre pas de comparaison-et-échange**. Il faut D1 (ou un Durable Object). | DOCUMENTATION | — |
| C9 | Points positifs : pas d'`innerHTML` (rendu par `textContent`), aucun `eval`, aucun accès `localStorage`, `node --check` OK sur 41 modules, bundles navigateur reproductibles à l'octet. | VÉRIFIÉ | `manifest.test.mjs` |
| C10 | Le prototype utilise le serveur de démonstration public OSRM (`router.project-osrm.org`) ; sa politique d'usage n'est pas prévue pour un trafic de production. | DOCUMENTATION (à relire) | — |

## 2. Conception retenue (`v2/`)

Nouveau Worker **séparé** (`carburant-radar-v2`), ESM mono-fichier, WebCrypto. `carburant-proxy` n'est pas touché.

* **Source** : `records?limit=1` (total) → `exports/json` (une requête) → `records?limit=1` (total). Publication seulement si les **trois mesures sont égales** (procédure E0/E1 de `audits/AUDIT_E0_E1_2026-11-05.md`). Aucune pagination par offset.
* **Normalisation tolérante** : lignes invalides écartées, comptées par motif dans la version (`rejected`), refus si > 1 % ; identifiant dupliqué = échec ; prix hors ]0 ; 20] = null ; date `*_maj` conservée.
* **Garde-fous de publication** : minimum 5 000 stations, chute > 10 % refusée, horloge qui recule refusée, relecture R2 + SHA-256 avant publication, bail D1 (un seul rafraîchissement à la fois).
* **Immuabilité** : objet R2 `france/snapshots/<version>.json` créé « si absent » ; ligne D1 immuable (triggers) ; version = horodatage + 8 premiers caractères du hachage du contenu.
* **Pointeur** : `snapshot_active`, CAS sur `revision` ; cible limitée aux versions jamais élaguées ; rétention de 3 versions.
* **Lecture** : `GET /v2/france?lat&lon&dist(≤50)&fuel&limit(≤100)&cursor&snapshot` — contrat **snapshot** (celui du pont du prototype, testé de bout en bout). Tri par distance puis identifiant ; `snapshot=<version>` épingle les pages suivantes ; version élaguée = 404 (le client recommence). Réponse : `stale`/`ageMs` informatifs.
* **Exploitation** : `GET /v2/status` ; `POST /admin/snapshot/{refresh,rollback}` (jeton `RADAR_ADMIN_SECRET`, comparaison à temps constant) ; journal `snapshot_events`.
* **CORS** : liste blanche (`ALLOWED_ORIGINS`), jamais `*`.

**Décision à prendre (C1)** : retenir le contrat snapshot ; `proxy-contract.js` ne doit pas servir pour la V2.

## 3. Mesures (Node, pas Workers) — `snapshot.test.mjs`, test « taille réelle »
9 826 stations : rafraîchissement ≈ 170 ms, 1re requête à froid ≈ 25 ms, requête en cache ≈ 5 ms, objet ≈ 3,3 Mo.
**Risque** : la limite CPU Workers gratuite est de 10 ms par invocation (DOCUMENTATION, à confirmer sur le compte). Rafraîchissement et requête à froid la dépassent probablement : plan payant ou conception « lignes D1 + requête SQL par zone » (repli non implémenté). À trancher par une mesure sur Cloudflare réel.

## 4. Garage (`garage-api.mjs`)
`GET/PUT /v2/garage`, une ligne D1 par compte, CAS sur `revision` (409 + état serveur), règle `prepareSave` conservée (plusieurs éditions hors ligne = +1 révision), 30 véhicules, 32 Ko, validation **identique** à `garage.js` (test différentiel sur 3 000 entrées mutées), `userId` issu uniquement de `authenticate()`. L'authentification n'est pas implémentée (voir PROXY_WORKER_CHANGES.md) : sans `authenticate`, les routes répondent 501. `createHttpGarageAdapter` s'branche sur `synchronizeGarage()` du prototype (testé).

## 5. Ce que les tests ne prouvent pas
D1/R2/Workers réels (SQLite et une Map les émulent) ; concurrence entre isolats ; format réel de l'export ODS (`exports/json`, forme de `geom`, champs `*_maj` : HYPOTHÈSE à vérifier en premier) ; Chromium/Android ; OSRM réel ; performances sur Cloudflare.

## 6. Preuves du `release-gate` (toutes `blocked` à ce jour)
Voir STAGING_REQUIREMENTS.md. `integration-audit.js` reste `releaseReady:false`, ce qui est correct.

## 7. Publication GitHub Pages
Le site est servi depuis la racine du dépôt : fusionner `radar-v76/` rendrait publics les fichiers du prototype. **Ne pas fusionner sans décision** : déplacer vers un dépôt/dossier non publié, ou accepter l'exposition (aucun secret dans ce dossier ; l'interface ne fait d'appels réels que sur clic).
