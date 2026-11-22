import unittest
from geo_audit import audit_state, distance_km

class GeographicAuditTests(unittest.TestCase):
    def setUp(self):
        self.state={'lat':45.75,'lon':4.85,'fuel':'E10','radius':10,'stations':[{'lat':45.76,'lon':4.86},{'lat':45.77,'lon':4.87}]}
    def audit(self):return audit_state(self.state,45.75,4.85,'E10')
    def test_good(self):self.assertEqual(self.audit()['station_count_audited'],2)
    def test_haversine_zero(self):self.assertAlmostEqual(distance_km(45,4,45,4),0)
    def test_wrong_city(self):self.state['lat']=43.3;self.assertRaises(ValueError,self.audit)
    def test_wrong_fuel(self):self.state['fuel']='Gazole';self.assertRaises(ValueError,self.audit)
    def test_outside_radius(self):self.state['stations'][0]['lat']=46.2;self.assertRaises(ValueError,self.audit)
    def test_empty(self):self.state['stations']=[];self.assertRaises(ValueError,self.audit)
    def test_missing_coordinate(self):self.state['stations'][0]['lon']=None;self.assertRaises(ValueError,self.audit)
    def test_invalid_radius(self):self.state['radius']=100;self.assertRaises(ValueError,self.audit)
    def test_invalid_target(self):self.assertRaises(ValueError,audit_state,self.state,999,4.85,'E10')
    def test_nan(self):self.state['stations'][0]['lat']=float('nan');self.assertRaises(ValueError,self.audit)
    def test_missing_state(self):self.assertRaises(ValueError,audit_state,None,45.75,4.85,'E10')
    def test_no_fabricated_station(self):self.state['stations']=[{}];self.assertRaises(ValueError,self.audit)

if __name__=='__main__':unittest.main()
