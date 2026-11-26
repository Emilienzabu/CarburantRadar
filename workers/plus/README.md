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

Configurer le portail client dans le même environnement Stripe. Le webhook public du proxy `POST /plus/stripe/webhook` relaie le corps et la signature au Worker Plus. Abonner l’endpoint à `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid` et `invoice.payment_failed`.

`PLUS_ANALYSIS_PREVIEW=1` expose le déblocage de l’analyse détaillée pour 24 h contre un crédit. L’interface de prévisualisation vérifie cette autorisation quand elle a chargé l’état du compte. Pour une activation publique, faire vérifier l’accès par le serveur qui fournit les calculs avancés.

La recharge de deux crédits via `/reward` est une opération privée qui nécessite le secret interne et un identifiant unique de récompense. L’adaptateur Google Ad Manager fournira cette opération uniquement après vérification de la notification de la régie.

## Tests

Depuis la racine du dépôt, avec Node 24.

```sh
node --test workers/plus/test/plus.test.mjs
```

Les tests exercent SQL avec une base SQLite en mémoire, les routes entre le proxy et le service Plus et les réponses Stripe simulées. Relier les Workers dans un environnement Cloudflare séparé permet ensuite de vérifier les liaisons et l’environnement Stripe avec une carte de test. Les alertes multizones et le Trajet avancé feront l’objet d’un lot séparé.
