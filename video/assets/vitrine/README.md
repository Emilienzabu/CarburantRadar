# Écrans du format « vitrine »

Quatre captures recadrées de l'application, attendues ici par `video/vitrine.py` :

| Fichier | Contenu |
|---|---|
| `ecran_radar.png` | écran Radar (liste de stations) |
| `ecran_trajet.png` | écran Trajet |
| `ecran_analyse.png` | écran Analyse (évolution des prix) |
| `ecran_carte.png` | écran Carte |

Chaque fichier fait **592 × 1132** (recadrage de l'intérieur de l'écran, sous l'en-tête). Ils se produisent à partir des
quatre plans composés 1080 × 1920 avec :

    python video/preparer_ecrans.py DOSSIER_DES_PLANS

Le script ne modifie aucune valeur et n'agrandit rien. Il retire l'en-tête (redessiné au rendu avec l'icône réelle de
l'application) et la bande sous la barre d'onglets, où un fragment de nom de station favorite dépassait.

**Données personnelles** : ces images sont publiques dès qu'elles sont commitées (dépôt public). Elles montrent des valeurs
de démonstration (pas des prix du jour) ; vérifier avant commit qu'aucun nom de lieu ou de compte n'y figure.

Sans ces quatre fichiers, `generate_video.py --format vitrine` s'arrête avec un message explicite ; les autres formats ne
sont pas concernés.
