"""Read-only V18 environment checks before attempting a real-site video.
No credentials, production writes, or publication. Exit nonzero on missing requirements.
"""
import argparse
import json
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE='https://carburantradar.fr/france/'
OFFICIAL='https://donnees.roulez-eco.fr/opendata/instantane'
GEO='https://geo.api.gouv.fr/communes?nom=Lyon&fields=nom,code,centre&format=json&geometry=centre'


def check_url(url, opener=None, timeout=12):
    """Fetch a small bounded sample, following redirects, and report final host.
    No claim that a HEAD-only response proves the application works.
    """
    opener=opener or urllib.request.urlopen
    req=urllib.request.Request(url,headers={'User-Agent':'CarburantRadar-V18-preflight/1.0','Range':'bytes=0-2047'})
    try:
        with opener(req,timeout=timeout) as resp:
            status=getattr(resp,'status',200)
            final=resp.geturl()
            chunk=resp.read(2048)
            return {'ok':status==200 and len(chunk)>0,'status':status,'final_url':final,'sample_bytes':len(chunk)}
    except Exception as e:
        return {'ok':False,'error':type(e).__name__+': '+str(e)[:200]}


def check_binary(name,runner=subprocess.run):
    exe=shutil.which(name)
    if not exe:return {'ok':False,'error':'binary_missing'}
    try:
        p=runner([exe,'-version'],capture_output=True,text=True,timeout=8)
        return {'ok':p.returncode==0,'path':exe,'version':p.stdout.splitlines()[0][:120] if p.stdout else ''}
    except Exception as e:return {'ok':False,'error':type(e).__name__}


def preflight(url_checker=check_url, binary_checker=check_binary):
    checks={
        'site_france':url_checker(SITE),
        'official_prices':url_checker(OFFICIAL),
        'french_geocoder':url_checker(GEO),
        'ffmpeg':binary_checker('ffmpeg'),
        'ffprobe':binary_checker('ffprobe'),
    }
    try:
        import playwright.sync_api
        checks['playwright']={'ok':True,'note':'Python package import only; browser launch still requires a live test'}
    except ImportError:checks['playwright']={'ok':False,'error':'python_playwright_missing'}
    # The live site must be reachable before claiming end-to-end validation.
    ready=all(v.get('ok') is True for v in checks.values())
    return {'status':'prerequisites_available' if ready else 'blocked',
            'real_site_capture_verified':False,'video_generated':False,
            'publication_authorized':False,'checked_at':datetime.now(timezone.utc).isoformat(),
            'checks':checks}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default='preflight_report.json')
    args=ap.parse_args()
    report=preflight()
    Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='prerequisites_available' else 2

if __name__=='__main__':raise SystemExit(main())
