# Worker `video-automation` : journal anti-doublon (CANDIDAT, NON DÉPLOYÉ)

**Rien de ce dossier n'a été déployé sur Cloudflare, aucune vidéo n'a été publiée, aucune base D1 n'a été créée ou migrée.**

## Ce que c'est, et ce que ce n'est pas

- `baseline/index.pdf-2026-11-08.js` : le code du Worker **reconstruit depuis `WORKER.pdf`** (fourni par le propriétaire). Ce n'est pas une
  lecture du Worker déployé : **compare-le au code réellement en ligne avant toute décision.**
- `src/index.js` : la même base + le protocole `slot_id` + `sha256` avec journal D1. Le diff exact :
  `diff -u baseline/index.pdf-2026-11-08.js src/index.js`. Fichier unique, sans import : il se colle tel quel dans l'éditeur Cloudflare.
- `test/` : tests Node (`npm test`, Node ≥ 22.5, aucune dépendance, aucun réseau). D1 est **simulé** par SQLite (`node:sqlite`).

## Les six constats de ChatGPT, vérifiés par exécution sur le code du PDF (`test/constats_baseline.test.mjs`)

| Constat | Résultat sur le code du PDF | Correction dans `src/index.js` |
|---|---|---|
| Pas de réservation durable et atomique | **Confirmé** : même créneau publié 2 fois, et plusieurs fois avec 20 envois simultanés ; aucun D1 dans le code | réservation + prise du créneau en D1 avant tout appel |
| Clé R2 fixe `video-du-jour.mp4` | **Confirmé** : un 2e envoi écrase le fichier qu'Instagram vient chercher (YouTube et Instagram reçoivent 2 vidéos différentes) | clé unique `carburant/<créneau>/<sha256>.mp4` ; clé unique par requête sur le chemin historique |
| Fichier choisi par listing (`objects[0]`) | **Confirmé** : un fichier résiduel est publié à la place de la vidéo envoyée | la clé est connue et passée explicitement ; les copies du journal sont exclues du listing |
| Suppression même après échec | **Confirmé** | copie supprimée seulement quand le créneau est complet |
| HTTP 200 si une seule plateforme réussit | **Confirmé** | 200 seulement si les deux sont confirmées ; sinon 502 |
| Pas de réconciliation durable | **Confirmé** : rien n'est enregistré, la relance republie | états durables + `0002` + routes `/ledger/*` |
| *(en plus)* `/media/<clé>` public | **Constaté** : sert n'importe quelle clé du bucket sans authentification | **non corrigé** (voir limites) |

Ces constats valent pour le code du PDF. La version déployée peut différer.

## Contrat HTTP (profil `carburant`, `POST /api/upload`)

Champs actuels conservés (`profile`, `video`, `title`, `description`, `caption`) + **`slot_id`** (`AAAA-MM-JJ:matin|soir`, date réelle) +
**`sha256`** (hex minuscule du fichier). Le Worker **recalcule** le SHA-256 et refuse toute différence.

| HTTP | `etat` | Sens |
|---|---|---|
| 200 | `complet` | les deux plateformes confirmées (`rejoue: true` si le créneau était déjà complet : lecture seule, aucun appel) |
| 400 / 413 / 500 / 503 | `refuse` | arrêté **avant** toute publication (entrée invalide, journal absent, R2 indisponible) |
| 409 | `bloque` | `creneau_en_cours`, `reconciliation_requise`, `creneau_clos_sans_publication`, `creneau_deja_utilise_par_une_autre_video` : rien de nouveau envoyé |
| 502 | `reconciliation_requise` | tentative faite, au moins une plateforme non confirmée : créneau bloqué |
| 500 | `incertain` | exception après la prise du créneau |

Corps : `slot_id`, `sha256`, `etat`, `rejoue`, `youtube`, `instagram`. Les clés historiques sont conservées : `youtube.success/videoId/url`,
`instagram.success/mediaId`, plus `remote_id`, `enregistre`, `tentee`. Le générateur Python lit `etat` (voir `video/generate_video.py`) et reste
compatible avec l'ancien format.

## Ordre transactionnel

1. valider `slot_id` / `sha256` (aucune écriture si invalide) ; 2. `INSERT … ON CONFLICT DO NOTHING` (réservation) ; 3. selon l'état : rejeu,
409, ou suite ; 4. copie R2 (clé unique) ; 5. **prise** `reserved → upload_started` (un seul gagnant, verrou de révision) ;
6. pour YouTube puis Instagram : ligne d'observation **avant** l'appel, résultat **après** ; 7. si une plateforme n'est pas confirmée
(identifiant distant), la suivante **n'est pas tentée** ; 8. `reported_complete` seulement avec les deux identifiants, sinon
`needs_reconciliation`. Le conteneur Instagram est noté (`video_attempt_refs`) dès sa création.

**Après crash** : jamais de republication. `scheduled` balaie les créneaux `upload_started` de plus de 30 min : deux succès enregistrés →
complet (copie supprimée) ; sinon → `needs_reconciliation`. Un créneau `reserved` (rien d'envoyé) est repris par la requête suivante.

## Réconciliation (propriétaire, `?key=UPLOAD_PASSWORD`, jamais automatique)

- `GET /ledger/status?slot_id=…` : état, observations, traces, preuves, décision, clé de la copie R2.
- `POST /ledger/evidence` `{slot_id, platform, outcome: published|absent, remote_id?, proof_kind, note?, confirm: true}`. Une preuve par
  plateforme, **jamais modifiable** (réfléchis avant de confirmer). `worker_pre_publish` n'est accepté que si le Worker a lui-même noté un
  échec avant envoi.
- `POST /ledger/resolve` `{slot_id, resolution: completed_by_evidence|closed_nothing_published, confirm: true}` : refusé par le schéma si
  les preuves ne le justifient pas. **Rien ne relance une publication** ; un créneau clos reste clos (une republication = décision à part).

## Variables et bindings (aucun secret dans ce dossier)

Existants, inchangés : `CONFIG_KV`, `VIDEO_BUCKET`, `API_KEY`, `UPLOAD_PASSWORD`, `YOUTUBE_*`, `INSTAGRAM_ACCOUNT_ID*`.
**Nouveau** : binding D1 **`DB_VIDEO`** (sans lui, `/api/upload` carburant répond 503 et ne publie rien). Optionnels : `ALLOW_LEGACY_CLIENT=1`
(transition : accepte l'ancien générateur sans `slot_id`/`sha256`, créneau déduit à l'heure de Paris) ; `LEDGER_MODE=off` (retour arrière :
chemin historique, **sans protection anti-doublon**).

## Ordre de déploiement suggéré (rien n'a été fait ; décision du propriétaire)

1. Comparer `baseline/` au Worker en ligne, sauvegarder celui-ci. 2. Créer une base D1 **de test**, appliquer `video/ledger/0001` puis `0002`
(ils n'ont été exécutés que sous SQLite). 3. Vérifier sur cette base les triggers (`changes()` dans un trigger, `meta.changes`, concurrence réelle).
4. Binder `DB_VIDEO`, poser `ALLOW_LEGACY_CLIENT=1`, déployer ce Worker. 5. Fusionner le générateur, puis retirer `ALLOW_LEGACY_CLIENT`.
**Attention : ce Worker n'a aucun mode « sans publication »** : tout essai réel publie sur les comptes réels.

## Limites restantes

- D1 réel non testé ; la concurrence testée est celle d'un seul processus (entrelacement entre requêtes), pas celle de plusieurs isolats.
- La page `/upload` (humain), `/run` et le cron du profil `default` n'utilisent **pas** le journal (pas de notion de créneau) ; seul le choix de fichier est corrigé.
- Le profil `default` via `/api/upload` n'a pas de journal (la clé de créneau ne contient pas le profil).
- `/media/<clé>` reste public et sert n'importe quelle clé (Instagram doit pouvoir la lire) ; les clés du journal contiennent le SHA-256 (non devinables en pratique, pas secrètes).
- Aucun délai d'attente sur les appels YouTube/Instagram ; durée maximale d'une requête non maîtrisée (le balayage à 30 min suppose qu'elle est plus courte).
- `reported_*` = ce que le Worker déclare ; la vérification distante (identifiant → API YouTube/Instagram) reste manuelle, **sans marqueur dans les descriptions** (décision du propriétaire).
- Vidéo en mémoire (limite 64 Mo) ; une preuve ou une décision ne peut pas être corrigée.
