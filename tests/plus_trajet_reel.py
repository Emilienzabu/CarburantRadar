from os import environ
from pathlib import Path
from re import compile as pattern
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


ORIGIN = environ.get("PLUS_TRAJET_ORIGIN", "http://127.0.0.1:8789")
PASSWORD = environ["PLUS_TRAJET_PASSWORD"]
PARIS = {"latitude": 48.8566, "longitude": 2.3522}


def comparison_state(context, token):
    response = context.request.post(ORIGIN + "/plus/status", data={},
                                    headers={"Authorization": f"Bearer {token}"})
    assert response.ok, response.text()
    return response.json()


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    devices = {
        "smartphone": {**pw.devices["Pixel 7"]},
        "tablette": {**pw.devices["iPad Mini"]},
        "pc": {"viewport": {"width": 1440, "height": 900}},
    }
    for label, device in devices.items():
        context = browser.new_context(**device, locale="fr-FR", service_workers="block", geolocation=PARIS)
        email = f"trajet-{uuid4().hex[:10]}@carburantradar.invalid"
        login = context.request.post(ORIGIN + "/login", data={"email": email, "password": PASSWORD})
        assert login.ok, login.text()
        token = login.json()["token"]
        context.add_init_script(f"""
          localStorage.setItem('cr_onboarding_vu', 'true');
          localStorage.setItem('cr_tuto_vu', 'true');
          localStorage.setItem('cr_account_token', '{token}');
          localStorage.setItem('cr_account_email', '{email}');
        """)
        page = context.new_page()
        page.on("response", lambda response: print("Source HTTP", response.status,
                response.url.split("?")[0], flush=True)
                if response.status >= 400 and (
                    response.url.startswith("https://data.geopf.fr/") or
                    response.url.startswith(ORIGIN + "/?") or response.url == ORIGIN + "/plus/trip") else None)
        page.goto(ORIGIN + "/france/", wait_until="domcontentloaded")
        page.locator("#nav-trajet").click()
        manual = page.get_by_role("radio", name="Saisir une adresse")
        gps = page.get_by_role("radio", name="Ma position")
        departure = page.get_by_label("Adresse ou ville de départ")
        arrive = page.get_by_label("Destination", exact=True)
        search = page.get_by_role("button", name="Trouver la meilleure station")
        result = page.locator("#trajetResult")
        before = comparison_state(context, token)
        assert before["credits"] == 5 and not before["plus"]["active"]

        expect(gps).to_be_checked()
        expect(departure).to_be_hidden()
        # Permissions are granted only after verifying the manual route.
        manual.check()
        departure.fill("10 rue de Paris 94300 Vincennes")
        arrive.fill("Paris 75004")
        page.get_by_role("option", name="Paris", exact=True).first.click(timeout=12000)
        search.click()
        expect(result.locator(".card.best")).to_be_visible(timeout=70000)
        manual_origin = page.evaluate("window.crTripVerifiedMeta.origin")
        assert 2.40 < manual_origin["lon"] < 2.48 and 48.80 < manual_origin["lat"] < 48.90
        assert comparison_state(context, token)["credits"] == 5
        compare = page.get_by_role("button", name="Comparer les autres stations · 1 crédit")
        expect(compare).to_be_visible()
        with page.expect_response(lambda response: response.url == ORIGIN + "/plus/trip", timeout=55000) as call:
            compare.click()
        response = call.value
        assert response.ok, response.text()
        comparison = response.json()
        assert comparison["credits"] == 4 and comparison["result"]["verified"] >= 2
        assert call.value.request.post_data_json["params"]["origin"] == {
            "lat": manual_origin["lat"], "lon": manual_origin["lon"]}
        expect(result.get_by_role("heading", name=pattern(r"Comparaison de \d+ stations vérifiées"))).to_be_visible()
        cards = result.get_by_role("article")
        assert cards.count() >= 2
        recommended = result.locator(".cr-trip-compare-card.recommended")
        expect(recommended.get_by_text("Meilleur coût total", exact=False)).to_be_visible()
        for metric in ("Prix au litre", "Distance en plus", "Temps en plus", "Coût total estimé"):
            expect(recommended.get_by_text(metric, exact=True)).to_be_visible()
        assert gps.evaluate("(node) => getComputedStyle(node).accentColor") == page.locator("#trajetBtn").evaluate(
            "(node) => getComputedStyle(node).backgroundColor")
        retry = context.request.post(ORIGIN + "/plus/trip", data=response.request.post_data_json,
                                     headers={"Authorization": f"Bearer {token}"})
        assert retry.ok and retry.json()["credits"] == 4
        if folder := environ.get("PLUS_SCREENSHOTS_DIR"):
            Path(folder).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=Path(folder, f"trajet-{label}.png"), full_page=True)

        map_button = result.get_by_role("button", name="Voir la carte")
        map_button.click()
        map_panel = result.get_by_role("region", name="Carte des stations comparées")
        expect(map_panel.locator(".leaflet-marker-icon")).to_have_count(cards.count(), timeout=15000)
        expect(map_panel.locator(".leaflet-marker-icon.best")).to_have_count(1)
        recommended.get_by_role("button", name=pattern(r"Sur la carte :")).click()
        expect(map_panel.locator(".leaflet-popup-content")).to_contain_text(recommended.get_by_role("heading").inner_text())
        if folder:
            page.screenshot(path=Path(folder, f"trajet-carte-{label}.png"), full_page=True)
        result.get_by_role("button", name="Masquer la carte").click()
        expect(map_panel).to_be_hidden()

        context.grant_permissions(["geolocation"], origin=ORIGIN)
        gps.check()
        expect(departure).to_be_hidden()
        expect(result.locator(".card.best")).to_be_hidden()
        search.click()
        expect(result.locator(".card.best")).to_be_visible(timeout=70000)
        gps_origin = page.evaluate("window.crTripVerifiedMeta.origin")
        assert gps_origin == {"lat": PARIS["latitude"], "lon": PARIS["longitude"]}
        expect(result.locator("a.go")).to_have_attribute("href",
            pattern(r"origin=48\.8566(?:%2C|,)2\.3522"))
        assert comparison_state(context, token)["credits"] == 4
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        print(f"{label}: départ manuel et GPS, {comparison['result']['verified']} détours, crédits 5 → 4", flush=True)
        context.close()
    browser.close()
