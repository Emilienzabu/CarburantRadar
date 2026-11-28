# CarburantRadar Plus

Ce service gère les crédits, les codes offerts et les abonnements Stripe de test. Le compte et la session restent vérifiés par `carburant-proxy`.

- Le solde démarre à cinq crédits sur chaque compte. Un crédit supplémentaire peut être réclamé à partir du lendemain de la création du compte, selon le calendrier de Paris. Les crédits réclamés s’accumulent.
- Les codes offrent six mois, douze mois ou un accès à vie. Une durée offerte prolonge un accès temporaire en cours. Les codes peuvent avoir une échéance et un quota global. Chaque compte peut utiliser un code une seule fois.
- L’identifiant transmis au service Plus est dérivé de l’identité et de la date de création vérifiées par le service de compte. Les codes sont conservés sous forme d’empreintes.

## Raccordement à carburant-proxy

La configuration Wrangler de ce dossier déclare un Worker privé appelé `carburant-plus`. Dans le projet source de `carburant-proxy`, ajouter une liaison de service `PLUS` vers ce Worker. Copier `src/proxy.mjs` près du fichier d’entrée et importer `forwardPlus`. Dans le gestionnaire HTTP, déclarer cette route après le traitement d’`OPTIONS` et avant la réponse de fin.

```js
if (path.startsWith('/plus/')) {
  return forwardPlus(request, env, headers, utilisateurDepuisJeton, adminAutorise);
}
```

Le secret `PLUS_ADMIN_TOKEN` est à générer et à installer dans les deux Workers. La page `/admin/plus.html` permet de créer un code avec la clé d’administration existante. Cette opération reçoit `{months: 6 | 12 | null, maxUses: nombre, deadline?: millisecondes UTC}` sur `POST /plus/issue` avec l’en-tête `X-Admin-Key`. La réponse contient le code en clair à transmettre au bénéficiaire. Les valeurs des secrets restent dans Cloudflare.

Les autres opérations `POST /plus/status`, `/plus/claim`, `/plus/preview` et `/plus/redeem` utilisent le jeton du compte CarburantRadar. Les deux dernières reçoivent `{code}`. L’identité et la date de création sont lues côté serveur.

## Préproduction Stripe et publicités

La configuration `wrangler.preprod.jsonc` crée un Worker et des espaces de stockage séparés. Elle contient les deux identifiants de tarifs de test. La page France, son manifeste et son service worker sont copiés avec le proxy de même origine. Le script de préparation retire les appels publicitaires et de mesure d’audience. Les comptes de test utilisent une adresse de la forme `mensuel@carburantradar.invalid` et un mot de passe réservé à la préproduction.

```sh
node workers/plus/prepare-preprod.mjs
npx --yes wrangler@4 deploy --dry-run --config workers/plus/wrangler.preprod.jsonc
npx --yes wrangler@4 deploy --config workers/plus/wrangler.preprod.jsonc
```

Le nom du Worker est `carburant-plus-preprod`. Avec le sous-domaine Workers actuel du projet, le site prévu est [CarburantRadar Plus de test](https://carburant-plus-preprod.emilienzabukovec09.workers.dev/france/) et le webhook est `https://carburant-plus-preprod.emilienzabukovec09.workers.dev/plus/stripe/webhook`. Valider l’URL affichée par Cloudflare après déploiement avant de l’enregistrer dans Stripe. Les Workers et les Durable Objects SQLite sont compatibles avec le forfait gratuit dans la limite de ses quotas. [Limites Workers](https://developers.cloudflare.com/workers/platform/limits/) · [Tarifs Durable Objects](https://developers.cloudflare.com/durable-objects/platform/pricing/)

| Paramètre | Type | Usage |
|---|---|---|
| `PREVIEW_LOGIN_PASSWORD` | Secret Cloudflare | Mot de passe de test aléatoire, 24 caractères ou plus |
| `STRIPE_SECRET_KEY` | Secret Cloudflare | Clé Stripe de test avec le préfixe `sk_test_` |
| `STRIPE_WEBHOOK_SECRET` | Secret Cloudflare | Secret Stripe de la destination de préproduction avec le préfixe `whsec_` |
| `STRIPE_MONTHLY_PRICE`, `STRIPE_YEARLY_PRICE` | Variables | Identifiants de tarifs de test déjà renseignés |
| `STRIPE_RETURN_URL` | Variable | URL HTTPS de la page France de préproduction |
| `PLUS_BILLING_TEST` | Variable | `1` pour ouvrir Checkout et le portail de test, `0` pour les désactiver |
| `PLUS_REWARD_SIMULATION` | Variable | `1` pour la simulation sans annonces ni écriture de solde, `0` pour la masquer |
| `PLUS_ADMIN_TOKEN` | Secret Cloudflare | Jeton interne pour les outils d’administration et une future intégration de récompenses vérifiées |

Dans Stripe Workbench, créer une destination de test pour **Votre compte** avec des événements **Snapshot**. Sélectionner `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. Le serveur vérifie la signature sur les octets reçus, relit l’abonnement chez Stripe et traite un événement reconnu une seule fois dans la fenêtre de 31 jours. Les données de retour du navigateur ne déclenchent aucune activation. [Webhooks Stripe](https://docs.stripe.com/webhooks)

### Recette Stripe en préproduction

La destination Snapshot utilise `2026-11-18.endive`. Elle fournit l’identifiant d’abonnement des factures via `parent.subscription_details.subscription`. Le Worker relit ensuite l’abonnement via l’API Stripe fixée à `2025-04-30.basil`. Cette réponse fournit la date de fin par tarif dans `items.data[].current_period_end` et l’état de la dernière facture. Le test automatisé couvre cette combinaison à travers le proxy avec le corps brut signé. Une livraison de la destination du compte de test permet de vérifier la signature configurée sur Cloudflare. [Versionnement Stripe](https://docs.stripe.com/api/versioning) · [Structure des factures](https://docs.stripe.com/changelog/basil/2025-03-31/adds-new-parent-field-to-invoicing-objects)

Ouvrir la [page de préproduction](https://carburant-plus-preprod.emilienzabukovec09.workers.dev/france/). Se connecter dans **Menu → Compte** avec une adresse ci-dessous et le mot de passe de préproduction. Chaque adresse crée un compte de test distinct à la première connexion. Les tests de paiement se font dans l’espace Stripe de test avec la carte `4242 4242 4242 4242`, une échéance future et un CVC de trois chiffres. [Cartes de test Stripe](https://docs.stripe.com/testing)

| Scénario | Manipulation | Résultat attendu |
|---|---|---|
| Offre mensuelle | `mensuel@carburantradar.invalid` → **CarburantRadar Plus → Tester à 1 €/mois**. Terminer le paiement de test. | Checkout affiche 1 €/mois et revient sur la préproduction. Plus devient actif après confirmation Stripe. |
| Signature et abonnement | Dans l’espace de test Stripe, ouvrir **Workbench → Webhooks → destination CarburantRadar → Livraisons**. Sélectionner `checkout.session.completed` puis `invoice.paid`. | Les livraisons sont réussies avec HTTP 200 et la version indiquée est `2026-11-18.endive`. |
| Offre annuelle | Se déconnecter ou utiliser une fenêtre privée. Avec `annuel@carburantradar.invalid`, choisir **Tester à 10 €/an** et terminer le paiement de test. | Checkout affiche 10 €/an. Après livraison, Plus est actif avec une échéance annuelle. Les deux comptes gardent leurs droits indépendants. |
| Avantages Plus | Noter le solde d’un compte abonné, puis choisir une période de 30 jours dans **Analyse** après avoir sélectionné une zone avec des données. | Si la source renvoie le graphique, il est inclus dans Plus et le solde est identique. |
| Portail | Depuis le compte mensuel, ouvrir **Gérer mon abonnement de test**. Consulter la facture et l’écran du moyen de paiement. | Le portail Stripe de test présente l’abonnement et la facture du compte mensuel. Le lien de retour ramène à la préproduction. |
| Résiliation à échéance | Dans le portail du compte mensuel, sélectionner la résiliation à la fin de la période. Revenir à CarburantRadar. | `customer.subscription.updated` est livré. Plus reste actif jusqu’à la date payée. |
| Résiliation immédiate et rejeu | Dans le tableau Stripe de test, annuler immédiatement l’abonnement annuel identifié par son tarif, puis rouvrir Plus sur ce compte. Dans Workbench, renvoyer un ancien `checkout.session.completed` de ce même abonnement. | `customer.subscription.deleted` est livré. Le compte annuel repasse en gratuit et le renvoi ne réactive pas Plus. |
| Refus et abandon | Avec `refus@carburantradar.invalid`, utiliser la carte de test `4000 0000 0000 0002` dans Checkout, puis revenir à CarburantRadar sans terminer le paiement. | Stripe refuse la carte et le retour indique l’annulation. Le compte reste gratuit. |

Le renouvellement, l’expiration et l’échec d’un renouvellement sont couverts par la suite automatisée qui simule les réponses de Stripe. Les comptes créés par Checkout dans cette préproduction ne sont pas rattachés à une horloge de test. Pour qualifier un cycle accéléré côté Stripe, préparer séparément un client rattaché à une horloge. [Tests Billing Stripe](https://docs.stripe.com/billing/testing)

Pour le retour de recette, relever le type d’événement, le code HTTP et le statut Plus affiché. Le statut d’une livraison est visible dans Workbench et un événement peut être renvoyé depuis cette vue. [Vérifier les livraisons](https://docs.stripe.com/webhooks#view-event-deliveries)

`PLUS_ANALYSIS_PREVIEW=1` active les analyses de 30, 90 et 365 jours sur `POST /plus/analysis`. Le serveur lit l’historique public, agrège les prix par jour et vérifie l’accès avant de rendre la série. Il débite un crédit pour 24 h après une confirmation et uniquement quand il dispose d’une série exploitable. Le graphique de sept jours reste gratuit.

## Publicités récompensées

Le panneau de simulation couvre l’accord volontaire, le refus, la fermeture, l’absence d’inventaire et la récompense de deux crédits simulés. Le composant suit les quatre événements GPT et teste les doublons sans charger GPT. Les 20 dernières opérations réelles ajoutées au registre (crédit du jour, récompense confirmée, dépenses) sont affichées. Le solde initial et les opérations antérieures à l’ajout du registre ne sont pas reconstruits.

Google documente des rappels HTTP GET de validation serveur pour l’inventaire récompensé Web. Après l’ouverture d’Ad Manager, relever le chemin complet du bloc récompensé Web, vérifier que les réglages de validation serveur sont disponibles pour ce bloc et récupérer la documentation du format des rappels, de leur preuve d’authenticité et du mécanisme de référence utilisateur. Le détail de ces paramètres reste à vérifier avec Google. [Annonces récompensées Web](https://support.google.com/admanager/answer/9116812?hl=fr) · [Exemple GPT](https://developers.google.com/publisher-tag/samples/display-rewarded-ad)

Le point d’attribution privé `/reward` accepte un compte vérifié et un identifiant d’événement unique. L’attribution de deux crédits et son écriture au registre sont atomiques. Le raccordement Google devra vérifier le rappel, associer sa référence temporaire au compte de l’utilisateur, puis appeler cette opération avec l’identifiant stable de la régie. Un événement reçu dans le navigateur ne déclenche aucun crédit réel. Le site en ligne possède déjà `ads.txt`. Vérifier l’alignement de son identifiant éditeur avec les tags existants avant d’activer des annonces.

## Avant le lancement commercial

- Faire valider le titulaire du compte Stripe et AdSense et les informations du vendeur par le représentant légal. Préparer les CGU, CGV et mentions de confidentialité avec les traitements liés au compte, aux crédits, aux paiements et aux annonces. Faire vérifier le prix total, le renouvellement, le droit de rétractation applicable et le parcours de résiliation en ligne. [Règles françaises du commerce en ligne](https://entreprendre.service-public.gouv.fr/vosdroits/F23455)
- Vérifier les règles de paiement Google Play applicables à l’APK avant d’ouvrir l’abonnement dans la version distribuée sur le Store. [Règles Google Play sur les paiements](https://support.google.com/googleplay/android-developer/answer/9858738?hl=fr)
- Mettre en place et tester une CMP certifiée et les choix de consentement applicables en France et dans les autres régions visées avant toute demande publicitaire. Tester le refus et le retrait du consentement. [Exigences Google pour les CMP](https://support.google.com/admanager/answer/13554116?hl=fr) · [Cookies et traceurs, CNIL](https://cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies/FAQ)
- Après validation explicite, prévoir des tarifs, des secrets, une destination Stripe et des espaces de stockage dédiés à la production. Le code actuel n’accepte que Stripe de test. L’ouverture des paiements réels nécessitera une modification et une nouvelle revue. Activer les publicités séparément après vérification du rappel serveur chez Google et du parcours de consentement.

## Comparaisons et alertes de préproduction

- `PLUS_TRIP_PREVIEW=1` propose la comparaison détaillée après le Trajet habituel, sur `POST /plus/trip`. Le départ peut être saisi ou fourni par la géolocalisation. Le navigateur et le serveur calculent les itinéraires français à partir de la Géoplateforme de l’IGN. Le serveur récupère les prix, vérifie les détours et compare le coût total, le prix au litre et le temps de détour. Il débite un crédit si au moins deux stations sont vérifiées et si le compte est gratuit. Une opération rejouée avec les mêmes paramètres retrouve son résultat pendant 24 h. `PLUS_OSRM_URL` permet de configurer un autre serveur de routage HTTPS côté serveur avec le suffixe `/route/v1/driving/`.
- `PLUS_ALERTS_PREVIEW=1` affiche les alertes supplémentaires. Une alerte gratuite historique reste gérée par le proxy existant. Chaque alerte supplémentaire coûte deux crédits pour sept jours, avec renouvellement manuel. L’abonnement Plus permet de surveiller jusqu’à douze zones simultanément sans débit. Les alertes incluses deviennent inactives quand les droits expirent, sauf si elles ont une durée payée restante.
- Copier `src/scheduled-alerts.mjs` près du fichier d’entrée du proxy de test et importer `deliverExtraAlerts`. Dans le gestionnaire planifié existant, appeler `ctx.waitUntil(deliverExtraAlerts(env, sendNotification))`. Activer `PLUS_ALERTS_DELIVERY=1` sur les deux Workers de test pour exécuter ce traitement. Les routes de traitement sont accessibles via la liaison de service privée et reprennent le service d’envoi Web Push du proxy. La règle des alertes supplémentaires est le seuil choisi par rapport à la moyenne, avec au plus une tentative de notification par alerte et par jour.

## Tests

Depuis la racine du dépôt, avec Node 24.

```sh
node --test workers/plus/test/plus.test.mjs
```

Les tests exercent SQL avec une base SQLite en mémoire, les routes du proxy et du service Plus, et des réponses simulées de Stripe, de l’historique, des stations et d’OSRM. Relier les Workers dans un environnement Cloudflare séparé permet ensuite de vérifier les services réels, Stripe avec une carte de test et la réception des notifications sur un téléphone.
