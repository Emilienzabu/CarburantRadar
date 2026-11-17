# Application Android (TWA) — CarburantRadar

## Pourquoi la barre orange avec l'URL s'affichait

Une TWA n'est plein écran que si Android/Chrome valident la relation Digital Asset Links entre l'app et le site. Deux défauts cumulés l'empêchaient :

1. **Dossier mal nommé** : le fichier était dans `. well-known/` (avec un espace) au lieu de `.well-known/`. `https://carburantradar.fr/.well-known/assetlinks.json` n'existait donc pas. *(corrigé dans cette PR)*
2. **APK configuré pour l'ancien domaine** : l'APK actuel (`CarburantRadar.apk`, package `io.github.emilienzabu.twa`) a pour hôte `emilienzabu.github.io`, pour URL de démarrage `https://emilienzabu.github.io/CarburantRadar/index.html` et pour manifest `https://emilienzabu.github.io/CarburantRadar/manifest.json`. Le site étant servi sur `carburantradar.fr` (fichier `CNAME`), Chrome valide `emilienzabu.github.io` (aucun assetlinks.json n'y est publié) puis se retrouve sur un autre domaine. **Cet APK doit être reconstruit** pour `carburantradar.fr`.

Le certificat de l'APK (SHA-256 `25:AC:70:0F:…:0B:58`) et le package correspondent bien à `.well-known/assetlinks.json` : rien à changer de ce côté si la même clé de signature est réutilisée.

## Reconstruire l'APK (manuel, nécessite la clé de signature d'origine)

Sur https://www.pwabuilder.com, URL `https://carburantradar.fr`, puis *Package for stores > Android* :

| Option | Valeur |
|---|---|
| Package ID | `io.github.emilienzabu.twa` (inchangé : mise à jour par-dessus l'ancienne version) |
| Host / Start URL | `carburantradar.fr` / `/` |
| App version / version code | supérieurs à l'actuelle (actuelle : 1.0.0.0 / 1) |
| Signing key | **Use mine** : fichier `.keystore`, alias et mot de passe d'origine |

Avec la même clé, `assetlinks.json` reste valide. Avec une nouvelle clé, remplacer l'empreinte par celle fournie par PWABuilder (fichier `assetlinks.json` du package) et conserver l'ancienne dans la liste tant que d'anciens APK circulent.

Remplacer ensuite `CarburantRadar.apk` à la racine et retirer le décorateur `@unittest.expectedFailure` de `test_apk_cible_le_domaine_personnalise` dans `tests/test_twa_assetlinks.py`.

## Déploiement

Le site est publié par `.github/workflows/generate-city-pages.yml` (artefact Pages). Ce workflow ne se déclenche pas sur un simple changement de `.well-known/` : lancer *Run workflow* à la main ou attendre le cron quotidien (05:30 UTC). Le `tar` du workflow copie bien les dossiers cachés ; `.nojekyll` n'est pas nécessaire avec un déploiement par artefact.

## Vérifications après déploiement

- `https://carburantradar.fr/.well-known/assetlinks.json` : HTTP 200, JSON valide, `Content-Type: application/json`, sans redirection.
- `https://digitalassetlinks.googleapis.com/v1/statements:list?source.web.site=https://carburantradar.fr&relation=delegate_permission/common.handle_all_urls` : doit lister le package et l'empreinte.
- Sur le téléphone : désinstaller l'ancien APK, installer le nouveau, ouvrir : plein écran, sans barre d'URL. `adb shell pm get-app-links io.github.emilienzabu.twa` doit indiquer `verified` pour `carburantradar.fr`.

## Tests

`python3 -m unittest tests/test_twa_assetlinks.py -v` (dépendances optionnelles : `pip install cryptography androguard`).
