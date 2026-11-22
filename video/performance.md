# Apprentissage à partir des vidéos publiées

Chaque pilote écrit une fiche `.creation.json` avec son scénario, sa catégorie,
son identité graphique, sa durée, la voix, la musique et l'empreinte du MP4.
L'identifiant interne est fourni par `--id-video`.

## Collecte

Le registre d'entrée est un tableau JSON. Une ligne associe la fiche de création
à un identifiant externe `video_id`, une `plateforme` (youtube, instagram ou
tiktok), un horodatage `publie_le` avec fuseau et un indicateur `organique`.
Le même rendu peut avoir trois lignes, une par plateforme. Une vidéo sponsorisée
doit avoir `organique: false`.

```sh
python video/collecte_stats.py publications.json mesures.jsonl
python video/performance.py mesures.jsonl > decisions.json
```

Le collecteur utilise les jetons d'accès `CR_YOUTUBE_TOKEN`,
`CR_INSTAGRAM_TOKEN` et `CR_TIKTOK_TOKEN`. Instagram utilise Instagram Login
avec un compte professionnel et la version Graph choisie par
`CR_INSTAGRAM_VERSION`. TikTok utilise Display API et le droit `video.list`.
Les jetons doivent être renouvelés hors du script. Exécuter un seul collecteur
à la fois, au moins toutes les six heures, avec un registre et un fichier
de mesures persistants. Une mesure déjà enregistrée est conservée. Les lectures
échouées peuvent être retentées avant la fin de la fenêtre. La fenêtre est
de 168 à moins de 180 heures après publication. Une observation manquante
reste absente du rapport.

Le rapport compare les vues médianes par catégorie et plateforme avec leur
effectif. Ces différences sont observationnelles. Le calendrier, le lieu,
le carburant ou la taille de l'audience peuvent influencer le résultat.
La rétention n'est pas comparée entre plateformes dans cette première version.

## Expériences qui modifient le rendu

Pour tester une musique, préattribuer deux futurs épisodes comparables du même
scénario à une paire, puis générer avec `--paire-musique ID --ordre 1` et
`--paire-musique ID --ordre 2`. Publier dans des créneaux comparables et conserver
les mêmes règles de montage et de diffusion. Ne pas republier la même vidéo.
Le générateur attribue le témoin et la variante à partir de la paire. Reporter
l'objet `experience` de la fiche dans le registre sans le reconstruire après
avoir vu les résultats.

Le rapport exige au moins 30 paires non à égalité par plateforme, un gain
médian d'au moins 15 % sur le rapport des vues plus un, et un test des signes
bilatéral corrigé pour le nombre de comparaisons. Les comparaisons ne
mélangent ni les plateformes ni les scénarios. Ce seuil est une règle de départ.
Pour une décision plus fiable, figer avant les essais la durée de collecte et
les variantes testées, puis analyser à la fin de la période. Les observations
répétées pendant la collecte ne sont pas un critère d'arrêt.

Générer avec `--decisions decisions.json --id-video ID` pour activer le choix
de piste. Il faut une décision favorable sur les trois plateformes pour
changer la musique d'un scénario. Environ 20 % des identifiants gardent le
témoin. Les quotas, le choix des villes et la rotation des carburants ne sont
pas modifiés par ces résultats. Retirer le rapport remet les pilotes sur
leur musique par défaut.

## État de l'intégration

Le workflow d'aperçu prépare les deux pilotes et leurs fiches. Le planificateur
éditorial sélectionne des candidats pour les six catégories à partir d'un
historique fourni. Il n'est pas encore le planificateur de publication.
Le registre externe, les comptes autorisés, la tâche de collecte et le stockage
persistant restent à configurer avant une recette avec des publications réelles.
Le générateur applique actuellement les résultats aux musiques des deux pilotes.
