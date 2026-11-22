import unittest
from datetime import datetime, timezone, timedelta
from diagnose_station_prices_v27 import diagnose

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


def row(station, age_hours, price=1.7):
    return {'station_id': station, 'fuel': 'Gazole', 'price': price,
            'updated_at': (NOW - timedelta(hours=age_hours)).isoformat()}


class StationDiagnosticsV27(unittest.TestCase):
    def setUp(self):
        self.trace = {'verified_on_real_site': True, 'displayed_prices': [
            {'station_id': '1', 'fuel': 'Gazole', 'price': 1.7},
            {'station_id': '2', 'fuel': 'Gazole', 'price': 1.7}]}

    def check(self, rows):
        return diagnose(self.trace, rows, retrieved_at=NOW.isoformat(), now=NOW)

    def test_all_eligible(self):
        r = self.check([row('1', 24), row('2', 144)])
        self.assertTrue(r['all_displayed_prices_eligible'])
        self.assertEqual(r['counts']['eligible'], 2)

    def test_stale_does_not_stop_inventory(self):
        r = self.check([row('1', 145), row('2', 2)])
        self.assertEqual(r['counts']['stale'], 1)
        self.assertEqual(r['counts']['eligible'], 1)
        self.assertFalse(r['publication_authorized'])

    def test_future(self):
        self.assertEqual(self.check([row('1', -1), row('2', 2)])['counts']['future'], 1)

    def test_mismatch(self):
        self.assertEqual(self.check([row('1', 2, 1.8), row('2', 2)])['counts']['price_mismatch'], 1)

    def test_missing(self):
        self.assertEqual(self.check([row('1', 2)])['counts']['missing_official'], 1)

    def test_duplicate_displayed(self):
        self.trace['displayed_prices'].append(self.trace['displayed_prices'][0])
        with self.assertRaises(ValueError): self.check([row('1', 2), row('2', 2)])

    def test_unverified_capture(self):
        self.trace['verified_on_real_site'] = False
        with self.assertRaises(ValueError): self.check([row('1', 2), row('2', 2)])

    def test_invalid_price(self):
        self.trace['displayed_prices'][0]['price'] = 'not a price'
        self.assertEqual(self.check([row('1', 2), row('2', 2)])['counts']['invalid_price'], 1)


if __name__ == '__main__': unittest.main()
