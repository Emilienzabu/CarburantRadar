"""Fail-closed verification of official fuel price evidence.

Evidence is supplied by an independently fetched, trusted official data adapter.
This module NEVER asserts that the evidence was fetched from an official source;
that claim must be established by the integration layer.
"""
from datetime import datetime, timezone, timedelta
from math import isfinite

OFFICIAL_SOURCE = 'https://donnees.roulez-eco.fr/opendata/instantane'
MAX_AGE = timedelta(days=6)
PRICE_TOLERANCE = 0.001  # EUR/L, independent of UI rounding


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError('Missing timestamp')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid timestamp') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('Timestamp must include UTC offset')
    return dt.astimezone(timezone.utc)


def _price(value):
    if isinstance(value, bool):
        raise ValueError('Invalid price')
    try:
        n = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid price') from exc
    if not isfinite(n) or not 0.1 <= n <= 5.0:
        raise ValueError('Invalid price range')
    return n


def audit_prices(displayed, official, *, source, retrieved_at, now=None):
    """Compare displayed station/fuel prices with independently fetched evidence.

    All displayed rows must match. Invalid, stale, and future timestamps fail
    closed; diagnostics identify the offending station without weakening limits.
    """
    if source != OFFICIAL_SOURCE:
        raise ValueError('Unapproved official evidence source')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Naive current time')
    now = now.astimezone(timezone.utc)
    retrieved = parse_utc(retrieved_at)
    if retrieved > now + timedelta(minutes=5) or now - retrieved > timedelta(hours=24):
        raise ValueError('Official evidence snapshot too old or in future')
    if not isinstance(displayed, list) or not displayed or not isinstance(official, list) or not official:
        raise ValueError('Missing price rows')
    lookup = {}
    for row in official:
        if not isinstance(row, dict):
            raise ValueError('Invalid official row')
        key = (str(row.get('station_id', '')).strip(), str(row.get('fuel', '')).strip())
        if not all(key) or key in lookup:
            raise ValueError('Missing/duplicate official station and fuel')
        lookup[key] = row
    seen = set()
    oldest = now
    for row in displayed:
        if not isinstance(row, dict):
            raise ValueError('Invalid displayed row')
        key = (str(row.get('station_id', '')).strip(), str(row.get('fuel', '')).strip())
        if not all(key) or key in seen:
            raise ValueError('Missing/duplicate displayed station and fuel')
        seen.add(key)
        evidence = lookup.get(key)
        if evidence is None:
            raise ValueError('Station/fuel not found in official evidence')
        shown = _price(row.get('price'))
        actual = _price(evidence.get('price'))
        if abs(shown - actual) > PRICE_TOLERANCE:
            raise ValueError('Price mismatch')
        updated = parse_utc(evidence.get('updated_at'))
        age = retrieved - updated
        if updated > retrieved + timedelta(minutes=5) or age > MAX_AGE:
            raise ValueError(
                'Price timestamp stale or in future: '
                f'station_id={key[0]!r}, fuel={key[1]!r}, '
                f'official_updated_at={updated.isoformat()}, '
                f'evidence_retrieved_at={retrieved.isoformat()}, '
                f'age_hours={age.total_seconds() / 3600:.2f}, '
                f'max_age_hours={MAX_AGE.total_seconds() / 3600:.0f}'
            )
        oldest = min(oldest, updated)
    return {'verified': True, 'rows_checked': len(seen),
            'oldest_official_price_at': oldest.isoformat(),
            'source': source, 'retrieved_at': retrieved.isoformat(),
            'max_price_age_hours': int(MAX_AGE.total_seconds() / 3600)}
