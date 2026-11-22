# Catalogue des animations CarburantRadar

Les fonctions de `video/animations.py` dessinent sur un calque RGBA transparent. Le montage décide du fond, des captures, des textes et de la composition. Les positions et dimensions sont exprimées en pixels dans une vidéo verticale de 1080 × 1920. La fonction `progression` transforme un temps, un début et une durée en progression de 0 à 1.

| Animation | Paramètres | Exemple |
| --- | --- | --- |
| `tracer` | Points, couleur, largeur et progression | Trajet direct ou passage par une station |
| `epingle` | Position, taille et progression | Indiquer la station sur la carte |
| `tap` | Position et progression | Indiquer où appuyer dans une capture |
| `surligner` | Rectangle et progression | Mettre en évidence un prix ou un bouton |
| `zone` | Centre, rayon et progression | Illustrer une zone de recherche |
| `reveler` | Position, texte, police, couleur et progression | Faire apparaître un écart ou un résultat |

## Générer les pilotes

Avec les dépendances vidéo et FFmpeg installés, générer d'abord les captures via `video/capture_vitrine.py`, puis appeler le rendu depuis la racine du dépôt.

```sh
python video/pilotes_beige.py detour --captures-mobiles video/sortie/captures --sortie video/sortie/pilote-detour.mp4
python video/pilotes_beige.py rayon --captures-mobiles video/sortie/captures --sortie video/sortie/pilote-rayon.mp4
```

La commande utilise Remy par défaut. L'option `--voix-locale` sert aux essais avec eSpeak NG. Le pilote Radar illustre le tap sur une capture d'écran et la portée du rayon dans un schéma. Les tracés du pilote Détour sont illustratifs. Le dernier plan montre un résultat capturé dans l'application.

Un workflow GitHub Actions peut appeler ces mêmes commandes après sa propre étape de capture. Le rendu crée uniquement un fichier MP4 local.
