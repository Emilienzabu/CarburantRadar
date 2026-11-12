"""V27 read-only inventory of official price eligibility for a captured trace.

No station is silently removed from screenshots, trace, or published video.
No evidence JSON is created and this diagnostic never authorizes publication.
"""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from official_adapter import fetch_official, extract_prices
from price_audit import OFFICIAL_SOURCE, MAX_AGE, PRICE_TOLERANCE, parse_utc, _price


def diagnose(trace, official_rows, *, retrieved_at, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Current time must be timezone-aware')
    now = now.astimezone(timezone.utc)
    retrieved = parse_utc(retrieved_at)
    if retrieved > now + timedelta(minutes=5) or now - retrieved > timedelta(hours=24):
        raise ValueError('Official snapshot timestamp invalid')
    if trace.get('verified_on_real_site') is not True:
        raise ValueError('Capture is not verified on real site')
    displayed = trace.get('displayed_prices')
    if not isinstance(displayed, list) or not displayed:
        raise ValueError('Missing displayed prices')
    lookup = {}
    for row in official_rows:
        key = (str(row['station_id']).strip(), str(row['fuel']).strip())
        if key in lookup:
            raise ValueError('Duplicate official station/fuel')
        lookup[key] = row
    seen = set()
    entries = []
    for row in displayed:
        key = (str(row['station_id']).strip(), str(row['fuel']).strip())
        if not all(key) or key in seen:
            raise ValueError('Invalid or duplicate displayed station/fuel')
        seen.add(key)
        official = lookup.get(key)
        item = {'station_id': key[0], 'fuel': key[1]}
        if official is None:
            item['status'] = 'missing_official'
        else:
            updated = parse_utc(official['updated_at'])
            age = retrieved - updated
            item.update(official_updated_at=updated.isoformat(), age_hours=round(age.total_seconds()/3600, 2))
            try:
                mismatch = abs(_price(row['price']) - _price(official['price'])) > PRICE_TOLERANCE
            except ValueError:
                item['status'] = 'invalid_price'
            else:
                if mismatch:
                    item['status'] = 'price_mismatch'
                elif updated > retrieved + timedelta(minutes=5):
                    item['status'] = 'future'
                elif age > MAX_AGE:
                    item['status'] = 'stale'
                else:
                    item['status'] = 'eligible'
        entries.append(item)
    counts = {status: sum(e['status'] == status for e in entries)
              for status in ('eligible', 'stale', 'future', 'price_mismatch', 'missing_official', 'invalid_price')}
    return {'diagnostic_only': True, 'publication_authorized': False,
            'source': OFFICIAL_SOURCE, 'retrieved_at': retrieved.isoformat(),
            'max_age_hours': int(MAX_AGE.total_seconds()/3600),
            'all_displayed_prices_eligible': counts['eligible'] == len(entries),
            'counts': counts, 'stations': entries}


def run(trace_file, output_file):
    trace = json.loads(Path(trace_file).read_text(encoding='utf-8'))
    displayed = trace.get('displayed_prices')
    if not isinstance(displayed, list) or not displayed:
        raise ValueError('Missing displayed prices')
    wanted = [(r['station_id'], r['fuel']) for r in displayed]
    blob = fetch_official()
    rows = extract_prices(blob, wanted)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    report = diagnose(trace, rows, retrieved_at=retrieved_at)
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--trace', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = run(args.trace, args.out)
    print(json.dumps({'counts': report['counts'], 'all_displayed_prices_eligible': report['all_displayed_prices_eligible']}, ensure_ascii=False))
