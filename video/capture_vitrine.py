"""Capture les quatre écrans de la vitrine dans le site mobile."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import TimeoutError as PlaywrightTimeout, expect, sync_playwright

SITE = "https://carburantradar.fr/france/"
ATTENTE = 90_000


def accueil(page):
    page.locator("#splash").wait_for(state="hidden")
    invite = page.get_by_role("button", name="Continuer sans compte", exact=True)
    invite.tap()
    passer = page.get_by_role("button", name="Passer le tutoriel", exact=True)
    try:
        passer.wait_for(state="visible", timeout=3500)
    except PlaywrightTimeout:
        pass
    else:
        passer.tap()
    expect(page.locator("#onboardingModal, #tutoModal, #crGuide").filter(visible=True)).to_have_count(0)


def capture(page, dossier, nom):
    page.wait_for_function("document.fonts.status === 'loaded'")
    page.screenshot(path=dossier / f"ecran_{nom}.png", animations="disabled")
    print(f"Capture {nom} enregistrée", flush=True)


def parcourir(page, dossier):
    page.goto(SITE, wait_until="load", timeout=ATTENTE)
    if page.url.rstrip("/") != SITE.rstrip("/"):
        raise RuntimeError(f"Destination inattendue : {page.url}")
    accueil(page)
    localisation = page.locator("#locBtn")
    localisation.tap()
    expect(localisation).to_be_enabled(timeout=35_000)
    if "Localisation trop longue" in page.locator("#status").inner_text():
        localisation.tap()
    expect(page.locator("#page-radar #sc")).to_have_text(re.compile(r"^[1-9]\d*$"), timeout=ATTENTE)
    try:
        page.locator("#page-radar .card.best .mv.s").first.wait_for(state="visible", timeout=20_000)
    except PlaywrightTimeout:
        print("Radar : prix chargés, calcul des coûts encore indisponible.", flush=True)
    capture(page, dossier, "radar")

    page.locator("#nav-trajet").tap()
    page.locator("#trajetDest").fill("Aix-en-Provence")
    page.locator("#trajetBtn").tap()
    resultat = page.locator("#trajetResult .metrics")
    expect(resultat).to_be_visible(timeout=ATTENTE)
    resultat.scroll_into_view_if_needed()
    capture(page, dossier, "trajet")

    page.locator("#nav-analyse").tap()
    page.locator("#analyseList .fav-analyse-btn").first.tap()
    page.get_by_role("button", name="3 mois", exact=True).tap()
    graphique = page.locator("#analyseGraph")
    expect(graphique).to_be_visible(timeout=ATTENTE)
    graphique.scroll_into_view_if_needed()
    capture(page, dossier, "analyse")

    page.locator("#nav-map").tap()
    expect(page.locator("#map .leaflet-marker-icon").nth(1)).to_be_visible(timeout=ATTENTE)
    page.wait_for_function(
        """() => {
            const tiles = [...document.querySelectorAll('#map .leaflet-tile')];
            return tiles.length > 0 && tiles.every(t => t.complete && t.naturalWidth > 0);
        }""",
        timeout=ATTENTE,
    )
    capture(page, dossier, "carte")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--canal", choices=["msedge", "chrome"])
    args = parser.parse_args()
    if args.sortie.exists():
        parser.error("--sortie doit désigner un nouveau dossier")
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.sortie.parent) as tmp, sync_playwright() as pw:
        dossier = Path(tmp) / "captures"
        dossier.mkdir()
        browser = pw.chromium.launch(channel=args.canal)
        try:
            context = browser.new_context(
                **pw.devices["Pixel 7"], locale="fr-FR", timezone_id="Europe/Paris",
                geolocation={"latitude": 43.2965, "longitude": 5.3698, "accuracy": 20},
                permissions=["geolocation"], service_workers="block",
            )
            # La navigation reste publique et les visites de capture ne sont pas comptabilisées.
            context.route("**/track", lambda route: route.fulfill(status=204))
            page = context.new_page()
            parcourir(page, dossier)
            (dossier / "capture.json").write_text(json.dumps({
                "url": page.url, "capture_utc": datetime.now(timezone.utc).isoformat(),
                "appareil": "Pixel 7", "depart": "Marseille", "destination": "Aix-en-Provence",
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            browser.close()
        dossier.rename(args.sortie)


if __name__ == "__main__":
    main()
