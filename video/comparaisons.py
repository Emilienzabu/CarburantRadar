"""Contrats de prix à partir des instantanés quotidiens de CarburantRadar."""
from datetime import date
from math import isfinite


def comparer(historique, carburant, gauche, droite, indicateur="minimum"):
    """Gauche et droite sont des couples (slug, jour ISO)."""
    if not carburant or indicateur not in {"minimum", "moyenne"}:
        raise ValueError("Carburant et indicateur explicites requis")
    ville_a, jour_a = gauche
    ville_b, jour_b = droite
    dates = date.fromisoformat(jour_a), date.fromisoformat(jour_b)
    if ville_a == ville_b and dates[0] < dates[1]:
        categorie = "ville_avant_maintenant"
    elif ville_a != ville_b and dates[0] == dates[1]:
        categorie = "ville_contre_ville"
    else:
        raise ValueError("Même commune à deux dates, ou deux communes à la même date")

    lignes = []
    for ville, jour in (gauche, droite):
        row = historique["days"].get(jour, {}).get(ville, {}).get(carburant)
        if not row:
            raise ValueError(f"Relevé absent pour {ville} le {jour}")
        portee, stations, moyenne, minimum = row
        if portee != "c" or stations < 2:
            raise ValueError(f"Couverture communale insuffisante pour {ville} le {jour}")
        prix = minimum if indicateur == "minimum" else moyenne
        if not isfinite(prix) or prix <= 0:
            raise ValueError(f"Prix invalide pour {ville} le {jour}")
        lignes.append(dict(ville=ville, date=jour, stations=stations, prix=prix))
    return dict(categorie=categorie, carburant=carburant, indicateur=indicateur,
                valeurs=lignes, ecart=round(lignes[1]["prix"] - lignes[0]["prix"], 3))
