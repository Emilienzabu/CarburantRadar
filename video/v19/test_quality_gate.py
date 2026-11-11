import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from datetime import datetime, timezone, timedelta
from price_audit import OFFICIAL_SOURCE
from quality_gate import validate_capture

class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        b={'x':20,'y':30,'width':100,'height':50}
        self.trace={'source':'https://carburantradar.fr/france/','verified_on_real_site':True,'geolocation_verified_in_app':True,'geographic_audit':{'verified':True,'station_count_audited':12},'city_scenario':'Marseille','fuel':'Gazole','steps':[{'action':'choose_fuel','bbox':b},{'action':'locate','bbox':b},{'action':'results','bbox':b,'stations_displayed':'12','minimum_displayed':'1,659 €','average_displayed':'1,699 €'}]}
        for f in ('01_carburant.png','02_localisation.png','03_resultats.png'): Image.new('RGB',(1170,2532)).save(self.root/f)
        self.trace['displayed_prices']=[{'station_id':'123','fuel':'Gazole','price':1.659}]
        self.evidence={'source':OFFICIAL_SOURCE,'provenance_verified_by_adapter':True,'retrieved_at':datetime.now(timezone.utc).isoformat(),'rows':[{'station_id':'123','fuel':'Gazole','price':1.659,'updated_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}]}
        (self.root/'official_evidence.json').write_text(json.dumps(self.evidence))
        self.save()
    def tearDown(self): self.tmp.cleanup()
    def save(self): (self.root/'trace.json').write_text(json.dumps(self.trace))
    def test_good(self): self.assertEqual(validate_capture(self.root)['stations'],12)
    def test_missing_evidence(self): (self.root/'official_evidence.json').unlink();self.assertRaises(ValueError,validate_capture,self.root)
    def test_false_provenance(self):
        self.evidence['provenance_verified_by_adapter']=False
        (self.root/'official_evidence.json').write_text(json.dumps(self.evidence))
        self.assertRaises(ValueError,validate_capture,self.root)
    def test_not_verified(self): self.trace['verified_on_real_site']=False;self.save();self.assertRaises(ValueError,validate_capture,self.root)
    def test_untrusted_source(self): self.trace['source']='https://other.com/';self.save();self.assertRaises(ValueError,validate_capture,self.root)
    def test_no_stations(self): self.trace['steps'][2]['stations_displayed']='0';self.save();self.assertRaises(ValueError,validate_capture,self.root)
    def test_missing_price(self): self.trace['steps'][2]['minimum_displayed']='—';self.save();self.assertRaises(ValueError,validate_capture,self.root)
    def test_missing_shot(self): (self.root/'03_resultats.png').unlink();self.assertRaises(ValueError,validate_capture,self.root)
    def test_low_resolution(self): Image.new('RGB',(390,844)).save(self.root/'01_carburant.png');self.assertRaises(ValueError,validate_capture,self.root)
    def test_out_of_frame(self): self.trace['steps'][0]['bbox']['x']=380;self.save();self.assertRaises(ValueError,validate_capture,self.root)
    def test_wrong_order(self): self.trace['steps'][0]['action']='results';self.save();self.assertRaises(ValueError,validate_capture,self.root)
    def test_corrupt_shot(self): (self.root/'02_localisation.png').write_bytes(b'garbage');self.assertRaises(Exception,validate_capture,self.root)

if __name__=='__main__':unittest.main()
