# video/ledger — journal anti-doublon (CANDIDAT, non appliqué)

`0001_video_ledger.sql` est un schéma **candidat** pour une base Cloudflare D1. **Rien n'a été exécuté sur une base distante.**
Il est testé sous SQLite par `video/tests/test_ledger_sql.py` (réservation unique, une seule prise de créneau en concurrence,
verrou de révision, observations immuables, complétion seulement avec les deux plateformes).

Il ne sert à rien tant que le Worker `video-automation` ne l'utilise pas : le générateur Python ne peut pas garantir seul
l'absence de doublon (l'exécuteur GitHub n'a aucun stockage durable). Le branchement se fait côté Worker, dans cet ordre :

1. calculer `slot_key` (`AAAA-MM-JJ:matin|soir`, heure de Paris) et le SHA-256 du MP4 reçu ;
2. `INSERT ... ON CONFLICT DO NOTHING` (réservation) ; si le créneau existe déjà avec un autre état que « reserved », **refuser** ;
3. prise du créneau par `UPDATE ... WHERE status='reserved' AND revision=?` : un seul appelant gagne ;
4. initialiser une ligne par plateforme, publier, enregistrer `reported_success` + `remote_id` par plateforme ;
5. toute issue incertaine (délai, réponse ambiguë) -> `needs_reconciliation`, **jamais de réessai automatique** ;
6. `reported_complete` seulement quand les deux plateformes ont confirmé.

Limites : `reported_*` est ce que le Worker déclare, pas une preuve vérifiée à distance. Les API YouTube/Instagram ne permettent pas
de comparer les octets d'une vidéo publiée ; une lecture de métadonnées (identifiant, compte, marqueur de créneau dans la description/légende) est possible mais n'est pas implémentée ici (modules `remote_metadata_verifier` du paquet V100, à valider
sur les API réelles).

## Protocole `slot_id` + `sha256` (PROPOSITION : modèle de référence testé, Worker réel non lu)

Modèle exécutable : `video/tests/ledger_worker_reference.py` ; tests : `video/tests/test_ledger_protocole.py` (SQLite, doubles de plateformes,
aucun réseau). Ils fixent le comportement attendu ; ils ne prouvent rien sur Cloudflare D1, sur les API YouTube/Instagram ni sur le Worker
`video-automation` (code non lu).

**Requête** (`POST /api/upload`, champs actuels conservés) : ajout de `slot_id` (`AAAA-MM-JJ:matin|soir`) et `sha256` (hex minuscule du MP4).
Le Worker valide le calendrier (le `GLOB` du schéma ne le fait pas) et **recalcule** le SHA-256 des octets reçus.

**Réponses** : `200` complet (ou rejeu en lecture seule, `rejoue: true`, aucun appel de plateforme) ; `400` entrée invalide ;
`409` `creneau_en_cours`, `reconciliation_requise` ou `creneau_deja_utilise_par_une_autre_video` ; `502` `reconciliation_requise` après une tentative
non confirmée. Corps : `slot_id`, `sha256`, `etat`, `rejoue`, `youtube` et `instagram` (`success`, `remote_id`, `enregistre`). Les clés
`youtube.success` / `instagram.success` du contrat actuel sont conservées.

**Ordre** : valider -> réserver -> prendre le créneau (un seul gagnant) -> pour chaque plateforme : ligne d'observation, appel, résultat enregistré
-> `reported_complete` seulement si les deux succès ont un identifiant distant. Après tout doute sur une plateforme, la suivante n'est pas appelée.

**Après crash** : jamais de republication. `reserved` (aucun appel fait) peut être repris ; `upload_started` ancien est balayé vers
`reported_complete` (deux succès enregistrés) ou `needs_reconciliation`. Sortir de `needs_reconciliation` exige une extension du schéma (0002,
preuves ajoutées sans réécrire les observations, car `0001` les rend immuables) : non écrite, à valider.

Le générateur Python (`video/generate_video.py`) envoie ces champs et lit ces réponses ; un ancien Worker (réponse sans champ `etat`) reste
supporté. À ne fusionner qu'avec la préparation du Worker (voir `workers/video-automation/README.md`, ordre de déploiement).

## Extension `0002` et Worker candidat

`0002_video_ledger_evidence.sql` ajoute (sans toucher à `0001`) les traces de tentative, les preuves de réconciliation et les décisions de
clôture, en ajout seul (testé : `video/tests/test_ledger_0002.py`). Le Worker candidat qui les utilise est dans
`workers/video-automation/` (non déployé). Toujours **non exécuté sur D1**.
