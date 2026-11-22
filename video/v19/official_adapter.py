"""Official French fuel XML adapter; read-only HTTPS download, fail-closed parsing.

The canonical feed endpoint is configured by OFFICIAL_SOURCE in price_audit.
Only an actual HTTPS fetch through fetch_official may mark provenance verified.
"""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, Request
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile
import json
from zoneinfo import ZoneInfo
from price_audit import OFFICIAL_SOURCE, audit_prices

MAX_DOWNLOAD = 35 * 1024 * 1024
MAX_XML = 85 * 1024 * 1024
FUEL_MAP = {'Gazole':'Gazole','SP95':'SP95','SP98':'SP98','E10':'E10','E85':'E85','GPLc':'GPLc', 'GPL':'GPLc'}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused for official evidence')


def unpack_xml(blob):
    if len(blob) > MAX_DOWNLOAD: raise ValueError('Official download too large')
    if blob[:4] == b'PK\x03\x04':
        with ZipFile(BytesIO(blob)) as z:
            members = [m for m in z.infolist() if m.filename.lower().endswith('.xml') and not m.is_dir()]
            if len(members) != 1: raise ValueError('Expected exactly one XML in official ZIP')
            info = members[0]
            if info.file_size > MAX_XML: raise ValueError('Uncompressed XML too large')
            with z.open(info) as f: xml = f.read(MAX_XML + 1)
            if len(xml) > MAX_XML: raise ValueError('Uncompressed XML too large')
            return xml
    if len(blob) > MAX_XML: raise ValueError('XML too large')
    return blob


def parse_update(value):
    if not isinstance(value,str) or not value.strip(): raise ValueError('Missing official update time')
    value=value.strip()
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as e: raise ValueError('Invalid official update time') from e
    # Official French feed dates without offsets are interpreted in Europe/Paris.
    if dt.tzinfo is None: dt=dt.replace(tzinfo=ZoneInfo('Europe/Paris'))
    return dt.astimezone(timezone.utc).isoformat()


def extract_prices(blob, wanted):
    """Return only requested station+fuel rows from official pdv/prix XML.

    'wanted' is a list of pairs, not arbitrary XML queries. Reject duplicates.
    """
    keys=[(str(s).strip(),str(f).strip()) for s,f in wanted]
    if not keys or any(not s or f not in FUEL_MAP.values() for s,f in keys) or len(set(keys))!=len(keys):
        raise ValueError('Invalid wanted stations/fuels')
    requested=set(keys); found={}
    xml=unpack_xml(blob)
    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise ValueError('DTD and entities not allowed')
    try: root=ET.fromstring(xml)
    except ET.ParseError as e: raise ValueError('Invalid official XML') from e
    if root.tag.split('}')[-1] not in ('pdv_liste','pdv_liste_maj'):
        raise ValueError('Unexpected official XML root')
    for pdv in root.iter():
        if pdv.tag.split('}')[-1] != 'pdv': continue
        station=pdv.get('id','').strip()
        for price in pdv:
            if price.tag.split('}')[-1] != 'prix': continue
            fuel=FUEL_MAP.get(price.get('nom',''))
            key=(station,fuel)
            if key not in requested: continue
            if key in found: raise ValueError('Duplicate official price entry')
            raw=price.get('valeur')
            try: val=float(raw)
            except (ValueError,TypeError) as e: raise ValueError('Invalid official price') from e
            found[key]={'station_id':station,'fuel':fuel,'price':val,
                        'updated_at':parse_update(price.get('maj'))}
    missing=requested-set(found)
    if missing: raise ValueError('Missing official entries: '+str(sorted(missing)[:4]))
    return [found[key] for key in keys]


def fetch_official(timeout=30):
    parts=urlsplit(OFFICIAL_SOURCE)
    if parts.scheme!='https' or parts.hostname!='donnees.roulez-eco.fr':
        raise ValueError('Unapproved official host')
    opener=build_opener(HTTPSHandler(),NoRedirect())
    req=Request(OFFICIAL_SOURCE,headers={'User-Agent':'CarburantRadar-evidence-check/1.0','Accept':'application/zip, application/xml, */*'})
    with opener.open(req,timeout=timeout) as response:
        if response.status!=200 or response.geturl()!=OFFICIAL_SOURCE:
            raise ValueError('Unexpected official response')
        blob=response.read(MAX_DOWNLOAD+1)
        if len(blob)>MAX_DOWNLOAD: raise ValueError('Download too large')
        return blob


def create_evidence(trace_file, output_file, fetcher=fetch_official, now=None):
    """Produce evidence only after trusted download, parsing and price audit.

    Injected fetcher is for unit tests only; production must use fetch_official.
    """
    trace=json.loads(Path(trace_file).read_text(encoding='utf-8'))
    displayed=trace.get('displayed_prices')
    if not isinstance(displayed,list) or not displayed: raise ValueError('Missing displayed prices')
    wanted=[(r['station_id'],r['fuel']) for r in displayed]
    out=Path(output_file)
    # A previous successful evidence file must never survive a failed refresh.
    out.unlink(missing_ok=True)
    blob=fetcher()
    rows=extract_prices(blob,wanted)
    timestamp=(now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    audit_prices(displayed,rows,source=OFFICIAL_SOURCE,retrieved_at=timestamp,now=now)
    result={'source':OFFICIAL_SOURCE,'retrieved_at':timestamp,
            'provenance_verified_by_adapter':True,'rows':rows}
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(out.suffix+'.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(out)
    return {'rows':len(rows),'output':str(out),'retrieved_at':timestamp}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--trace',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    print(json.dumps(create_evidence(args.trace,args.out),ensure_ascii=False))
