import io
import json
import unittest
from geocoding import parse_communes, resolve
from capture_france import validate

class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

class GeoTests(unittest.TestCase):
    def setUp(self):
        self.data=[{'nom':'Saint-Sauveur','code':'12345','centre':{'coordinates':[2.1,44.2]}},
                   {'nom':'Saint-Sauveur','code':'54321','centre':{'coordinates':[3.2,45.3]}}]
    def test_ambiguity(self):
        with self.assertRaisesRegex(ValueError,'ambiguë'): parse_communes(self.data,'Saint-Sauveur')
    def test_insee(self):
        self.assertEqual(parse_communes(self.data,'Saint-Sauveur','54321').latitude,45.3)
    def test_case(self):
        self.assertEqual(parse_communes([self.data[0]],'saint-sauveur').code,'12345')
    def test_missing(self):
        with self.assertRaises(ValueError): parse_communes(self.data,'Nice')
    def test_invalid_coordinates(self):
        d=[{'nom':'Lyon','code':'69123','centre':{'coordinates':['x',45]}}]
        with self.assertRaises(ValueError): parse_communes(d,'Lyon')
    def test_outside(self):
        d=[{'nom':'Paris','code':'75056','centre':{'coordinates':[120,45]}}]
        with self.assertRaises(ValueError): parse_communes(d,'Paris')
    def test_api_mock(self):
        def opener(url,timeout):
            self.assertIn('nom=Lyon',url)
            return Response(json.dumps([{'nom':'Lyon','code':'69123','centre':{'coordinates':[4.8,45.7]}}]).encode())
        self.assertEqual(resolve('Lyon',opener=opener).code,'69123')
    def test_bad_insee(self):
        with self.assertRaises(ValueError): resolve('Lyon','bad')
    def test_no_fixed_city_list(self):
        def opener(url,timeout):
            return Response(json.dumps([{'nom':'Quimper','code':'29232','centre':{'coordinates':[-4.1,48]}}]).encode())
        self.assertEqual(resolve('Quimper',opener=opener).nom,'Quimper')
    def test_bad_fuel(self):
        with self.assertRaises(ValueError): validate('Diesel')
    def test_bad_domain(self):
        with self.assertRaises(ValueError): validate('Gazole','https://evil.test/france/')

if __name__=='__main__': unittest.main()
