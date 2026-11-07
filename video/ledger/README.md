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
