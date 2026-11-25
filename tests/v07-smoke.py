import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


SITE = "http://localhost:8765/france/"
HTML = Path(sys.argv[1]).read_bytes()
SECTIONS = ("Compte", "Lieux et favoris", "Véhicules et réglages", "Alertes prix", "Aide et informations")


def tester(browser, profil, reglages):
    with browser.new_context(**reglages, locale="fr-FR", service_workers="block") as context:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", lambda route: route.fulfill(body=HTML, content_type="text/html; charset=utf-8")
                   if route.request.url == SITE else route.abort())
        dialogues = []
        page.on("dialog", lambda dialog: (dialogues.append(dialog.message), dialog.dismiss()))
        page.goto(SITE)
        expect(page.locator("#splash")).to_be_hidden()
        expect(page.locator("#onboardingModal.on")).to_be_visible()
        page.locator("#onboardingModal").get_by_role("button", name="J'ai déjà un compte").click()
        menu = page.locator("#sideMenu")
        main = menu.locator("#crV07Main")
        detail = menu.locator("#crV07Detail")
        titre = menu.locator("#crV07Title")
        expect(titre).to_have_text("Compte")
        expect(detail.locator("#compteEmail")).to_be_visible()
        page.locator("#crV07Close").click()
        page.locator(".menu-btn").click()
        expect(titre).to_have_text("Menu")

        for section in SECTIONS:
            main.get_by_role("button", name=section, exact=False).click()
            expect(titre).to_have_text(section)
            page.locator("#crV07Back").click()
            expect(titre).to_have_text("Menu")

        main.get_by_role("button", name="Alertes prix").click()
        page.evaluate("""() => {
            la = 48.853; lo = 2.349;
            setLs('cr_alert_key', 'fixture');
            setLs('cr_alert_info', {carburant: 'SP98', rayon: 20, seuil: 8, lat: la, lon: lo});
            updateAlertUI();
        }""")
        detail.get_by_role("button", name="Configurer les alertes").click()
        expect(page.locator("#alertModal.on")).to_be_visible()
        expect(page.locator("#alertLoc")).to_have_value("current")
        assert page.locator("#alertSeuil option").evaluate_all("n => n.map(o => o.value)") == ["2", "3", "5", "8"]
        expect(page.locator("#crV07AlertValue")).to_have_text("8 %")
        expect(page.locator("#alertRayon")).to_have_value("20")
        page.locator("#crV07AlertRange").fill("0")
        expect(page.locator("#alertSeuil")).to_have_value("2")
        expect(page.locator("#crV07AlertValue")).to_have_text("2 %")
        page.locator("#alertModal").get_by_role("button", name="Annuler").click()
        expect(page.locator("#alertToggle")).to_be_checked()
        page.locator("#crV07Close").click()
        page.locator(".menu-btn").click()
        expect(titre).to_have_text("Menu")
        expect(main.get_by_role("button", name="Alertes prix")).to_be_visible()
        page.locator("#crV07Close").click()
        assert page.evaluate("TUTO_ETAPES.length") == 13
        assert not dialogues, dialogues
        assert not errors, errors
        print(f"{profil} : parcours compte, cinq rubriques du menu, réouverture et formulaire alertes validés")


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel=os.environ.get("V07_BROWSER") or None, headless=True)
    tester(browser, "Pixel 7 émulé", pw.devices["Pixel 7"])
    tester(browser, "iPhone 13 émulé dans Chromium", pw.devices["iPhone 13"])
    tester(browser, "Chromium bureau", {"viewport": {"width": 1280, "height": 900}})
    browser.close()
