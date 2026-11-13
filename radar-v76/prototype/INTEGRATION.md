# CarburantRadar V51 — essai réel en lecture seule

## Nouveaux fichiers
- `radar-real-provider.js` : adaptateur du proxy historique et routage OSRM (injection de `fetch`).
- `radar-real-provider.browser.js` : version navigateur sans dépendance externe.
- `radar-real-provider.test.js` : 8 tests supplémentaires.
- `radar-interface.html` : bouton explicite « Tester les données réelles (lecture seule) ».

## Essai
Servir le dossier sur un serveur HTTPS (ou localhost) et ouvrir `radar-interface.html`. Cliquer sur le bouton d'essai réel et autoriser la géolocalisation. Le test utilise un véhicule temporaire **Gazole, 6 L/100 km, 50 L, 80 %**, modifiable par la jauge. Il n'enregistre pas de compte et ne modifie pas la production.

## Limites à ne pas masquer
- Le proxy historique limite à 100 stations ; **le Top 10 reste provisoire** même si les itinéraires sont tous calculés.
- Le service public OSRM peut limiter/refuser les requêtes, et n'inclut pas le trafic en temps réel.
- Le proxy peut ne pas autoriser CORS depuis un site local : essai navigateur à confirmer.
- Les tests Node utilisent un fetch simulé ; pas de validation navigateur Android ou réseau réelle.
- Les nouvelles architectures snapshot V42–V46 ne sont pas encore déployées. Ne pas modifier le Worker sans tests de migration.
- Aucun changement sur GitHub, comptes ou Cloudflare.


## V52 — robustesse de l'interface
- L'annulation notifie immédiatement l'interface que le chargement est terminé.
- Les erreurs de chargement sont affichées explicitement et non comme un chargement infini.
- Un calcul manuel achevé après le lancement d'une autre recherche ne doit pas écraser les résultats plus récents.
- Les copies `*.browser.js` sont synchronisées avec les modules CommonJS.
- Tests simulés uniquement : aucun test Android réel ni appel API de production.

## V53 — ergonomie et robustesse
- Jauge : les événements `input` sont regroupés (250 ms), évitant une recherche réseau à chaque mouvement. Le pourcentage visible change immédiatement.
- Une sélection de véhicule ou un changement de mode annule une jauge en attente.
- L’ouverture « Voir plus » est conservée lors des mises à jour de classement ; la jauge en attente reste affichée tant que le garage n’a pas confirmé sa valeur.
- Les erreurs de recherche sont affichées au lieu d’un message trompeur de classement vérifié.
- Les tests Node ne prouvent pas la compatibilité Android. Vérification Chromium locale distincte à réaliser.

## V54 — prévention des courses entre modes et smoke JS navigateur
- Un identifiant de génération empêche une géolocalisation tardive de remplacer la démonstration choisie entre-temps.
- Le statut de l’essai réel distingue désormais les erreurs de classement d’une réussite.
- Nouveau test Node `vm` charge et exécute les trois bundles navigateur sans `require` ; il valide le comportement d’état.
- Chromium headless local expirait dans cet environnement ; **aucun test visuel Android ou Chromium réussi n’est revendiqué**.
- Aucun déploiement ni modification du dépôt.

## V55 — éviter les appels proxy inutiles
- `radar-live.js` et son bundle navigateur réutilisent la réponse des stations lors des recalculs `reloadStations:false`, uniquement pour le même carburant et la même origine (fixe pour cette instance).
- Un changement de carburant ou `refresh()` explicite recharge les données.
- Quatre tests nouveaux vérifient ces cas. Total : 451/451 tests Node.js.
- Chromium headless a encore expiré (timeout 18 s) : **aucune validation navigateur réelle**.
- Aucun changement en production.

## V56 — cache des stations invalidé à chaque actualisation explicite
- `radar-live.js` et `radar-live.browser.js` effacent `stationSource` au début d'un `refresh({reloadStations:true})`.
- Une actualisation échouée ou annulée ne peut plus faire réutiliser les anciennes stations lors du prochain changement de jauge.
- Deux tests nouveaux : échec de récupération et annulation pendant récupération.
- 453/453 tests Node.js réussis. Tentative Chromium headless avec délai de 10 s : expiration (code 124), pas de validation navigateur revendiquée.
- Aucun changement sur GitHub, Cloudflare ou en production.


## V57 — Isolation des recherches concurrentes
- `radar-live.js` invalide désormais les résultats de l’ancien véhicule **avant** toute notification `onUpdate`, même pendant le chargement.
- `cancel()` efface classement, stations et moteur précédent; les résultats retardés sont ignorés par génération.
- Tests de changement de véhicule, réponse tardive, annulation manuelle et jauge modifiée pendant un calcul.
- Tests Node.js uniquement, pas de validation Chromium/Android ou production.


## V58 — résultats incomplets et erreurs d’itinéraire
- `radar-view-model.js` : distingue `error`, `cancelled`, `unverified`, `verified` ; une erreur du proxy ne peut plus être présentée comme une recherche vérifiée.
- Les cartes exposent `routeUnavailable` et `blocksCertification` ; coûts et durées manquants restent `null`, et l’utilisateur peut relancer un calcul individuel.
- `radar-interface.html` : état « Recherche annulée » distinct.
- Cinq nouveaux tests de régression (`radar-view-model.v58.test.js`).
- Les tests Node ne valident ni Chromium ni Android ; les résultats du proxy réel et d’OSRM ne sont pas certifiés par ces tests.
- Pas de changement sur le site en production.

## V59 — Déduplication des calculs individuels simultanés

`radar-live.js` conserve une promesse en cours par identifiant de station et génération de recherche. Deux clics simultanés sur « Calculer le coût total » pour une même station partagent donc le même calcul au lieu de lancer deux demandes d'itinéraire. Une annulation ou un changement de recherche invalide les demandes précédentes et empêche un résultat obsolète de réapparaître. La version `radar-live.browser.js` a été synchronisée. Deux tests de régression ont été ajoutés.

Limites : cette protection n'est pas un quota global d'API ni une validation dans un vrai navigateur. Tests réels du proxy, d'OSRM et d'Android encore nécessaires. Aucun déploiement.

## V60 — Temporisation après saturation du service routier
- `routing-guard.js` reconnaît HTTP 429 et 503 et applique `Retry-After` (secondes ou date HTTP), avec repli sur `cooldownMs` et plafond de 1 h.
- Pendant la temporisation, `routeBatch` renvoie `route_unavailable` sans inventer de distances ou de coûts. `status()` expose `rateLimited` et `retryAfterMs`.
- Trois nouveaux tests dans `routing-guard.test.js` vérifient 429, 503 et le plafond.
- Limite importante : garde en mémoire d'une seule instance, pas de quota partagé entre utilisateurs. Pas de test d'intégration réel OSRM ni de navigateur Android.
- Aucun déploiement ni modification du dépôt de production.

## V61 — Résultats partiels OSRM conservés
- `routing-guard.js` conserve les itinéraires valides retournés par `resolveRoutes` lorsqu'un autre lot échoue ; les routes manquantes restent `route_unavailable`.
- Le compteur d'échecs et le coupe-circuit restent actifs après une erreur réseau ; aucun résultat partiel n'est présenté comme certification du Top 10.
- Deux tests nouveaux : un lot réussi suivi d'un lot en panne, et conservation d'une entrée du cache lors d'une erreur HTTP 503 sur une autre station.
- 470/470 tests Node.js réussis. Tests navigateur/Android et API réelles non validés. Aucun déploiement.


## V62 — récupération pendant indisponibilité OSRM
- Les trajets encore valides en cache restent disponibles même quand le circuit est ouvert ou que le service impose un délai Retry-After.
- Après une réponse 429, les autres lots de la même recherche ne déclenchent plus d'appels réseau pendant le délai imposé.
- Tests unitaires V62 avec horloge et fournisseur simulés ; pas de validation réelle Android/API.

## V63 — Cache GPS et validation des entrées
- `routing-guard.js` valide l'origine, les coordonnées de toutes les stations et l'unicité des identifiants **avant** le coupe-circuit OSRM. Les requêtes invalides ne sont plus silencieusement présentées comme indisponibles pendant une panne.
- `routing-guard.v63.test.js` : cinq tests pour changement de position GPS, déplacement d'une station à ID identique, expiration du cache pendant limitation, IDs dupliqués pendant limitation, coordonnées GPS invalides pendant limitation.
- Les clés de cache existantes intègrent déjà origine + ID + coordonnées de station : les tests de régression confirment cette propriété sans modifier leur format.
- 477 tests Node.js réussis. Pas de test réel OSRM/Android/Chromium. Pas de modification GitHub, Cloudflare ou production.

## V64 — tests d'intégration du moteur à l'état de l'interface
- `radar-integration.test.js` : 6 scénarios reliant `createLiveRadar` à `createUiState` (récupération et classement, jauge, changement de véhicule, Voir plus, couverture incomplète, itinéraire manquant).
- 483/483 tests Node.js réussis le 12/11/2026. Ce sont des tests de modules avec fournisseurs simulés, **pas** des tests DOM/Chromium/Android ni des appels réels aux API.
- Lors de la création des tests, le scénario « Voir plus » supposait qu'une station déjà calculée devait présenter un bouton de calcul : assertion corrigée pour refléter l'état réel. Aucun correctif de production dans cette version.
- Suite : automatisation des interactions DOM dans un navigateur réel, contrôle des contrats du proxy et OSRM, validation Android, puis préparation d'une intégration sur branche isolée. Ne pas déployer sans validation.

## V65 — Parcours d’intégration réseau et état d’annulation
- `radar-ui.js` et bundle navigateur : un état `cancelled` est désormais affiché explicitement, sans être assimilé à un chargement infini.
- `radar-integration.v65.test.js` : cinq tests de régression (annulation, panne proxy, reprise, ancienne réponse tardive, annulation pendant chargement).
- Test Chromium réel tenté dans le conteneur avec `--headless --no-sandbox --dump-dom` : expiration du délai ; non validé.
- Aucun appel réel aux API, aucun déploiement.

## V66 — Serveur de prévisualisation HTTP isolé
- `preview-server.js` sert uniquement l'interface, la page smoke et les trois bundles depuis `127.0.0.1` sur un port aléatoire : `node preview-server.js`.
- Politique CSP `connect-src 'none'` : les requêtes vers le proxy et OSRM sont intentionnellement bloquées. Utiliser uniquement le mode démonstration dans cet environnement ; le mode réel ne peut pas fonctionner avec cette CSP.
- Quatre tests HTTP de bout en bout sur loopback : page HTML, trois scripts, refus des autres fichiers et méthodes, en-têtes de sécurité.
- 492/492 tests Node.js réussis. Le test Chromium réel n'est toujours pas validé (tentative CLI expirée). Aucun test Android ni appel réseau API réelle ; aucun déploiement.
- Prochaine étape : tests DOM automatisés sur navigateur utilisable, puis tests API sur environnement de préproduction contrôlé, avant toute intégration.


## V67 — isolation des modes et prévisualisation honnête
- Les mises à jour tardives du moteur de démonstration ou du moteur réel sont ignorées si l’utilisateur a changé de mode (garde `modeGeneration` dans les deux callbacks `onUpdate`).
- Une fin tardive de géolocalisation ne réinitialise plus le bouton du nouveau mode ; le retour à la démonstration le réactive explicitement.
- Le serveur HTTP de prévisualisation désactive visuellement le bouton « données réelles », en cohérence avec `connect-src 'none'`. Le fichier HTML hors serveur conserve le mode réel pour les tests futurs autorisés.
- Tests V67 : régressions de structure et test HTTP de la page isolée. Ces tests ne remplacent pas une exécution DOM/Chromium.

## V68 — diagnostic de navigateur réel
- Ajout de `browser-check.js` : démarre un serveur local isolé, lance Chromium en mode headless, recherche le résultat explicite `PASS` dans `browser-smoke.html`, impose un délai maximum et arrête le serveur même en cas d'échec.
- Le test `browser-check.test.js` vérifie qu'un exécutable navigateur absent ne peut pas être interprété comme un succès.
- Pour tenter la validation : `node browser-check.js`. Un délai dépassé ou un navigateur indisponible signifie **non validé**, pas réussi.
- Aucun appel à l'API réelle ni changement en production.

## V69 — Diagnostic en deux étapes du navigateur
- `browser-diagnostics.js` distingue un blocage au **démarrage minimal de Chromium** d’un problème de chargement de l’application.
- `node browser-diagnostics.js` exécute d’abord une page `data:` minimale puis, seulement si elle passe, le test `browser-smoke.html` sur le serveur local isolé.
- Trois nouveaux tests vérifient les cas navigateur absent, absence de lancement de la seconde étape et faux positif sans marqueur DOM.
- Aucun test navigateur expiré ne vaut réussite ; aucun appel API ni déploiement.

## V70 — Validation alternative explicite (sans navigateur)
- `node browser-fallback.js` exécute les trois bundles et le script de `browser-smoke.html` dans un contexte Node `vm` avec un DOM minimal simulé.
- Un résultat `simulated_pass` confirme uniquement la compatibilité JavaScript de ce parcours ; **ce n’est pas un test Chromium, Android, DOM complet ou réseau**.
- `browser-fallback.test.js` garantit que le rapport ne revendique jamais une validation navigateur.
- Pour un test navigateur réel, lancer `node browser-diagnostics.js` dans un environnement où Chromium démarre, puis vérifier manuellement les interactions sur Android.
- Intégration Claude : conserver le proxy existant (authentification et pays multiples), intégrer d’abord sur branche de test, vérifier pagination exhaustive et routes OSRM, puis mesurer performances et erreurs avant toute fusion.
- Aucun changement GitHub/Cloudflare/production.

## V71 — Expiration du cache routier de l'orchestrateur
- `radar-live.js` et `radar-live.browser.js` : cache des itinéraires de l'orchestrateur limité à 15 minutes par défaut (`routeCacheTtlMs`), horloge injectable (`now`).
- Les changements de jauge réutilisent un trajet encore valide, mais demandent un nouveau calcul après expiration.
- `radar-live.v71.test.js` : quatre tests de régression (cache valide, expiration, frontière TTL, configuration invalide).
- 506/506 tests Node.js réussis. Les tests navigateur réel, Android et API réelles restent à réaliser.
- **Attention intégration** : l'interface HTML est un prototype distinct ; ne pas fusionner sans test de bout en bout. Le proxy historique ne garantit pas l'exhaustivité des stations et le service OSRM public ne garantit pas les capacités nécessaires à une production à grande échelle.
- **Plan de validation avant fusion** : (1) tester le proxy sur zone avec >100 stations et vérifier pagination/exhaustivité, (2) tester OSRM aller/retour et cas 429/503, (3) tester l'interface dans Chromium/Android, (4) tester le garage et la synchronisation des comptes, (5) mesurer performances et charge, (6) intégration sur branche isolée, sans modifier les routes existantes du Worker, (7) déploiement seulement après accord explicite.

## V72 — synchronisation du garage, protocole isolé
- Nouveau `garage-sync.js` : protocole de lecture + écriture atomique conditionnelle (`read`, `compareAndSwap`) et adaptateur **mémoire uniquement** pour tests.
- Les écritures concurrentes sont détectées et signalées `conflict` : **aucune fusion silencieuse, aucun écrasement du garage d'un autre appareil**.
- Plusieurs modifications hors ligne sont enregistrées en une seule révision serveur ; aucun accès réseau ni compte utilisateur n'est intégré à ce stade.
- Avant intégration, Claude doit raccorder un endpoint authentifié par utilisateur, isoler les garages entre comptes, vérifier les autorisations, implémenter une CAS atomique côté serveur et gérer explicitement les conflits côté interface.
- Ne jamais utiliser l'adaptateur mémoire pour promettre une synchronisation entre appareils ou une persistance durable.

## V73 — audit du contrat d'exhaustivité du proxy

**Incompatibilité identifiée** : `proxy-contract.js` attend un endpoint V2 à curseurs (`?v=2`, `cursor`, `snapshot`) tandis que `worker-france-v2.js` définit un endpoint autonome `/v2/france` exigeant `fuel` et renvoyant une réponse unique. Ces deux modules ne doivent pas être raccordés directement.

- Nouveau `proxy-single-response.js` : adaptateur **explicite** du contrat actuel de `worker-france-v2.js` (une seule réponse, `/v2/france`, `fuel`, `sourceTotal`, `total`, `complete`). Validation stricte avant de déclarer la réponse complète.
- `proxy-single-response.test.js` : tests du contrat, des doublons, des totaux et de l'URL.
- **Bloquant production** : `worker-france-v2.js` reste un prototype non déployé. Il peut renvoyer HTTP 503 pour une recherche trop grande (`maxRecords`, `maxPages`), et sa pagination interne via offset sur une source mouvante ne constitue pas une preuve de snapshot immuable. La valeur `snapshot: single-response-N` n'est pas une empreinte du contenu. Il faut une véritable génération de snapshot versionné et un stockage atomique avant de certifier l'exhaustivité sur le service réel.
- Ne pas activer ce chemin dans la PWA en production tant que le Worker réel, la sécurité, les quotas, la couverture géographique et les tests réseau ne sont pas validés. Le fournisseur legacy reste non certifiable.

## V74 — contrôle d'exhaustivité de la source avant publication
- `source-snapshot-loader.js` : récupère toutes les pages avec un ordre stable attendu du fournisseur, refuse pages courtes, doublons, changements de total et dépassement des limites.
- Deux lectures complètes consécutives sont comparées par empreinte SHA-256 : cela détecte des modifications entre les lectures, mais **ne garantit pas l'atomicité** de la source si elle change puis revient à l'état initial ou pendant chaque lecture.
- **Ne pas présenter le Top 10 comme certifié sur cette seule base.** Pour une garantie forte, obtenir un export source figé/versionné ou une API à curseur lié à un snapshot immuable, puis publier atomiquement une version côté Worker.
- Le Worker `/v2/france` de V41 ne consomme pas encore ce chargeur ; ne pas le déployer tel quel. Conserver les routes historiques, authentification et pays existants.
- Aucun accès aux API réelles, aucun changement de production.

## V75 — garde de publication et transmission Claude
- `release-gate.js` bloque toute déclaration de préparation sans dix validations réelles documentées : source immuable, couverture complète, publication atomique, compatibilité proxy, OSRM réel, navigateur réel, Android réel, synchronisation des comptes, performances et rollback.
- `release-gate.test.js` vérifie que les tests simulés ne satisfont pas les critères réels.
- `V75_CLAUDE_HANDOFF.md` détaille le passage de relais **sur branche isolée**, sans mise en ligne publique.
- Aucun de ces contrôles n'est une preuve que les services réels fonctionnent déjà.

## V76 — audit statique de transmission
- `node integration-audit.js` produit un inventaire SHA-256 des fichiers critiques et une liste explicite des preuves manquantes.
- Les tests locaux ne constituent **pas** une autorisation de fusion, déploiement ou publication.
- Le dossier peut être transmis à Claude pour intégration sur **branche isolée / staging non public**. Aucun changement en production sans accord explicite.
