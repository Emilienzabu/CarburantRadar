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

Le registre d'entrée du collecteur est un tableau JSON de ces lignes. Il faut
archiver les reçus dans un stockage persistant et les réunir dans ce registre.
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
hashtag et tranche de durée, séparément par plateforme et par horizon. Une
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
les pilotes sur leur musique par défaut. Les statistiques de hashtags et de
durée sont exploitées dans le rapport. Seul le choix de musique peut
actuellement modifier le rendu.

## État de l'intégration

Le workflow d'aperçu prépare les deux pilotes et leurs fiches. Le planificateur
éditorial sélectionne les sujets à partir d'un historique fourni. Le raccord
au planning quotidien, l'archivage des reçus, les accès statistiques réels et
l'exécution planifiée de la collecte restent à valider avant activation.
