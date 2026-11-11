"""Read-only visual automation for CarburantRadar France, never publishes.

Run: python capture_france.py --city Marseille --fuel Gazole --out captures
Requires playwright and installed Chromium. Does not bypass site protections.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from geocoding import resolve
from geo_audit import audit_state

SITE = 'https://carburantradar.fr/france/'
FUELS = {'Gazole', 'SP95', 'SP98', 'E10', 'E85', 'GPLc'}


def validate(fuel, url=SITE):
    if fuel not in FUELS:
        raise ValueError('Carburant inconnu')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'carburantradar.fr', 'www.carburantradar.fr'} or parsed.path.rstrip('/') != '/france':
        raise ValueError('URL hors de CarburantRadar France')


def target_box(locator):
    b = locator.bounding_box()
    if not b or b['width'] <= 0 or b['height'] <= 0:
        raise RuntimeError('Cible invisible : impossible de calculer le zoom')
    return {k: round(b[k], 2) for k in ('x', 'y', 'width', 'height')}


def capture(city, fuel='Gazole', out='captures', url=SITE, insee=None):
    validate(fuel, url)
    commune = resolve(city, insee)
    lat, lon = commune.latitude, commune.longitude
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    steps = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 390, 'height': 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            locale='fr-FR',
            geolocation={'latitude': lat, 'longitude': lon},
            permissions=['geolocation'],
        )
        # Avoid leaking any account/session data: new isolated context, no login.
        page = context.new_page()
        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if not response or response.status >= 400:
                raise RuntimeError(f'Chargement impossible : HTTP {response.status if response else "sans réponse"}')
            page.locator('#page-radar').wait_for(state='visible', timeout=15000)
            # Onboarding may obscure controls; close only when a visible close control exists.
            page.evaluate("""() => {
              for (const id of ['onboardingModal', 'tutoModal']) {
                const el = document.getElementById(id);
                if (el) el.classList.remove('on');
              }
              const splash = document.getElementById('splash');
              if (splash) splash.style.display='none';
            }""")
            fuel_button = page.locator(f'#page-radar #fg .fb[data-f="{fuel}"]')
            fuel_button.wait_for(state='visible', timeout=10000)
            steps.append({'action': 'choose_fuel', 'fuel': fuel, 'bbox': target_box(fuel_button)})
            fuel_button.click()
            if 'a' not in (fuel_button.get_attribute('class') or '').split():
                raise RuntimeError('Carburant non sélectionné après clic')
            page.screenshot(path=str(dest/'01_carburant.png'))
            loc = page.locator('#locBtn')
            steps.append({'action': 'locate', 'city_scenario': commune.nom, 'insee': commune.code, 'coords_scenario': {'lat': lat, 'lon': lon}, 'bbox': target_box(loc)})
            loc.click()
            page.screenshot(path=str(dest/'02_localisation.png'))
            # Network results must actually load. No fictitious city search input.
            try:
                page.wait_for_function("""() => {
                    const e=document.getElementById('sc');
                    return e && Number((e.textContent||'').replace(/\\s/g,'')) > 0;
                }""", timeout=25000)
            except Exception as exc:
                raise RuntimeError('Aucune station réelle confirmée : vidéo bloquée') from exc
            # Audit de la position et des stations dans l'état réel de l'application.
            # Un compteur positif seul ne prouve pas que les stations appartiennent à la ville.
            app_state = page.evaluate("""() => ({
              lat: typeof la !== 'undefined' ? la : null,
              lon: typeof lo !== 'undefined' ? lo : null,
              fuel: typeof fu !== 'undefined' ? fu : null,
              radius: typeof ra !== 'undefined' ? ra : null,
              stations: typeof st !== 'undefined' && Array.isArray(st)
                ? st.map(s => ({id:s.id,lat:s.lat,lon:s.lon,prix:s.prix})) : null
            })""")
            geo_result = audit_state(app_state, lat, lon, fuel)
            count = page.locator('#sc').inner_text()
            minimum = page.locator('#sm').inner_text()
            average = page.locator('#sa').inner_text()
            if not re.search(r'\d', minimum) or not re.search(r'\d', average):
                raise RuntimeError('Statistiques illisibles : vidéo bloquée')
            page.screenshot(path=str(dest/'03_resultats.png'))
            steps.append({'action': 'results', 'stations_displayed': count, 'minimum_displayed': minimum, 'average_displayed': average, 'bbox': target_box(page.locator('#stats'))})
            result = {'source': url, 'city_scenario': commune.nom, 'insee': commune.code, 'city_selection_method': 'browser_geolocation_override', 'fuel': fuel, 'verified_on_real_site': True, 'geolocation_verified_in_app': True, 'geographic_audit': geo_result, 'displayed_prices': [{'station_id':str(s['id']), 'fuel':fuel, 'price':s['prix']} for s in app_state['stations'] if s.get('prix') is not None], 'steps': steps}
            (dest/'trace.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            return result
        except Exception as exc:
            # Never write verified_on_real_site=True on failure.
            (dest/'diagnostic.json').write_text(json.dumps({'status':'failed', 'error':str(exc), 'steps_completed':steps},ensure_ascii=False,indent=2),encoding='utf-8')
            raise
        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--city', required=True)
    parser.add_argument('--insee', default=None, help='Code INSEE si plusieurs communes portent le même nom')
    parser.add_argument('--fuel', default='Gazole')
    parser.add_argument('--out', default='captures')
    args = parser.parse_args()
    capture(args.city, args.fuel, args.out, insee=args.insee)
