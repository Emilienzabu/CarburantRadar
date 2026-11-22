"""V23 regression tests: diagnostics must not weaken freshness checks."""
import unittest
from datetime import datetime, timezone, timedelta
from price_audit import OFFICIAL_SOURCE, audit_prices

NOW = datetime(2026, 11, 12, 7, 0, tzinfo=timezone.utc)
RETRIEVED = NOW.isoformat()
DISPLAYED = [{'station_id': '12345678', 'fuel': 'Gazole', 'price': 1.729}]


def official(updated):
    return [{'station_id': '12345678', 'fuel': 'Gazole',
             'price': 1.729, 'updated_at': updated.isoformat()}]


def check(updated):
    return audit_prices(DISPLAYED, official(updated), source=OFFICIAL_SOURCE,
                        retrieved_at=RETRIEVED, now=NOW)


class V23PriceDiagnostics(unittest.TestCase):
    def test_recent_price_accepted(self):
        self.assertTrue(check(NOW - timedelta(hours=2))['verified'])

    def test_exact_six_day_limit_accepted(self):
        self.assertTrue(check(NOW - timedelta(days=6))['verified'])

    def test_stale_price_rejected_with_station_and_dates(self):
        with self.assertRaisesRegex(ValueError, 'station_id=') as err:
            check(NOW - timedelta(days=6, seconds=1))
        message = str(err.exception)
        for expected in ('12345678', 'Gazole', 'official_updated_at=',
                         'evidence_retrieved_at=', 'age_hours=', 'max_age_hours=144'):
            self.assertIn(expected, message)

    def test_future_price_rejected_with_diagnostic(self):
        with self.assertRaisesRegex(ValueError, 'station_id='):
            check(NOW + timedelta(minutes=6))

    def test_future_within_existing_tolerance_accepted(self):
        self.assertTrue(check(NOW + timedelta(minutes=5))['verified'])


if __name__ == '__main__':
    unittest.main()
