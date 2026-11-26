# CarburantRadar Plus

Ce premier lot gère les crédits quotidiens et les codes offerts. Le compte et la session restent vérifiés par `carburant-proxy`.

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

Le secret `PLUS_ADMIN_TOKEN` est à générer et à installer dans les deux Workers. Le proxy utilise la vérification d’administration existante pour la création d’un code. Cette opération reçoit `{months: 6 | 12 | null, maxUses: nombre, deadline?: millisecondes UTC}` sur `POST /plus/issue` avec l’en-tête `X-Admin-Key`. La réponse contient le code en clair à transmettre au bénéficiaire. Les valeurs des secrets restent dans Cloudflare.

Les autres opérations `POST /plus/status`, `/plus/claim`, `/plus/preview` et `/plus/redeem` utilisent le jeton du compte CarburantRadar. Les deux dernières reçoivent `{code}`. L’identité et la date de création sont lues côté serveur.

## Tests

Depuis la racine du dépôt, avec Node 24.

```sh
node --test workers/plus/test/plus.test.mjs
```

Les tests exercent SQL avec une base SQLite en mémoire ainsi que les routes entre le proxy et le service Plus. Relier le Worker à un environnement de test Cloudflare permet ensuite de vérifier les liaisons et le navigateur sur une installation réelle. Les paiements, les pubs et la consommation de crédits par les fonctionnalités seront raccordés dans des lots suivants.
