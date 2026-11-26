from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ORIGIN = "http://localhost:8765"
files = {"/france/": ("index.html", "text/html"),
         "/france/plus.js": ("plus.js", "application/javascript"),
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
    if request.url.startswith(ORIGIN) and request.url[len(ORIGIN):] in files:
        filename, mime = files[request.url[len(ORIGIN):]]
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
    panel = page.get_by_role("dialog", name="CarburantRadar Plus")
    expect(panel).to_be_visible()
    expect(panel.get_by_text("5 crédits disponibles")).to_be_visible()
    panel.get_by_role("button", name="Réclamer mon crédit du jour").click()
    expect(panel.get_by_text("6 crédits disponibles")).to_be_visible()
    expect(panel.get_by_role("button", name="Réclamer mon crédit du jour")).to_be_hidden()
    expect(panel.get_by_role("button", name="Tester à 1 €/mois")).to_be_visible()
    panel.get_by_role("button", name="Tester à 10 €/an").click()
    expect(panel.get_by_text("Le lien Stripe est indisponible.")).to_be_visible()
    assert page.url == ORIGIN + "/france/"
    panel.get_by_role("button", name="Fermer").click()
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
    panel.get_by_role("button", name="Fermer").click()
    expect(panel).to_be_hidden()
    page.locator("#crV07Close").click()
    page.locator("#nav-trajet").click()
    page.evaluate("""() => {
      window.comparisonFixture = [
        {id:'1', adresse:'Station A', prix:1.75, crTotal:29, detour:60},
        {id:'2', adresse:'Station B', prix:1.79, crTotal:30, detour:120}
      ];
      crTripRun += 1;
      la = 48.8; lo = 2.3; trajetDestLat = 48.9; trajetDestLon = 2.4;
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
    browser.close()
