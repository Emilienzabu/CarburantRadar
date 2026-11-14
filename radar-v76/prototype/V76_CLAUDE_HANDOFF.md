# CarburantRadar — relais Claude V76

## Décision : transmettre pour intégration en staging isolé, PAS pour production

Le prototype a des tests locaux mais aucune validation Chromium/Android, proxy/OSRM réels ni sauvegarde de garage authentifiée.

1. Lire `V75_CLAUDE_HANDOFF.md` et `INTEGRATION.md` ; vérifier les trois Workers existants dans le Workspace.
2. Lancer `node --test *.test.js` et `node integration-audit.js` avant modification. Comparer les SHA-256 du rapport à ceux de l'archive reçue.
3. Intégrer sur une **nouvelle branche isolée**, sans fusion, déploiement public ni modification de routes de production.
4. Mettre en place un endpoint snapshot V2 réellement immuable/versionné et compatible avec les anciennes routes, sans considérer deux lectures identiques comme une preuve d'atomicité.
5. Raccorder la synchronisation garage à une persistance serveur authentifiée, avec CAS et gestion explicite des conflits.
6. Tester sur un environnement de staging : navigateur Chromium, Android, GPS, changements de véhicule/jauge, exhaustivité des stations, OSRM aller/retour, limites de débit, performance, annulation et rollback.
7. Produire les journaux, captures et références de preuve pour `release-gate.js`. Ne demander l'autorisation de production qu'après succès des contrôles réels.

**Aucun secret ni identifiant utilisateur dans les journaux ou les archives.**
