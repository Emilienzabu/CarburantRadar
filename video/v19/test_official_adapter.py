import json
import tempfile
import unittest
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime, timezone
from official_adapter import extract_prices, unpack_xml, create_evidence, parse_update

NOW=datetime(2026,11,11,12,0,tzinfo=timezone.utc)
XML=b'''<?xml version="1.0"?><pdv_liste><pdv id="123" latitude="4850000" longitude="230000"><prix nom="Gazole" valeur="1.729" maj="2026-11-10T10:00:00"/><prix nom="E10" valeur="1.650" maj="2026-11-10T10:00:00"/></pdv></pdv_liste>'''
def zip_xml(xml=XML):
 b=BytesIO()
 with ZipFile(b,'w',ZIP_DEFLATED) as z:z.writestr('PrixCarburants_instantane.xml',xml)
 return b.getvalue()

class OfficialAdapterTests(unittest.TestCase):
 def test_xml(self):
  r=extract_prices(XML,[('123','Gazole')]);self.assertEqual(r[0]['price'],1.729)
 def test_zip(self):self.assertEqual(extract_prices(zip_xml(),[('123','E10')])[0]['fuel'],'E10')
 def test_missing(self):
  with self.assertRaises(ValueError):extract_prices(XML,[('999','Gazole')])
 def test_wrong_fuel(self):
  with self.assertRaises(ValueError):extract_prices(XML,[('123','SP98')])
 def test_duplicate_requested(self):
  with self.assertRaises(ValueError):extract_prices(XML,[('123','E10'),('123','E10')])
 def test_duplicate_official(self):
  with self.assertRaises(ValueError):extract_prices(XML.replace(b'</pdv>',b'<prix nom="Gazole" valeur="1.729" maj="2026-11-10T10:00:00"/></pdv>'),[('123','Gazole')])
 def test_dtd(self):
  with self.assertRaises(ValueError):extract_prices(b'<!DOCTYPE foo><pdv_liste/>',[('123','Gazole')])
 def test_bad_root(self):
  with self.assertRaises(ValueError):extract_prices(b'<html/>',[('123','Gazole')])
 def test_zip_multiple(self):
  b=BytesIO()
  with ZipFile(b,'w') as z:z.writestr('a.xml',XML);z.writestr('b.xml',XML)
  with self.assertRaises(ValueError):unpack_xml(b.getvalue())
 def test_bad_date(self):
  with self.assertRaises(ValueError):parse_update('nonsense')
 def test_timezone(self):self.assertEqual(parse_update('2026-11-10T10:00:00'),'2026-11-10T09:00:00+00:00')
 def test_end_to_end(self):
  with tempfile.TemporaryDirectory() as td:
   trace=Path(td)/'trace.json';out=Path(td)/'official_evidence.json'
   trace.write_text(json.dumps({'displayed_prices':[{'station_id':'123','fuel':'Gazole','price':1.729}]}))
   result=create_evidence(trace,out,fetcher=lambda:zip_xml(),now=NOW)
   self.assertEqual(result['rows'],1);self.assertTrue(json.loads(out.read_text())['provenance_verified_by_adapter'])
 def test_failure_removes_previous_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   trace=Path(td)/'trace.json';out=Path(td)/'official_evidence.json'
   trace.write_text(json.dumps({'displayed_prices':[{'station_id':'123','fuel':'Gazole','price':1.729}]}))
   out.write_text('stale evidence')
   with self.assertRaises(ValueError):create_evidence(trace,out,fetcher=lambda:b'<bad/>',now=NOW)
   self.assertFalse(out.exists())
 def test_mismatch_never_writes(self):
  with tempfile.TemporaryDirectory() as td:
   trace=Path(td)/'trace.json';out=Path(td)/'official_evidence.json'
   trace.write_text(json.dumps({'displayed_prices':[{'station_id':'123','fuel':'Gazole','price':1.5}]}))
   with self.assertRaises(ValueError):create_evidence(trace,out,fetcher=lambda:XML,now=NOW)
   self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
