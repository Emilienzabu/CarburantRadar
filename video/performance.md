# Apprentissage à partir des vidéos publiées

Chaque pilote écrit une fiche `.creation.json` avec son scénario, sa catégorie,
son identité graphique, sa durée mesurée dans le MP4, la voix, la musique et
l'empreinte du fichier. Pour les essais des pilotes, fournir un identifiant
interne stable avec `--id-video`.

## Registre et collecte

La publication quotidienne utilise GitHub Actions et le Worker Cloudflare pour
YouTube et Instagram. Lorsqu'une plateforme confirme un envoi et que son
identifiant vidéo est disponible, le générateur fournit un fichier
`.publications.json` dans l'artefact **references-publication**. Le reçu
contient le créneau, l'identifiant de la plateforme, la durée mesurée, le
carburant si applicable, les hashtags transmis pour cette plateforme et
l'horodatage de confirmation du Worker. Une réponse partielle conserve
uniquement les références confirmées. Un identifiant manquant est signalé sans
relancer la publication.

Le collecteur autonome accepte un tableau JSON de ces reçus. En mode programmé,
le compartiment privé Cloudflare fait office de registre persistant.
Pour un rendu publié autrement, associer la fiche de création à la
`plateforme`, au `video_id` de la plateforme, à `publie_le` avec fuseau et
aux `hashtags` de cette publication. Le même rendu peut avoir une ligne
distincte par plateforme. Marquer `organique: false` si une diffusion reçoit
une promotion payante et exclure de l'apprentissage toute mesure antérieure
de cette diffusion devenue sponsorisée.

```sh
python video/collecte_stats.py publications.json mesures.jsonl
python video/performance.py mesures.jsonl > decisions.json
```

Le collecteur active YouTube et Instagram par défaut. Il lit leurs statistiques
avec `CR_YOUTUBE_TOKEN` et `CR_INSTAGRAM_TOKEN`. Instagram utilise Instagram
Login avec un compte professionnel et la version Graph choisie par
`CR_INSTAGRAM_VERSION`. Ajouter TikTok une fois le compte raccordé avec
`--plateformes youtube instagram tiktok`, `CR_TIKTOK_TOKEN` et le droit
`video.list`. Cette option de collecte n'active aucune publication TikTok.

Renouveler les jetons hors du script. Exécuter un seul collecteur à la fois,
au moins toutes les six heures. Il conserve un relevé de compteurs cumulés par
vidéo et par plateforme à **J+1, J+3, J+7, J+14 et J+30**. Chaque fenêtre dure
douze heures après l'échéance, en temps écoulé. Les échecs peuvent être
retentés dans cette fenêtre. Un relevé manqué reste absent du rapport.
Si la plateforme fournit le texte publié, le collecteur relève ses hashtags.
Sinon il garde ceux du reçu, lorsqu'ils sont connus. Les hashtags observés à
J+30 peuvent différer de ceux exposés au lancement si la légende a changé.

## Rapport et expériences

Le rapport affiche les vues médianes et le nombre de vidéos par catégorie,
hashtag, tranche de durée, carburant et musique, séparément par plateforme et par horizon. Une
même vidéo peut contribuer à plusieurs hashtags. Les écarts sont
observationnels. Le créneau, le lieu, le carburant, les autres hashtags et
la taille de l'audience peuvent influencer le résultat.

Pour tester une musique, préattribuer deux futurs épisodes comparables du même
scénario à une paire, puis générer avec `--paire-musique ID --ordre 1` et
`--paire-musique ID --ordre 2`. Publier dans des créneaux comparables et
conserver des durées, légendes, hashtags et choix de montage comparables.
Le générateur attribue le témoin et la variante à partir de la paire. Reporter
l'objet `experience` de la fiche dans le registre sans le reconstruire après
avoir vu les résultats.

Le rapport exige à J+30 au moins 30 paires non à égalité par plateforme, un
gain médian d'au moins 15 % sur le rapport des vues plus un, et un test des
signes bilatéral corrigé pour le nombre de comparaisons. Les comparaisons
gardent la plateforme, l'horizon et le scénario distincts. Figer avant les
essais la période d'analyse et les variantes. Garder les hashtags inchangés
pendant la période si leur effet doit être mesuré.

Générer avec `--decisions decisions.json --id-video ID` pour activer le choix
de piste. Le résultat doit être favorable sur YouTube et Instagram par
défaut. Lorsque TikTok fait partie de la diffusion, le périmètre peut passer
à trois avec `--plateformes-apprentissage youtube instagram tiktok`.
Environ 20 % des identifiants gardent la piste témoin. Retirer le rapport remet
les pilotes sur leur musique par défaut.

## État de l'intégration

Le workflow d'aperçu rend les pilotes à partir de captures mobiles réelles et
contrôle deux sujets du planning. Le parcours de publication et de collecte
est soumis aux tests du Worker. Son activation en production est indépendante
du workflow d'aperçu.

## Collecte programmée avec les connexions Cloudflare existantes

Le Worker de la branche importe `video/cloudflare/statistiques.mjs` et lui
confie les routes `/api/stats/`. Associer un compartiment
R2 privé dédié à la liaison `VIDEO_STATS`. Ce compartiment conserve les reçus,
les mesures et les marqueurs d'import sans durée d'expiration. Il doit rester
distinct du compartiment utilisé pour servir les vidéos. Le module réutilise
la clé du robot et les connexions sociales du profil CarburantRadar.

Après validation et mise en service du Worker, la variable GitHub
`CR_STATS_ACTIVES=true` autorise le workflow sur la branche principale.
Toutes les six heures il récupère les reçus encore disponibles du workflow
de publication, y compris en cas de publication partielle. Chaque import
abouti est marqué. Chaque relevé est enregistré une seule fois, même lors de
deux exécutions concurrentes. Les compteurs sont lus à nouveau après un
échec tant que leur fenêtre de douze heures reste ouverte. Un fichier de
reçus expiré avant son premier import devra être récupéré depuis une sauvegarde.

Pour analyser les relevés depuis un environnement disposant déjà de
`VIDEO_API_KEY`, exporter les mesures puis lancer le rapport :

```sh
python video/synchroniser_stats.py --export mesures.jsonl
python video/performance.py mesures.jsonl > decisions.json
```

Le planning quotidien dispose de son propre interrupteur `CR_PLANNING_ACTIF`
dans GitHub Actions. L’activer après le déploiement du Worker intégré et la
validation de ses liaisons privées. Chaque créneau lit le registre avant de
choisir un sujet. Une réservation identifie la catégorie, les communes et le
carburant avant l’appel de publication. Elle reste consultable après une coupure.
Les reçus confirmés sont archivés après l’envoi ou récupérés par la collecte
programmée depuis l’artefact GitHub si l’archivage immédiat échoue.

Après la collecte, la tâche enregistre un rapport privé des expériences et
des indicateurs à J+30. Le format « ville du jour » alterne entre des paires
qui testent une piste et des paires qui testent l'ajout de `#prixcarburant`.
Une paire change une seule variable. Si la légende observée ne correspond
plus à l'attribution du hashtag, la paire est écartée pour cette plateforme.
La piste peut être favorisée quand les deux plateformes actives atteignent
les seuils. Le hashtag peut être favorisé indépendamment sur chaque
plateforme qui atteint les seuils. Hors expérience, environ un épisode sur
cinq conserve la référence. Les catégories, durées et carburants figurent
dans les indicateurs descriptifs.
