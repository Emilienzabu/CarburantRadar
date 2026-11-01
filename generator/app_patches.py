"""Correctifs appliqués aux applications (france/, espagne/, italie/ index.html) au moment du déploiement.

Pourquoi ici : les trois index.html font ~177 Ko chacun et contiennent la même logique. Les fonctionnalités ajoutées vivent dans de vrais
fichiers testables (generator/app_vehicles.js) ; ce module les injecte dans la copie déployée de chaque application et branche les
quelques points d'accroche nécessaires par remplacement de texte exact. Aucun index.html du dépôt n'est modifié ni commité.

Règles de sécurité :
- tout ou rien par application : si un des points d'accroche n'est pas retrouvé exactement une fois (le code a changé), AUCUNE
  modification n'est faite pour cette application et le rapport SEO_REPORT.md le signale ;
- si la fonctionnalité est déjà intégrée directement dans le fichier (marqueur MARK présent), rien n'est fait : on peut donc un jour
  copier ce code dans les index.html puis supprimer ce module.

Fonctionnalité actuelle : véhicules (nom, réservoir, consommation, carburant, véhicule par défaut) et classement des stations par
coût total (plein + trajet), pour le Radar et le mode Trajet. Voir app_vehicles.js pour la formule.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "crVehiclesCard"   # présent dès que la fonctionnalité est intégrée

# Textes d'aide « À propos des économies » (un par langue) : ancien texte -> nouveau texte
ABOUT = {
    "france": (
        "Les économies affichées représentent la différence entre le prix de la station sélectionnée et la moyenne régionale du même carburant, multipliée par la quantité que vous seriez susceptible d'acheter (basée sur votre réservoir et consommation).",
        "Les stations sont classées par coût total : le plein (80 % du réservoir × prix de la station) plus le carburant brûlé pour l'aller-retour (distance × consommation × prix de la station). Plus votre véhicule consomme, ou plus son réservoir est petit, plus la distance compte face au prix.",
    ),
    "espagne": (
        "El ahorro mostrado representa la diferencia entre el precio de la estación seleccionada y la media regional del mismo combustible, multiplicada por la cantidad que probablemente comprarías (según tu depósito y consumo).",
        "Las estaciones se ordenan por coste total: el repostaje (80 % del depósito × precio de la estación) más el combustible gastado en el trayecto de ida y vuelta (distancia × consumo × precio de la estación). Cuanto más consume tu vehículo, o más pequeño es su depósito, más pesa la distancia frente al precio.",
    ),
    "italie": (
        "Il risparmio mostrato rappresenta la differenza tra il prezzo del distributore selezionato e la media regionale dello stesso carburante, moltiplicata per la quantità che probabilmente acquisteresti (in base al tuo serbatoio e consumo).",
        "I distributori sono ordinati per costo totale: il pieno (80 % del serbatoio × prezzo del distributore) più il carburante consumato per l'andata e ritorno (distanza × consumo × prezzo del distributore). Più il tuo veicolo consuma, o più il serbatoio è piccolo, più la distanza pesa rispetto al prezzo.",
    ),
}

# (nom, type, ancien, nouveau). type : "texte" (remplacement exact) ou "regex" (DOTALL). Chaque ancien doit être trouvé EXACTEMENT une fois.
COMMON_OPS = [
    ("carte véhicule (Personnalisation)", "regex",
     r'    <!-- Vehicle Configuration -->\n    <div class="side-item">.*?id="vehicleConfigStatus"[^>]*></div>\n    </div>\n',
     '    <!-- Véhicules (generator/app_vehicles.js) -->\n    <div class="side-item" id="crVehiclesCard"></div>\n'),
    ("sélecteur de véhicule du Radar", "texte",
     '<div class="fuels" id="fg">',
     '<div id="crVehicleBar" class="cr-vbar"></div>\n      <div class="fuels" id="fg">'),
    ("initialisation des anciens champs", "texte",
     "  if (tankSize) document.getElementById('tankSize').value = tankSize;\n  if (consumption) document.getElementById('consumption').value = consumption;",
     "  if (window.crRenderVehicles) crRenderVehicles();"),
    ("sélecteur de véhicule du Trajet", "regex",
     r'id="page-trajet">.*?margin-bottom:16px">[^<]*</div>\n',
     '{{MATCH}}    <div id="crVehicleBar2" class="cr-vbar"></div>\n'),
    ("stations dont on calcule la route", "texte",
     "var top10=st.filter(function(s){return s.prix>0;}).sort(function(a,b){return a.prix-b.prix;}).slice(0,10);",
     "var top10=crPickCandidates(st);"),
    ("classement du Radar", "regex",
     r"  var ts=wp\.map\(.*?  var all=sc2\.concat\(np\);\n",
     "  var all=crRankStations(wp);\n"),
    ("libellé du rang", "regex",
     r"\(s\.score!==null\?' - [^']+ '\+s\.score\+'/100':''\)",
     "(s.score!==null?' - '+crRankLabel(s):'')"),
    ("bloc de chaque carte", "regex",
     r"      \(savingsEUR !== null \?\n.*?      \(s\.score!==null\?'<div class=\"bar\"><div class=\"fill\" style=\"width:'\+s\.score\+'%\"></div></div>':''\)\+\n",
     "      crCardBlocks(s)+\n"),
    ("changement de carburant : recharger les prix", "texte",
     "localStorage.setItem('cr_fu',fu);if(st.length)render();synchroniserVersServeur();}",
     "localStorage.setItem('cr_fu',fu);if(la!==null)load();else if(st.length)render();synchroniserVersServeur();}"),
    ("synchronisation : envoi", "texte",
     "prefs:{fu:fu,ra:ra}};}",
     "prefs:{fu:fu,ra:ra,vehicles:crGetVehicles(),vehicleDefault:crGetDefaultId()}};}"),
    ("synchronisation : réception", "texte",
     "    if(d.prefs.ra){ra=d.prefs.ra;localStorage.setItem('cr_ra',ra);}\n",
     "    if(d.prefs.ra){ra=d.prefs.ra;localStorage.setItem('cr_ra',ra);}\n    if(d.prefs.vehicles){crApplyServer(d.prefs.vehicles,d.prefs.vehicleDefault);}\n"),
    ("synchronisation : rafraîchissement", "texte",
     "function rafraichirApresSync(){\n  renderFavList();renderRepList();",
     "function rafraichirApresSync(){\n  renderFavList();renderRepList();crRenderVehicles();"),
    ("Trajet : distance directe", "texte",
     "var dureeDirecte=route.routes[0].duration;",
     "var dureeDirecte=route.routes[0].duration;var distDirecte=route.routes[0].distance;"),
    ("Trajet : présélection des stations", "texte",
     "stations.sort(function(a,b){return a.prix-b.prix;});",
     "crTrajetPreSort(stations,la,lo,dLat,dLon);"),
    ("Trajet : détour en km", "texte",
     "s.dureeAvec=data.routes[0].duration;s.detour=s.dureeAvec-dureeDirecte;return s;",
     "s.dureeAvec=data.routes[0].duration;s.detour=s.dureeAvec-dureeDirecte;s.detourKm=(data.routes[0].distance-distDirecte)/1000;return s;"),
    ("Trajet : échec du calcul de détour", "texte",
     "s.dureeAvec=null;s.detour=null;return s;",
     "s.dureeAvec=null;s.detour=null;s.detourKm=null;return s;"),
    ("Trajet : classement", "regex",
     r"      var mnP=Math\.min\.apply\(null,avecDetour\.map\(.*?      avecDetour\.sort\(function\(a,b\)\{return b\.score-a\.score;\}\);\n",
     "      crTrajetRank(avecDetour);\n"),
]


def _script():
    with open(os.path.join(HERE, "app_vehicles.js"), encoding="utf-8") as f:
        return f.read()


def _operations(pays):
    old, new = ABOUT[pays]
    return COMMON_OPS + [("texte d'aide", "texte", old, new)]


def _count(kind, pattern, text):
    return len(re.findall(pattern, text, re.S)) if kind == "regex" else text.count(pattern)


def patch_text(pays, text):
    """-> (nouveau texte | None, statut). Tout ou rien."""
    if MARK in text:
        return None, "déjà intégré dans le fichier"
    ops = _operations(pays)
    missing = []
    for nom, kind, old, new in ops:
        n = _count(kind, old, text)
        if n != 1:
            missing.append(nom + (" (introuvable)" if n == 0 else f" (présent {n} fois)"))
    if text.count("</body>") < 1:
        missing.append("balise </body> (introuvable)")
    if missing:
        return None, "NON appliqué, texte du code modifié : " + ", ".join(missing)
    for nom, kind, old, new in ops:
        if kind == "regex":
            text = re.sub(old, lambda m, new=new: new.replace("{{MATCH}}", m.group(0)), text, count=1, flags=re.S)
        else:
            text = text.replace(old, new, 1)
    i = text.rindex("</body>")
    text = text[:i] + "<script>\n" + _script() + "</script>\n" + text[i:]
    return text, "appliqué"


def apply(root):
    """Applique la fonctionnalité aux 3 applications présentes dans `root`. -> {pays: statut}"""
    out = {}
    for pays in ABOUT:
        p = os.path.join(root, pays, "index.html")
        if not os.path.isfile(p):
            out[pays] = "fichier absent"
            continue
        with open(p, encoding="utf-8", newline="") as f:   # newline="" : ne touche pas aux fins de ligne du fichier
            text = f.read()
        new, statut = patch_text(pays, text)
        if new is not None:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        out[pays] = statut
    return out
