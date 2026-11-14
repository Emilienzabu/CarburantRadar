# Analyse des modifications du Worker `carburant-proxy` (aucun déploiement)

## Ce qui est accessible
Le code du Worker n'est **ni dans le dépôt de production, ni dans le Workspace** (`codes/worker_proxy.md` : « code hors dépôt »). Seul existe l'audit statique du 2026-11-04 (`audits/AUDIT_WORKER_CARBURANT_PROXY_2026-11-04.md`, établi sur un code compilé fourni en conversation, non archivé). Rien ci-dessous n'invente son fonctionnement : tout ce qui n'est pas dans l'audit est listé comme manquant.

## Ce que l'audit établit
Routes `/register /login /logout /account(GET,POST) /subscribe /unsubscribe /update-names /track /admin/*`, liaisons `USERS` (comptes + sessions), `SUBS`, `DB_STATS`, `DB_ITALIE`, mots de passe PBKDF2-SHA256, sessions aléatoires à expiration, France par `within_distance` avec cache mémoire 10 min, **sans** `limit` paginé exhaustif.

## Ce qui MANQUE pour intégrer le garage (à fournir, sans secrets)
1. Fonction qui lit le jeton de session : en-tête ou cookie, nom, préfixe.
2. Clés KV : format de la clé de session et de la clé de compte dans `USERS`, durée d'expiration, valeur stockée (identifiant stable du compte ? e-mail ?).
3. Comment `/account` POST fusionne `favoris/noms/repères/préférences` (le garage doit-il y vivre ou à part ?).
4. Gestion CORS actuelle (origines, en-têtes) et traitement d'`OPTIONS`.
5. `wrangler.toml` / liaisons réelles, plan Cloudflare (gratuit/payant), cron réel (`10 5 * * *` ?).
6. Existence d'une route de suppression de compte (aucune n'est listée).
7. Politique de limitation de débit (l'audit signale son absence).

## Modifications proposées (une fois 1 à 4 fournis)
**Option A (recommandée)** — ajouter dans `carburant-proxy` : `if (path === '/v2/garage') return handleGarage(request, { db: env.DB_RADAR, authenticate, allowedOrigins })`, où `authenticate(request)` réutilise la validation de session existante et renvoie `{ userId }` (identifiant stable du compte). Nouvelle liaison D1 `DB_RADAR` (migration `0002_garage.sql`). Aucune route existante ne change ; l'authentification actuelle n'est pas modifiée.
**Option B** — Worker V2 séparé liant en **lecture seule** le même KV `USERS` : exige de connaître exactement le format des sessions (point 2) et duplique la logique d'authentification : déconseillé.

Dans les deux cas : limite de débit sur `PUT` (règle Cloudflare), suppression de compte à brancher sur `deleteGarageForUser`, durées de conservation à documenter (RGPD ; l'audit signale ce manque pour `/track`).

## Le contrat V2 snapshot ne nécessite AUCUNE modification de `carburant-proxy`
Il vit dans le Worker V2 séparé. Le seul changement côté proxy envisagé est celui du garage (option A). Les anomalies P0/P1 de l'audit (import italien non atomique, alertes, abonnements Push, cache français arrondi) sont **hors périmètre** de ce lot et inchangées.
