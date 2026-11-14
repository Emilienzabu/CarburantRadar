# Procédure de retour arrière (radar V2)

Principe : rien n'écrase rien. Chaque version de snapshot est un objet R2 immuable + une ligne D1 immuable ; seul un pointeur (`snapshot_active`, comparaison-et-échange sur `revision`) désigne la version servie. Le garage est dans une table à part (`garages`).

## A. Une mauvaise donnée est servie (snapshot)
1. `GET /v2/status` : noter `active.version`.
2. `POST /admin/snapshot/rollback` avec `Authorization: Bearer <RADAR_ADMIN_SECRET>` et `{"version":"<version précédente>"}`. Refusé si la version est inconnue, déjà active, élaguée, ou si son objet R2 ne correspond plus à son SHA-256 (le pointeur ne bouge alors pas).
3. Vérifier `GET /v2/status` puis une requête `/v2/france`. L'événement `rollback` est dans `snapshot_events`.
4. Les versions conservées : les 3 dernières (`retain`). Plus ancien = élagué, non restaurable.
5. Cause racine avant tout nouveau rafraîchissement : le cron reprendra et republiera ; suspendre le déclencheur planifié si nécessaire.

## B. Le Worker V2 lui-même pose problème
Aucune application n'en dépend tant que le radar n'est pas branché : retirer la route/le déclencheur du Worker V2 suffit. `carburant-proxy` n'est pas modifié par ce lot.

## C. Garage
Aucune donnée n'est écrite avant l'activation de la route garage. En cas de problème après activation : désactiver la route (le client retombe sur le garage local) ; les lignes `garages` restent, sans effet. Suppression d'un compte : `deleteGarageForUser`.

## D. Retour complet
Supprimer les liaisons/ressources de TEST créées (D1 `DB_RADAR`, bucket R2, Worker V2). Côté dépôt : fermer la PR / supprimer la branche `claude/radar-v76-2026-11-12`. `main` n'a jamais été modifié.

## Test
`v2/test/snapshot.test.mjs` couvre le retour arrière (succès, refus, intégrité, journal). Un exercice sur une base D1/R2 de test réelle reste à faire (voir STAGING_REQUIREMENTS.md).
