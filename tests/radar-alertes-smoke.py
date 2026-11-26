import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ORIGIN = "http://localhost:8765"
PAGE = ORIGIN + "/france/"
HTML = Path("france/index.html").read_bytes()
STATION = {
    "id": "75001001", "adresse": "10 avenue de la Station", "ville": "Paris", "cp": "75001",
    "geom": {"lat": 48.8566, "lon": 2.3522}, "e10_prix": 1.8
}
DESTINATION = re.compile(r"https://www\.waze\.com/ul\?ll=48\.8566,2\.3522&navigate=yes")


def respond(route):
    url = route.request.url
    if url.startswith(PAGE):
        route.fulfill(body=HTML, content_type="text/html; charset=utf-8")
    elif url.startswith("https://carburant-proxy.") and "/?" in url:
        rows = [] if "lat=44" in url else [STATION]
        route.fulfill(json={"results": rows}, headers={"access-control-allow-origin": "*"})
    else:
        route.abort()


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(**pw.devices["Pixel 7"], locale="fr-FR", service_workers="block")
    page = context.new_page()
    page.route("**/*", respond)
    er = []
    page.on("pageerror", lambda e: er.append(str(e)))
    page.add_init_script("""
      localStorage.setItem('cr_onboarding_vu', 'true');
      localStorage.setItem('cr_tuto_vu', 'true');
      localStorage.setItem('cr_nav_pref', 'waze');
      localStorage.setItem('cr_alert_key', JSON.stringify('fixture'));
      localStorage.setItem('cr_alert_info', JSON.stringify({lat:48.85,lon:2.35,rayon:5,carburant:'E10'}));
      Object.defineProperty(Notification,'permission',{value:'granted'});
      const registration = new EventTarget();
      registration.scope = location.origin + '/';
      registration.pushManager = {getSubscription: async () => ({})};
      registration.showNotification = async (title, options) => { window.testNotice={title,...options}; };
      const service = new EventTarget();
      service.register = async () => registration;
      service.ready = Promise.resolve(registration);
      Object.defineProperty(navigator,'serviceWorker',{value:service});
    """)
    page.goto(PAGE)
    expect(page.locator("#splash")).to_be_hidden()

    page.evaluate("""() => {
      crActiveVehicle=() => ({reservoir:50,conso:6});
      crFillFraction=0.8;
      st=[
        {id:'autre',adresse:'Autre station',cp:'12345',ville:'Autre ville',lat:43.7,lon:7.26,
          prix:1.8,distance:2,duree:300,distRoute:2500,distRetour:1500},
        {id:'sans-trajet',adresse:'Station B',cp:'12345',ville:'Autre ville',lat:43.7,lon:7.27,
          prix:1.89,distance:3,duree:null,distRoute:null}
      ];
      render();
    }""")
    card = page.locator("#card-autre")
    expect(card.locator(".metrics").filter(has_text="Carburant acheté")).to_contain_text("72,00 €")
    expect(card.locator(".metrics").filter(has_text="Trajet aller-retour")).to_contain_text("0,43 €")
    expect(card.locator(".radar-cost-total")).to_contain_text("72,43 €")
    expect(page.locator("#card-sans-trajet")).to_contain_text("Trajet non calculé")
    assert card.locator(".metrics").filter(has_text="Carburant acheté").evaluate(
        "(e) => e.getBoundingClientRect().bottom") <= card.locator(".radar-cost-total").evaluate(
        "(e) => e.getBoundingClientRect().top")

    page.locator(".menu-btn").click()
    page.locator("#crV07Main").get_by_role("button", name="Alertes prix").click()
    page.get_by_role("button", name="Tester ma notification").click()
    expect(page.locator("#testAlertStatus")).to_have_text("Notification de test affichée sur cet appareil.")
    assert page.evaluate("testNotice.data.stationId") == STATION["id"]
    assert page.evaluate("testNotice.data.carburant") == "E10"
    page.locator("#crV07Close").click()
    page.locator("#nav-trajet").click()
    page.evaluate("""navigator.serviceWorker.dispatchEvent(new MessageEvent('message',
      {data:{...testNotice.data,type:'NOTIFICATION_CLICK'}}))""")
    fiche = page.locator("#notificationStation")
    expect(fiche).to_contain_text(STATION["adresse"])
    expect(fiche).to_contain_text("E10 · 1,800 €/L")
    expect(fiche.get_by_role("link", name="Y aller")).to_have_attribute("href", DESTINATION)
    expect(page.locator("#page-radar")).to_have_class(re.compile(r"\bactive\b"))
    assert page.evaluate("st[0].id") == "autre"
    fiche.get_by_role("button", name="Fermer la fiche station").click()
    expect(fiche).to_be_hidden()

    page.goto(PAGE + "?notif=1#station=75001001&lat=48.8566&lon=2.3522&carburant=E10")
    expect(fiche).to_contain_text(STATION["adresse"])
    expect(fiche.get_by_role("link", name="Y aller")).to_have_attribute("href", DESTINATION)
    assert page.url == PAGE
    page.goto(PAGE + "?notif=1#station=75001002&lat=44&lon=2&carburant=E10")
    expect(fiche).to_contain_text("Position de la station reçue dans la notification.")
    expect(fiche.get_by_role("link", name="Y aller")).to_have_attribute("href", re.compile(r"ll=44,2&"))
    assert not er, er
    print("Radar mobile : somme sous les deux montants, notification de test, fiche et lien de navigation vérifiés.")
    browser.close()
