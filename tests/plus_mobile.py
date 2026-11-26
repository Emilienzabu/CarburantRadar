from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ORIGIN = "http://localhost:8765"
files = {"/france/": ("index.html", "text/html"),
         "/france/plus.js": ("plus.js", "application/javascript"),
         "/france/plus.css": ("plus.css", "text/css")}
calls = []


def respond(route):
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
        else:
            route.fulfill(json={"credits": 5 if action == "status" else 6, "claimed": action == "claim",
                                "canClaimToday": action == "status",
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
    panel.get_by_role("button", name="J’ai un code").click()
    code = panel.get_by_label("Code Plus")
    code.fill("1234-5678-90AB-CDEF-1234-5678")
    panel.get_by_role("button", name="Vérifier le code").click()
    expect(panel.get_by_text("Ce code ajoute 6 mois de Plus", exact=False)).to_be_visible()
    assert calls == ["status", "claim", "preview"]
    panel.get_by_role("button", name="Activer le code").click()
    expect(panel.get_by_text("Ton accès Plus est activé.")).to_be_visible()
    expect(panel.get_by_text("Ton accès Plus est actif jusqu’au", exact=False)).to_be_visible()
    assert calls == ["status", "claim", "preview", "redeem"]
    panel.get_by_role("button", name="Fermer").click()
    expect(panel).to_be_hidden()
    browser.close()
