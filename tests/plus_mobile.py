from os import environ
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ORIGIN = "http://localhost:8765"
files = {"/france/": ("index.html", "text/html"),
         "/france/plus.js": ("plus.js", "application/javascript"),
         "/france/plus-rewarded.mjs": ("plus-rewarded.mjs", "application/javascript"),
         "/france/plus.css": ("plus.css", "text/css")}
calls = []
analysis_unlocked = False
extra_alerts = []
trip_charges = []


def respond(route):
    global analysis_unlocked
    request = route.request
    cors = {"access-control-allow-origin": "*", "access-control-allow-headers": "authorization,content-type",
            "access-control-allow-methods": "GET,POST,OPTIONS"}
    local_path = request.url[len(ORIGIN):].split("?", 1)[0]
    if request.url.startswith(ORIGIN) and local_path in files:
        filename, mime = files[local_path]
        route.fulfill(body=Path("france", filename).read_bytes(), content_type=mime + "; charset=utf-8")
    elif "carburant-proxy." in request.url and request.method == "OPTIONS":
        route.fulfill(status=204, headers=cors)
    elif "carburant-proxy." in request.url and "/plus/" in request.url:
        action = request.url.rsplit("/", 1)[-1]
        assert request.headers.get("authorization") == "Bearer session-fixture"
        calls.append(action)
        if action == "preview":
            route.fulfill(json={"months": 6, "lifetime": False, "until": 1800000000000}, headers=cors)
        elif action == "checkout":
            assert request.post_data_json == {"plan": "year"}
            route.fulfill(json={"url": "https://checkout.stripe.com.example.test/invalid"}, headers=cors)
        else:
            result = None
            if action == "analysis":
                assert request.post_data_json["confirm"] is True
                assert request.post_data_json["params"]["period"] == 30
                analysis_unlocked = True
                result = {"dates": ["2026-11-25", "2026-11-26"], "average": [1.8, 1.7], "prices": [None, None]}
            if action == "add":
                settings = request.post_data_json["settings"]
                assert settings["name"] == "Travail"
                assert settings["carburant"] == "E10"
                assert settings["sub"]["endpoint"].startswith("https://fcm.googleapis.com/")
                extra_alerts.append({"name": settings["name"], "carburant": settings["carburant"],
                                     "rayon": settings["rayon"], "id": request.post_data_json["id"],
                                     "active": True, "until": 4102444800000})
            if action == "remove":
                assert request.post_data_json["id"] == extra_alerts[0]["id"]
                extra_alerts.clear()
            if action == "trip":
                assert request.post_data_json["confirm"] is True
                assert request.post_data_json["params"]["destination"]["lat"] == 48.9
                trip_charges.append(request.post_data_json["id"])
                result = {"verified": 2, "choices": [{"label": "Coût total le plus bas",
                          "station": {"address": "Station vérifiée côté serveur", "price": 1.7, "total": 29, "minutes": 2}}]}
            credits = 5 if action == "status" or analysis_unlocked else 6
            if extra_alerts:
                credits -= 2
            route.fulfill(json={"credits": credits, "claimed": action == "claim",
                                "canClaimToday": action == "status",
                                "analysis": {"unlocked": analysis_unlocked,
                                             "expires": 4102444800000 if analysis_unlocked else None},
                                "billing": {"test": True, "hasCustomer": False, "canCheckout": True},
                                "rewards": {"mode": "simulation"},
                                "history": [{"amount": 1, "reason": "daily", "time": 1795734000000}]
                                           if action == "claim" else [],
                                "trip": True, "alerts": extra_alerts, "result": result,
                                "plus": {"active": action == "redeem", "lifetime": False,
                                         "until": 1800000000000 if action == "redeem" else None}}, headers=cors)
    elif "carburant-proxy." in request.url and request.url.endswith("/account"):
        route.fulfill(json={"ok": True, "data": {}}, headers=cors)
    else:
        route.abort()


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(**pw.devices["Pixel 7"], locale="fr-FR", service_workers="block")
    page = ctx.new_page()
    page.route("**/*", respond)
    page.add_init_script("""
      localStorage.setItem('cr_onboarding_vu', 'true');
      localStorage.setItem('cr_tuto_vu', 'true');
      localStorage.setItem('cr_account_token', 'session-fixture');
      localStorage.setItem('cr_reps', JSON.stringify([{name: 'Travail', lat: 48.8, lon: 2.3}]));
      Object.defineProperty(Notification, 'permission', {value: 'granted'});
      const registration = new EventTarget();
      registration.scope = location.origin + '/';
      registration.pushManager = {getSubscription: async () => ({toJSON: () => ({
        endpoint: 'https://fcm.googleapis.com/fcm/send/fixture',
        keys: {auth: 'AAAAAAAAAAAAAAAAAAAAAA', p256dh: 'A'.repeat(87)}
      })})};
      const service = new EventTarget();
      service.register = async () => registration;
      service.ready = Promise.resolve(registration);
      Object.defineProperty(navigator, 'serviceWorker', {value: service});
    """)
    page.goto(ORIGIN + "/france/")
    expect(page.locator("#splash")).to_be_hidden()
    page.locator(".menu-btn").click()
    page.get_by_role("button", name="CarburantRadar Plus").click()
    panel = page.get_by_role("region", name="CarburantRadar Plus")
    expect(panel).to_be_visible()
    expect(panel.get_by_text("5 crédits disponibles")).to_be_visible()
    panel.get_by_role("button", name="Réclamer mon crédit du jour").click()
    expect(panel.get_by_text("6 crédits disponibles")).to_be_visible()
    panel.get_by_text("Historique des crédits").click()
    expect(panel.locator("[data-plus-history] li")).to_contain_text("Crédit du jour")
    expect(panel.get_by_role("button", name="Réclamer mon crédit du jour")).to_be_hidden()
    expect(panel.get_by_role("button", name="Tester à 1 €/mois")).to_be_visible()
    panel.get_by_role("button", name="Tester à 10 €/an").click()
    expect(panel.get_by_text("Le lien Stripe est indisponible.")).to_be_visible()
    assert page.url == ORIGIN + "/france/"
    prepare_ad = panel.get_by_role("button", name="Préparer la publicité")
    prepare_ad.click()
    panel.get_by_role("button", name="Refuser").click()
    expect(panel.get_by_text("Publicité passée. Aucun crédit simulé.")).to_be_visible()
    prepare_ad.click()
    panel.get_by_role("button", name="Regarder", exact=True).click()
    panel.get_by_role("button", name="Fermer la publicité").click()
    expect(panel.get_by_text("Publicité passée. Aucun crédit simulé.")).to_be_visible()
    panel.get_by_label("Simuler une annonce indisponible").check()
    prepare_ad.click()
    expect(panel.get_by_text("Aucune publicité disponible pour le moment.")).to_be_visible()
    panel.get_by_label("Simuler une annonce indisponible").uncheck()
    prepare_ad.click()
    panel.get_by_role("button", name="Regarder", exact=True).click()
    expect(panel.get_by_text("2 crédits simulés obtenus.")).to_be_visible()
    expect(panel.get_by_text("6 crédits disponibles")).to_be_visible()
    assert calls == ["status", "claim", "checkout"]
    page.locator("#crV07Close").click()
    page.locator("#nav-analyse").click()
    page.evaluate("""() => {
      document.getElementById('analyseList').innerHTML = '<div id="analyseLoading"></div>';
      window.dessinerGraphique = (dates, series) => {window.receivedAnalysis = {dates, series};};
      document.getElementById('analyseList').insertAdjacentHTML('beforeend', '<div id="analyseGraphContainer"></div>');
      chargerSerieZone(48.8, 2.3, 5, 30, 'E10', ++analyseReqId);
    }""")
    panel.get_by_role("button", name="Débloquer l’analyse détaillée pour 24 h", exact=False).click()
    page.wait_for_function("window.receivedAnalysis?.series[1] === 1.7")
    expect(panel).to_be_hidden()
    page.locator(".menu-btn").click()
    page.get_by_role("button", name="CarburantRadar Plus").click()
    expect(panel.get_by_text("5 crédits disponibles")).to_be_visible()
    panel.get_by_label("Carburant").select_option("E10")
    panel.get_by_role("button", name="Activer 7 jours", exact=False).click()
    expect(panel.get_by_text("Travail · E10", exact=False)).to_be_visible()
    expect(panel.get_by_text("3 crédits disponibles")).to_be_visible()
    panel.get_by_role("button", name="Supprimer").click()
    expect(panel.get_by_text("Travail · E10", exact=False)).to_be_hidden()
    panel.get_by_role("button", name="J’ai un code").click()
    code = panel.get_by_label("Code Plus")
    code.fill("1234-5678-90AB-CDEF-1234-5678")
    panel.get_by_role("button", name="Vérifier le code").click()
    expect(panel.get_by_text("Ce code ajoute 6 mois de Plus", exact=False)).to_be_visible()
    assert calls == ["status", "claim", "checkout", "status", "status", "analysis", "status", "add", "remove", "preview"]
    panel.get_by_role("button", name="Activer le code").click()
    expect(panel.get_by_text("Ton accès Plus est activé.")).to_be_visible()
    expect(panel.get_by_text("Ton accès Plus est actif jusqu’au", exact=False)).to_be_visible()
    assert calls[-2:] == ["preview", "redeem"]
    page.locator("#crV07Close").click()
    expect(panel).to_be_hidden()
    page.locator("#nav-trajet").click()
    page.evaluate("""() => {
      window.comparisonFixture = [
        {id:'1', adresse:'Station A', prix:1.75, crTotal:29, detour:60},
        {id:'2', adresse:'Station B', prix:1.79, crTotal:30, detour:120}
      ];
      crTripRun += 1;
      window.crTripVerifiedMeta = {origin:{lat:48.8,lon:2.3}, destination:{lat:48.9,lon:2.4}, fuel:'Gazole'};
      crTripRenderAlternatives(window.comparisonFixture);
    }""")
    comparison = page.get_by_role("button", name="Comparer les autres stations · 1 crédit")
    expect(comparison).to_be_visible()
    expect(page.locator("#crTripAlternatives")).to_be_hidden()
    comparison.click()
    expect(page.locator("#crTripAlternatives")).to_be_visible()
    expect(page.get_by_text("Station vérifiée côté serveur", exact=False)).to_be_visible()
    page.evaluate("crTripRenderAlternatives(window.comparisonFixture)")
    expect(page.locator("#crTripAlternatives")).to_be_visible()
    expect(comparison).to_be_hidden()
    assert len(trip_charges) == 1
    ctx.close()

    for width, height, touch in [(360, 780, True), (768, 1024, True), (1440, 900, False)]:
        screen = browser.new_context(viewport={"width": width, "height": height},
                                     has_touch=touch, service_workers="block", locale="fr-FR")
        page = screen.new_page()
        attempts = [0]

        def billing_response(route):
            request = route.request
            if request.method == "POST" and request.url.endswith("/plus/status"):
                returning = bool(request.post_data_json.get("refresh"))
                attempts[0] += 1
                active = returning and attempts[0] >= 2
                expiry = 4102444800000 if active else None
                route.fulfill(json={
                    "credits": 5, "canClaimToday": False, "history": [], "rewards": {"mode": "simulation"},
                    "plus": {"active": active, "lifetime": False, "until": expiry},
                    "billing": {"test": True, "hasCustomer": active, "canCheckout": not active,
                                "subscription": {"plan": "month", "status": "active", "paidUntil": expiry,
                                                 "periodEnd": expiry, "cancelAtPeriodEnd": False} if active else None},
                }, headers={"access-control-allow-origin": "*"})
            else:
                respond(route)

        page.route("**/*", billing_response)
        page.add_init_script("""localStorage.setItem('cr_onboarding_vu', 'true');
            localStorage.setItem('cr_tuto_vu', 'true');
            localStorage.setItem('cr_account_token', 'session-fixture');""")
        page.goto(ORIGIN + "/france/")
        expect(page.locator("#splash")).to_be_hidden()
        page.locator(".menu-btn").click()
        page.get_by_role("button", name="CarburantRadar Plus").click()
        plus = page.get_by_role("region", name="CarburantRadar Plus")
        expect(plus.get_by_text("−16,67 %")).to_be_visible()
        expect(plus.get_by_role("heading", name="Crédits", exact=True)).to_be_visible()
        assert page.locator("#crV07Close").bounding_box()["width"] <= 40
        assert plus.evaluate("element => element.closest('#crV07Detail').scrollWidth <= element.closest('#crV07Detail').clientWidth")
        page.wait_for_function("Math.abs(document.getElementById('sideMenu').getBoundingClientRect().right - innerWidth) <= 1")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        attempts[0] = 0
        page.goto(ORIGIN + "/france/?plus=retour")
        expect(plus.get_by_text("Vérification de ton abonnement…")).to_be_visible()
        expect(plus.get_by_text("Abonnement de test confirmé.")).to_be_visible(timeout=12000)
        expect(plus.get_by_text("Offre mensuelle · 1 €/mois", exact=False)).to_be_visible()
        expect(plus.get_by_role("button", name="Tester à 1 €/mois")).to_be_hidden()
        expect(plus.get_by_role("button", name="Gérer mon abonnement de test")).to_be_visible()
        expect(plus.get_by_text("Vérification de ton abonnement…")).to_be_hidden()
        assert page.locator("#crV07Close").bounding_box()["width"] <= 40
        if "PLUS_SCREENSHOTS_DIR" in environ:
            screenshots = Path(environ["PLUS_SCREENSHOTS_DIR"])
            screenshots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=screenshots / f"plus-{width}.png", animations="disabled")
        screen.close()
    browser.close()
