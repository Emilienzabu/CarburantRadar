# CarburantRadar

**Trouve les stations-service les moins chères autour de toi, suis l'évolution des prix, et sois alerté des bonnes affaires.**

CarburantRadar est une application web progressive (PWA) gratuite qui aide les automobilistes français à ne plus payer leur carburant plus cher que nécessaire. Elle s'appuie sur les données publiques officielles du gouvernement français pour comparer en temps réel les prix pratiqués par les stations-service.

---

## 🎯 Objectif

Éviter de payer plus cher que nécessaire en repérant en quelques secondes les stations les plus avantageuses autour de soi, sur son trajet, ou dans le temps — le tout sans jamais avoir à ouvrir six onglets ou comparer des tableurs.

---

## ⛽ Fonctionnalités

### Radar (recherche autour de soi)
- Géolocalisation en un tap
- Choix du carburant : Diesel, SP95, SP98, E10, E85, GPL
- Rayon de recherche ajustable : 5, 10, 20 ou 50 km
- Classement des stations par un **score combiné** (prix + temps de trajet réel, pas juste la distance à vol d'oiseau)
- Badge "Meilleur ratio" sur la station la plus avantageuse
- Indicateur des stations ouvertes 24h/24
- Renommage personnalisé des stations (ex : "Total maison")
- Ajout aux favoris

### Carte
- Vue cartographique interactive (Leaflet / OpenStreetMap)
- Marqueurs colorés avec le prix affiché directement sur la carte
- Position de l'utilisateur et repères personnels affichés

### Trajet
- Calcule la meilleure station **sur le trajet** vers une destination donnée, pas juste autour de soi
- Arbitrage automatique entre prix et détour occasionné
- Géolocalisation automatique si besoin, sans étape bloquante
- Itinéraire complet ouvrable directement dans Google Maps

### Analyse
- Historique des prix par station ou par zone, sur 7 jours / 1 mois / 3 mois / 1 an
- Graphique interactif : zoom (pincement ou molette), déplacement, infobulle au survol avec le prix exact du jour
- Courbe de comparaison à la moyenne de la zone (discrète, en arrière-plan)
- Classement de chaque station parmi toutes celles de sa zone
- Item "Moyenne zone" dédié : période, rayon et carburant configurables indépendamment
- Plusieurs analyses peuvent être ouvertes en accordéon, chacune avec ses propres réglages

### Alertes prix
- Notifications quand une station de la zone passe sous un seuil configurable par rapport à la moyenne locale, ou atteint son meilleur prix relatif depuis plusieurs jours
- Seuil et rayon personnalisables
- Logique anti-spam : notifie sur un *changement d'état*, pas en boucle sur une station déjà connue pour être pas chère
- Web Push natif (fonctionne même app fermée), chiffré et signé selon les standards du web (RFC 8291/8292)

### Compte utilisateur
- Création de compte par email + mot de passe (mots de passe hachés, jamais stockés en clair)
- Synchronisation automatique des favoris, repères, noms personnalisés et préférences entre appareils
- Fonctionne aussi sans compte, en local uniquement sur l'appareil

### Repères personnels
- Enregistrement de positions favorites (domicile, travail...) réutilisables pour les alertes

---

## 🔒 Sécurité et confidentialité

- Toutes les entrées utilisateur et données externes sont échappées avant affichage (protection XSS)
- Mots de passe hachés avec sel aléatoire (PBKDF2, 100 000 itérations)
- Endpoints serveur protégés contre les abus (validation stricte, limite d'inscriptions, blocage des cibles réseau internes)
- Aucune donnée personnelle revendue à des tiers
- Géolocalisation utilisée uniquement avec l'autorisation explicite du navigateur
- Pages légales complètes : mentions légales, politique de confidentialité, contact

---

## 🎨 Design

- Thème sombre par défaut, cohérent sur toute l'app
- Iconographie 100% vectorielle (SVG dessinés à la main) : plus de rendu différent selon les emoji du téléphone
- Interface mobile-first, navigation par onglets en bas d'écran
- Installable sur l'écran d'accueil (PWA) avec icône dédiée

---

## 🛠️ Stack technique

| Composant | Technologie |
|---|---|
| Frontend | HTML/CSS/JS vanilla (fichier unique), aucun framework |
| Hébergement frontend | GitHub Pages |
| Backend | Cloudflare Worker (sans dépendance npm — tout en JS natif + Web Crypto API) |
| Base de données | Cloudflare KV (abonnements aux alertes, comptes utilisateurs) |
| Notifications | Web Push natif (implémentation manuelle RFC 8291/8292, sans librairie) |
| Cartographie | Leaflet.js + tuiles OpenStreetMap |
| Géocodage & itinéraires | Nominatim (OSM) et OSRM |
| Données carburant | data.economie.gouv.fr (API officielle du gouvernement français) |
| Historique des prix | Opendatasoft (public.opendatasoft.com) |
| Analytics | Google Analytics (gtag) |
| Monétisation | Google AdSense |

---

## 📊 Origine et limites des données

Les prix affichés proviennent des données publiques officielles mises à disposition par le gouvernement français, dans le cadre de l'obligation de transparence des prix imposée aux stations-service.

Deux limites à garder en tête :
- Les prix peuvent évoluer entre deux mises à jour officielles
- Les informations dépendent des déclarations transmises par chaque station elle-même

En cas de doute, vérifier l'affichage en station avant de faire le plein.

---

## 📄 Licence des données

Les données de prix des carburants sont réutilisées dans le cadre de la licence ouverte applicable aux données publiques françaises. Le code de l'application appartient à son auteur.

---

*CarburantRadar — développé par Emilien Zabukovec*
