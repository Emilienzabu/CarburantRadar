import unittest
from datetime import datetime, timezone, timedelta
from price_audit import audit_prices, OFFICIAL_SOURCE

NOW=datetime(2026,11,11,12,0,tzinfo=timezone.utc)
SNAP='2026-11-11T11:00:00+00:00'
D=[{'station_id':'123','fuel':'Gazole','price':1.729}]
O=[{'station_id':'123','fuel':'Gazole','price':1.729,'updated_at':'2026-11-10T10:00:00+00:00'}]

def audit(d=None,o=None,**kw):
    return audit_prices(D if d is None else d,O if o is None else o,
      source=kw.pop('source',OFFICIAL_SOURCE),retrieved_at=kw.pop('retrieved_at',SNAP),now=kw.pop('now',NOW))

class PriceAuditTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(audit()['rows_checked'],1)
    def test_missing_station(self):
        with self.assertRaises(ValueError): audit([{'station_id':'999','fuel':'Gazole','price':1.729}])
    def test_wrong_fuel(self):
        with self.assertRaises(ValueError): audit([{'station_id':'123','fuel':'E10','price':1.729}])
    def test_wrong_price(self):
        with self.assertRaises(ValueError): audit([{'station_id':'123','fuel':'Gazole','price':1.75}])
    def test_stale_price(self):
        with self.assertRaises(ValueError): audit(o=[dict(O[0],updated_at='2026-11-01T00:00:00Z')])
    def test_future_price(self):
        with self.assertRaises(ValueError): audit(o=[dict(O[0],updated_at='2026-11-12T00:00:00Z')])
    def test_wrong_source(self):
        with self.assertRaises(ValueError): audit(source='https://example.org')
    def test_old_snapshot(self):
        with self.assertRaises(ValueError): audit(retrieved_at='2026-11-09T00:00:00Z')
    def test_naive_time(self):
        with self.assertRaises(ValueError): audit(o=[dict(O[0],updated_at='2026-11-10T10:00:00')])
    def test_duplicate_evidence(self):
        with self.assertRaises(ValueError): audit(o=O+O)
    def test_duplicate_displayed(self):
        with self.assertRaises(ValueError): audit(d=D+D)
    def test_empty(self):
        with self.assertRaises(ValueError): audit(d=[])
    def test_nan(self):
        with self.assertRaises(ValueError): audit(d=[dict(D[0],price=float('nan'))])
    def test_invalid_price_range(self):
        with self.assertRaises(ValueError): audit(d=[dict(D[0],price=0)])
    def test_near_tolerance(self):
        self.assertTrue(audit(d=[dict(D[0],price=1.7295)])['verified'])
    def test_timezone_offset(self):
        self.assertTrue(audit(o=[dict(O[0],updated_at='2026-11-10T11:00:00+01:00')])['verified'])
    def test_snapshot_future(self):
        with self.assertRaises(ValueError): audit(retrieved_at='2026-11-12T00:00:00Z')
    def test_invalid_official_price(self):
        with self.assertRaises(ValueError): audit(o=[dict(O[0],price='not a price')])

if __name__=='__main__': unittest.main()
