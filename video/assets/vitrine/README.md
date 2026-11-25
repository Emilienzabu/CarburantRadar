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

## Captures mobiles automatisées

Depuis la racine du dépôt, avec Python 3.12 et FFmpeg (dont ffprobe) dans le PATH :

```sh
pip install -r video/requirements.txt playwright==1.65.2 edge-tts==7.3.1
python -m playwright install chromium
python video/capture_vitrine.py --sortie video/sortie/captures
python video/generate_video.py --format vitrine --captures-mobiles video/sortie/captures --sortie video/sortie/apercu-vitrine.mp4
```

Le navigateur émule un Pixel 7 et prend ses captures sur carburantradar.fr.
Le scénario invité présente le Radar à Marseille, un Trajet vers Aix-en-Provence,
l’Analyse sur trois mois et la Carte. Les quatre captures et leur date sont
conservées ensemble. L'absence de prix, de résultat de trajet, de graphique ou
de fond de carte fait échouer la capture. Le calcul du coût aller-retour du
Radar peut encore être en cours lorsque ses prix sont disponibles.

Le montage conserve les écrans complets et leurs valeurs. Il anime les
transitions entre les captures. Le workflow **Aperçu vitrine mobile** se lance
sur la branche de validation lors d'un changement du générateur ou du workflow.
Il fournit le MP4, les captures et les journaux en artefact.
