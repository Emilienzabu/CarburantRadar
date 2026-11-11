"""Strict verification of a Playwright capture before rendering a public video."""
from pathlib import Path
import json
import re
from PIL import Image
from price_audit import audit_prices

STEPS = ('choose_fuel', 'locate', 'results')
SHOTS = ('01_carburant.png', '02_localisation.png', '03_resultats.png')

def _bbox_valid(box, viewport=(390,844)):
    if not isinstance(box, dict): return False
    try:
        x,y,w,h=(float(box[k]) for k in ('x','y','width','height'))
    except (ValueError, TypeError, KeyError): return False
    return w>0 and h>0 and x>=0 and y>=0 and x+w<=viewport[0]+1 and y+h<=viewport[1]+1

def validate_capture(folder, min_dsf=3, viewport=(390,844)):
    folder=Path(folder)
    path=folder/'trace.json'
    if not path.is_file(): raise ValueError('Missing trace.json')
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('verified_on_real_site') is not True: raise ValueError('Not verified on real site')
    if data.get('source') != 'https://carburantradar.fr/france/': raise ValueError('Untrusted source')
    audit=data.get('geographic_audit')
    if data.get('geolocation_verified_in_app') is not True or not isinstance(audit,dict) or audit.get('verified') is not True:
        raise ValueError('Geographic audit not verified')
    if not isinstance(audit.get('station_count_audited'),int) or audit['station_count_audited'] < 1:
        raise ValueError('No audited stations')
    steps=data.get('steps')
    if not isinstance(steps,list) or tuple(s.get('action') for s in steps)!=STEPS: raise ValueError('Missing or reordered steps')
    for step in steps:
        if not _bbox_valid(step.get('bbox'),viewport): raise ValueError('Invalid target bounding box')
    results=steps[-1]
    try: n=int(re.sub(r'\s','',results['stations_displayed']))
    except (TypeError,ValueError,KeyError): raise ValueError('Invalid station count')
    if n<=0: raise ValueError('No stations')
    for k in ('minimum_displayed','average_displayed'):
        s=results.get(k,'')
        if not re.search(r'\d+[,.]\d+',s): raise ValueError('Missing numerical price: '+k)
    for name in SHOTS:
        path=folder/name
        if not path.is_file(): raise ValueError('Missing screenshot: '+name)
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            w,h=im.size
        if w < viewport[0]*min_dsf or h < viewport[1]*min_dsf:
            raise ValueError('Screenshot resolution insufficient: '+name)
    evidence_file = folder/'official_evidence.json'
    if not evidence_file.is_file():
        raise ValueError('Official evidence required: no public video without independent price validation')
    evidence = json.loads(evidence_file.read_text(encoding='utf-8'))
    if evidence.get('provenance_verified_by_adapter') is not True:
        raise ValueError('Official source provenance not confirmed by trusted adapter')
    price_audit = audit_prices(data.get('displayed_prices'), evidence.get('rows'),
        source=evidence.get('source'), retrieved_at=evidence.get('retrieved_at'))
    return {'price_audit': price_audit, 'ok':True,'city':data['city_scenario'],'fuel':data['fuel'],'stations':n,'screenshots':list(SHOTS)}
