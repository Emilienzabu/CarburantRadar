import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from render_verified import validate_capture_set, compose, ease

class Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
        self.manifest={'verified_on_real_site':True,'geolocation_verified_in_app':True,'source':'https://carburantradar.fr/france/','city_scenario':'Lyon','insee':'69123','fuel':'Gazole','geographic_audit':{'ok':True},'displayed_prices':[{'station_id':'123','price':1.8}], 'steps':[{'action':a,'bbox':{'x':10,'y':20,'width':100,'height':30}} for a in ('choose_fuel','locate','results')]}
        self.write()
        for f in ('01_carburant.png','02_localisation.png','03_resultats.png'):Image.new('RGB',(1170,2532)).save(self.p/f)
    def tearDown(self):self.t.cleanup()
    def write(self): (self.p/'trace.json').write_text(json.dumps(self.manifest),encoding='utf8')
    def test_valid(self):self.assertEqual(len(validate_capture_set(self.p)[1]),3)
    def test_not_live(self):self.manifest['verified_on_real_site']=False;self.write();self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_wrong_source(self):self.manifest['source']='https://example.com';self.write();self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_wrong_city(self):self.manifest['insee']='';self.write();self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_no_prices(self):self.manifest['displayed_prices']=[];self.write();self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_no_geo(self):self.manifest['geographic_audit']=None;self.write();self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_out_of_view(self):self.manifest['steps'][0]['bbox']['x']=900;self.write();self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_wrong_action(self):self.manifest['steps'][1]['action']='fake';self.write();self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_missing_file(self):(self.p/'02_localisation.png').unlink();self.assertRaises(FileNotFoundError,validate_capture_set,self.p)
    def test_low_resolution(self):Image.new('RGB',(720,1280)).save(self.p/'03_resultats.png');self.assertRaises(ValueError,validate_capture_set,self.p)
    def test_ease(self):self.assertEqual(ease(0),0);self.assertEqual(ease(1),1);self.assertAlmostEqual(ease(.5),.5)
    def test_composition(self):self.assertEqual(compose(Image.new('RGB',(1170,2532)),(200,300),1.2).size,(1080,1920))
if __name__=='__main__':unittest.main()
