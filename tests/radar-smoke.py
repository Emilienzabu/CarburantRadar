import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright


ORIGIN = "http://localhost:8765"
PAGE = ORIGIN + "/france/"
HTML = Path("france/index.html").read_bytes()
ICON = Path("icons/icon-96.png").read_bytes()


def respond(route):
    if route.request.url == PAGE:
        route.fulfill(body=HTML, content_type="text/html; charset=utf-8")
    elif route.request.url == ORIGIN + "/icons/icon-96.png":
        route.fulfill(body=ICON, content_type="image/png")
    else:
        route.abort()


def check(browser, device, theme, accent):
    with browser.new_context(**device, locale="fr-FR", service_workers="block") as context:
        page = context.new_page()
        page.route("**/*", respond)
        page.add_init_script("""
            localStorage.setItem('cr_onboarding_vu', 'true');
            localStorage.setItem('cr_tuto_vu', 'true');
        """)
        page.goto(PAGE)
        expect(page.locator("#splash")).to_be_hidden()
        if theme == "clair":
            page.evaluate("document.documentElement.dataset.theme = 'light'")
        radar = page.locator("#nav-radar")
        icon = radar.locator("img")
        expect(radar).to_have_class("nav-btn active")
        expect(icon).to_have_css("clip-path", "inset(7% round 18%)")
        assert icon.evaluate("(img) => img.complete && img.naturalWidth === 96")
        image = Image.open(io.BytesIO(icon.screenshot(animations="disabled"))).convert("RGB")
        w, h = image.size
        corners = [(round(w * x), round(h * y)) for x in (0.08, 0.9) for y in (0.08, 0.9)]
        for xy in corners:
            pixel = image.getpixel(xy)
            assert max(abs(p - a) for p, a in zip(pixel, accent)) <= 6, (theme, xy, pixel, accent)
        assert image.getpixel((round(w * .38), round(h * .42))) != accent
        page.locator("#nav-trajet").click()
        expect(icon).to_have_css("clip-path", "none")
        radar.click()
        expect(icon).to_have_css("clip-path", "inset(7% round 18%)")
        print(f"Thème {theme} : coins orange et icône visible, changement d’onglet validé")


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    check(browser, pw.devices["Pixel 7"], "sombre", (245, 166, 35))
    check(browser, pw.devices["iPhone 13"], "clair", (232, 148, 15))
    browser.close()
