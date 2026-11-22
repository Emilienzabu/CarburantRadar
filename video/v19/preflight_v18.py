"""Read-only environment checks before attempting a real-site video.

Retry transient geocoder connectivity errors. No credentials or publication.
"""
import argparse
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = 'https://carburantradar.fr/france/'
OFFICIAL = 'https://donnees.roulez-eco.fr/opendata/instantane'
GEO = 'https://geo.api.gouv.fr/communes?nom=Lyon&fields=nom,code,centre&format=json&geometry=centre'


def check_url(url, opener=None, timeout=12):
    """Bounded GET, without Range. Site must be real HTML on expected host."""
    from urllib.parse import urlsplit
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(url, headers={
        'User-Agent': 'CarburantRadar-V22-preflight/1.0',
        'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
    })
    try:
        with opener(req, timeout=timeout) as resp:
            status = getattr(resp, 'status', 200)
            final = resp.geturl()
            chunk = resp.read(2048)
            is_site = url == SITE
            parsed = urlsplit(final)
            host_ok = (parsed.scheme == 'https' and parsed.hostname in
                       {'carburantradar.fr', 'www.carburantradar.fr'})
            html_ok = b'<html' in chunk.lower() or b'<!doctype html' in chunk.lower()
            ok = status == 200 and bool(chunk) and (not is_site or (host_ok and html_ok))
            return {'ok': ok, 'status': status, 'final_url': final,
                    'sample_bytes': len(chunk),
                    'site_html_sample_valid': html_ok if is_site else None,
                    'site_host_valid': host_ok if is_site else None}
    except urllib.error.HTTPError as e:
        # urlopen raises on 4xx/5xx: keep the status so transient ones can be retried.
        return {'ok': False, 'status': e.code, 'error': 'HTTPError: ' + str(e)[:200]}
    except Exception as e:
        return {'ok': False, 'error': type(e).__name__ + ': ' + str(e)[:200]}


def check_geocoder(checker=check_url, sleep=time.sleep, attempts=3):
    """Retry only network-like failures and transient HTTP statuses."""
    for index in range(attempts):
        result = checker(GEO)
        if result.get('ok') is True:
            return {**result, 'attempts': index + 1}
        status = result.get('status')
        error = result.get('error', '')
        transient = (status in {408, 429, 500, 502, 503, 504} or
                     any(marker in error for marker in
                         ('URLError', 'TimeoutError', 'ConnectionError', 'ConnectionResetError')))
        if not transient or index == attempts - 1:
            return {**result, 'attempts': index + 1}
        sleep(index + 1)
    raise RuntimeError('Unreachable')


def check_binary(name, runner=subprocess.run):
    exe = shutil.which(name)
    if not exe:
        return {'ok': False, 'error': 'binary_missing'}
    try:
        p = runner([exe, '-version'], capture_output=True, text=True, timeout=8)
        return {'ok': p.returncode == 0, 'path': exe,
                'version': p.stdout.splitlines()[0][:120] if p.stdout else ''}
    except Exception as e:
        return {'ok': False, 'error': type(e).__name__}


def preflight(url_checker=check_url, binary_checker=check_binary):
    checks = {
        'site_france': url_checker(SITE),
        'official_prices': url_checker(OFFICIAL),
        'french_geocoder': check_geocoder(checker=url_checker),
        'ffmpeg': binary_checker('ffmpeg'),
        'ffprobe': binary_checker('ffprobe'),
    }
    try:
        import playwright.sync_api
        checks['playwright'] = {'ok': True,
                               'note': 'Python package import only; browser launch requires a live test'}
    except ImportError:
        checks['playwright'] = {'ok': False, 'error': 'python_playwright_missing'}
    ready = all(v.get('ok') is True for v in checks.values())
    return {'status': 'prerequisites_available' if ready else 'blocked',
            'real_site_capture_verified': False, 'video_generated': False,
            'publication_authorized': False,
            'checked_at': datetime.now(timezone.utc).isoformat(), 'checks': checks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='preflight_report.json')
    args = ap.parse_args()
    report = preflight()
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'prerequisites_available' else 2


if __name__ == '__main__':
    raise SystemExit(main())
