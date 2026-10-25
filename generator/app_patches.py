"""Correctifs appliqués aux applications (france/, espagne/, italie/ index.html) au moment du déploiement.

Pourquoi ici : les trois index.html font ~177 Ko chacun et contiennent la même logique ; un correctif de quelques lignes y est appliqué
par remplacement de texte exact, une seule fois par build, sur la copie qui est déployée. Aucun fichier n'est commité.

Règles de sécurité :
- tout ou rien par application : si un des morceaux de texte n'est pas retrouvé (le code a changé), AUCUNE modification n'est faite
  pour cette application et le rapport SEO_REPORT.md le signale ;
- si le correctif est déjà intégré directement dans le fichier (marqueur MARK présent), rien n'est fait : on peut donc un jour
  copier le code ci-dessous dans les index.html puis supprimer ce module.

Correctif actuel : « économie estimée » NETTE du trajet jusqu'à la station (voir CALC_NEW).
"""
import os

MARK = "savingsGross"   # présent dans le code dès que le correctif est intégré

CALC_OLD = """    // Calculate savings vs average price
    var savingsEUR = null;
    var savingsPercent = null;
    if (s.prix && avgPrice) {
      var priceDiff = avgPrice - s.prix; // Positive if station is cheaper than average
      savingsEUR = priceDiff * fillQuantity;
      savingsPercent = (priceDiff / avgPrice) * 100;
    }
"""

CALC_NEW = """    // Économie NETTE vs moyenne : (moyenne - prix) x plein, moins le carburant brûlé pour l'aller-retour jusqu'à la station
    // (distance par la route si connue, sinon à vol d'oiseau ; consommation des réglages ; valorisé au prix moyen)
    var savingsEUR = null;
    var savingsPercent = null;
    var savingsGross = null;
    var detourKm = 0;
    var detourEUR = 0;
    if (s.prix && avgPrice) {
      savingsGross = (avgPrice - s.prix) * fillQuantity;
      detourKm = (typeof s.distRoute === 'number') ? s.distRoute / 1000 : (s.distance || 0);
      detourEUR = 2 * detourKm * consumption / 100 * avgPrice;
      savingsEUR = savingsGross - detourEUR;
      savingsPercent = (savingsEUR / (avgPrice * fillQuantity)) * 100;
    }
"""

MV_LINE = """            '<div class="mv" style="color:'+(savingsEUR >= 0 ? 'var(--success)' : 'var(--danger)')+'">'+(savingsEUR >= 0 ? '+' : '')+savingsEUR.toFixed(2)+' € ('+(savingsPercent >= 0 ? '+' : '')+savingsPercent.toFixed(1)+'%)</div>'+
"""


def detail_line(brut, trajet, defaut):
    return ("            '<div style=\"font-size:11px;color:var(--text-muted);margin-top:4px;\">" + brut + " '+(savingsGross >= 0 ? '+' : '')+savingsGross.toFixed(2)+' € · "
            + trajet + " '+detourKm.toFixed(1)+' km −'+detourEUR.toFixed(2)+' €'+(localStorage.getItem('cr_consumption') ? '' : ' (" + defaut
            + " '+consumption.toFixed(1)+' L/100 km)')+'</div>'+\n")


LANGS = {
    "france": {
        "label_old": "'Économie estimée vs moyenne' : 'Surcoût estimé vs moyenne'",
        "label_new": "'Économie nette estimée vs moyenne' : 'Surcoût net estimé vs moyenne'",
        "detail": detail_line("Brut", "trajet A/R", "conso par défaut"),
        "about_old": "Les économies affichées représentent la différence entre le prix de la station sélectionnée et la moyenne régionale du même carburant, multipliée par la quantité que vous seriez susceptible d'acheter (basée sur votre réservoir et consommation).",
        "about_new": "L'économie affichée est nette : (moyenne de la zone − prix de la station) × la quantité d'un plein (75 % de votre réservoir), moins le carburant consommé pour aller à la station et en revenir (distance × votre consommation × prix moyen). Plus la station est loin, plus l'économie diminue, jusqu'à devenir un surcoût.",
    },
    "espagne": {
        "label_old": "'Ahorro estimado vs media' : 'Sobrecoste estimado vs media'",
        "label_new": "'Ahorro neto estimado vs media' : 'Sobrecoste neto estimado vs media'",
        "detail": detail_line("Bruto", "trayecto I/V", "consumo por defecto"),
        "about_old": "El ahorro mostrado representa la diferencia entre el precio de la estación seleccionada y la media regional del mismo combustible, multiplicada por la cantidad que probablemente comprarías (según tu depósito y consumo).",
        "about_new": "El ahorro mostrado es neto: (media de la zona − precio de la estación) × la cantidad de un repostaje (75 % de tu depósito), menos el combustible gastado para ir a la estación y volver (distancia × tu consumo × precio medio). Cuanto más lejos está la estación, menor es el ahorro, hasta convertirse en sobrecoste.",
    },
    "italie": {
        "label_old": "'Risparmio stimato vs media' : 'Sovrapprezzo stimato vs media'",
        "label_new": "'Risparmio netto stimato vs media' : 'Sovrapprezzo netto stimato vs media'",
        "detail": detail_line("Lordo", "tragitto A/R", "consumo predefinito"),
        "about_old": "Il risparmio mostrato rappresenta la differenza tra il prezzo del distributore selezionato e la media regionale dello stesso carburante, moltiplicata per la quantità che probabilmente acquisteresti (in base al tuo serbatoio e consumo).",
        "about_new": "Il risparmio mostrato è netto: (media della zona − prezzo del distributore) × la quantità di un pieno (75 % del tuo serbatoio), meno il carburante consumato per andare al distributore e tornare (distanza × il tuo consumo × prezzo medio). Più il distributore è lontano, più il risparmio diminuisce, fino a diventare un sovrapprezzo.",
    },
}


def _operations(pays):
    t = LANGS[pays]
    return [
        ("calcul de l'économie", CALC_OLD, CALC_NEW),
        ("libellé", t["label_old"], t["label_new"]),
        ("détail brut / trajet", MV_LINE, MV_LINE + t["detail"]),
        ("texte d'aide", t["about_old"], t["about_new"]),
    ]


def patch_text(pays, text):
    """-> (nouveau texte | None, statut). Tout ou rien."""
    if MARK in text:
        return None, "déjà intégré dans le fichier"
    missing = []
    for nom, old, new in _operations(pays):
        n = text.count(old)
        if n != 1:
            missing.append(nom + (" (introuvable)" if n == 0 else f" (présent {n} fois)"))
    if missing:
        return None, "NON appliqué, texte du code modifié : " + ", ".join(missing)
    for nom, old, new in _operations(pays):
        text = text.replace(old, new, 1)
    return text, "appliqué"


def apply(root):
    """Applique le correctif aux 3 applications présentes dans `root`. -> {pays: statut}"""
    out = {}
    for pays in LANGS:
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
