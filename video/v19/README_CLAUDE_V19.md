# CarburantRadar V19 — diagnostic GitHub Actions manuel

## Objectif
Exécuter V18/V17 sur un runner GitHub Actions connecté, **sans publication ni déploiement**. Aucun commit n'a été effectué par ChatGPT. La vidéo produite, si elle existe, est un **brouillon non validé**.

## Intervention minimale de Claude
1. Sur une **nouvelle branche dédiée**, ajouter le contenu de ce paquet sous `video/v19/`, sauf le workflow YAML qui va à `.github/workflows/carburant-v19-diagnostic.yml`.
2. Ouvrir une PR **sans la fusionner**. Pour le tout premier `workflow_dispatch`, GitHub peut exiger que le workflow soit présent sur la branche par défaut; **ne pas fusionner pour contourner cette restriction**. Si le bouton Run workflow n'apparaît pas, utiliser l'API GitHub `workflow_dispatch` uniquement si GitHub accepte la branche, sinon signaler le blocage.
3. Lancer manuellement le workflow sur la branche dédiée avec ville et carburant souhaités (par exemple Lyon/Gazole).
4. Renvoyer l'archive d'artefacts `carburant-v19-diagnostic-*` et le journal de l'exécution. Ne pas corriger le code, déployer, publier, modifier main ou fusionner.

## Sécurité
- Déclenchement **uniquement manuel**, aucune planification ni `push`.
- Permissions du GITHUB_TOKEN : `contents: read`.
- Aucun secret fourni, aucune étape d'upload vers YouTube, Instagram ou Cloudflare.
- La commande produit seulement `diagnostics/brouillon.mp4`.
- L'artefact est conservé 7 jours.
- Attention : les captures sont temporaires dans V17 et ne sont pas conservées par le pipeline en cas d'échec. Le journal de la commande est conservé si l'étape atteint le pipeline.

## Limites connues
- Le préflight utilise une vérification réseau et peut échouer pour des raisons indépendantes de Playwright.
- Le workflow suppose que les modules sont copiés dans `video/v19/`.
- L'essai peut révéler des défauts d'intégration; ne pas désactiver les contrôles pour le faire passer.
- La vidéo ne comprend pas encore de voix off ou de musique finalisée.
- L'existence d'un MP4 ne prouve pas à elle seule l'exactitude des données affichées.
