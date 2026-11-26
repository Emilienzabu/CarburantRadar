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

## Préproduction

Utiliser une instance privée distincte pour le Worker Plus et une copie de test du service de compte. Renseigner `STRIPE_SECRET_KEY` et `STRIPE_WEBHOOK_SECRET` comme secrets Cloudflare, les identifiants de prix `STRIPE_MONTHLY_PRICE` et `STRIPE_YEARLY_PRICE` comme variables, et `STRIPE_RETURN_URL` avec l’URL HTTPS de l’interface de test. Le service vérifie que les prix sont récurrents en euros à 100 centimes par mois et 1 000 centimes par an et exige une clé Stripe de test.

Dans la copie de test de `france/index.html`, remplacer l’URL de `PROXY` par celle du proxy de test. Créer les comptes de test sur ce proxy. Utiliser des espaces de stockage distincts et appeler le webhook de ce même proxy depuis Stripe. Ne pas modifier le proxy de production pour effectuer ces tests.

Configurer le portail client dans le même environnement Stripe. Le webhook public du proxy `POST /plus/stripe/webhook` relaie le corps et la signature au Worker Plus. Abonner l’endpoint à `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid` et `invoice.payment_failed`.

`PLUS_ANALYSIS_PREVIEW=1` active les analyses de 30, 90 et 365 jours sur `POST /plus/analysis`. Le serveur lit l’historique public, agrège les prix par jour et vérifie l’accès avant de rendre la série. Il débite un crédit pour 24 h après une confirmation et uniquement quand il dispose d’une série exploitable. Le graphique de sept jours reste gratuit.

La recharge de deux crédits via `/reward` est une opération privée qui nécessite le secret interne et un identifiant unique de récompense. L’adaptateur Google Ad Manager fournira cette opération uniquement après vérification de la notification de la régie.

## Comparaisons et alertes de préproduction

- `PLUS_TRIP_PREVIEW=1` propose la comparaison détaillée après le Trajet habituel, sur `POST /plus/trip`. Le serveur récupère les stations, vérifie les détours et compare le coût total, le prix au litre et le temps de détour. Il débite un crédit si au moins deux stations sont vérifiées. Une opération rejouée avec les mêmes paramètres retrouve son résultat pendant 24 h. Configurer `PLUS_OSRM_URL` avec une base OSRM HTTPS appropriée avec le suffixe `/route/v1/driving/` avant une utilisation durable. Le service de démonstration par défaut est réservé aux essais.
- `PLUS_ALERTS_PREVIEW=1` affiche les alertes supplémentaires. Une alerte gratuite historique reste gérée par le proxy existant. Chaque alerte supplémentaire coûte deux crédits pour sept jours, avec renouvellement manuel. L’abonnement Plus permet de surveiller jusqu’à douze zones simultanément sans débit. Les alertes incluses deviennent inactives quand les droits expirent, sauf si elles ont une durée payée restante.
- Copier `src/scheduled-alerts.mjs` près du fichier d’entrée du proxy de test et importer `deliverExtraAlerts`. Dans le gestionnaire planifié existant, appeler `ctx.waitUntil(deliverExtraAlerts(env, sendNotification))`. Activer `PLUS_ALERTS_DELIVERY=1` sur les deux Workers de test pour exécuter ce traitement. Les routes de traitement sont accessibles via la liaison de service privée et reprennent le service d’envoi Web Push du proxy. La règle des alertes supplémentaires est le seuil choisi par rapport à la moyenne, avec au plus une tentative de notification par alerte et par jour.

## Tests

Depuis la racine du dépôt, avec Node 24.

```sh
node --test workers/plus/test/plus.test.mjs
```

Les tests exercent SQL avec une base SQLite en mémoire, les routes du proxy et du service Plus, et des réponses simulées de Stripe, de l’historique, des stations et d’OSRM. Relier les Workers dans un environnement Cloudflare séparé permet ensuite de vérifier les services réels, Stripe avec une carte de test et la réception des notifications sur un téléphone.
