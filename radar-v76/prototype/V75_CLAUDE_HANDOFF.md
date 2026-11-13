# CarburantRadar V75 — transmission pour Claude (préparation uniquement)

## Décision actuelle : PAS PRÊT POUR MISE EN LIGNE
Les tests Node.js sont simulés. Chromium réel, Android, proxy réel, OSRM réel, persistance compte et source immuable ne sont pas validés.

## Travail demandé à Claude (sur branche isolée, sans fusion ni déploiement public)
1. Examiner le dépôt public et le Workspace, en particulier les trois Workers existants, sans modifier les routes de production ni exposer les secrets.
2. Auditer la compatibilité de la source des prix et concevoir une génération de snapshot immuable avec publication atomique, sans affirmer qu'une double lecture offset garantit l'atomicité.
3. Implémenter un endpoint V2 **séparé** et authentifier les opérations de synchronisation garage, en préservant les routes historiques et pays existants.
4. Raccorder l'interface au moteur sur une branche de préproduction isolée. Ne pas fusionner sur main.
5. Effectuer des tests navigateur Android/Chromium, appels réseau proxy/OSRM, limites de débit, GPS, comptes, performances et rollback; fournir les journaux et résultats traçables.
6. Utiliser `release-gate.js` pour documenter les dix validations indispensables. Aucune mention « prêt » tant que les preuves réelles ne sont pas fournies.

## Décision utilisateur requise
Ne demander l'autorisation de déployer qu'après validation de l'environnement de staging. Ne jamais modifier la production sans accord explicite.
