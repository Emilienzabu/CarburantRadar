import unittest
from preflight_v18 import check_url, check_binary, preflight

class Response:
    status=200
    def __init__(self,body=b'OK'):self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def geturl(self):return 'https://example.org/final'
    def read(self,n):return self.body[:n]

class Tests(unittest.TestCase):
    def test_success_url(self):
        self.assertTrue(check_url('https://example.org',lambda req,timeout:Response())['ok'])
    def test_empty_url(self):
        self.assertFalse(check_url('https://example.org',lambda req,timeout:Response(b''))['ok'])
    def test_failed_url(self):
        def fail(*args,**kwargs):raise OSError('blocked')
        self.assertIn('OSError',check_url('https://example.org',fail)['error'])
    def test_range_limited(self):
        self.assertEqual(check_url('https://example.org',lambda req,timeout:Response(b'a'*5000))['sample_bytes'],2048)
    def test_preflight_blocked(self):
        result=preflight(lambda url:{'ok':False},lambda name:{'ok':True})
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(result['publication_authorized'])
    def test_preflight_ok_never_claims_capture(self):
        result=preflight(lambda url:{'ok':True},lambda name:{'ok':True})
        self.assertEqual(result['status'],'prerequisites_available')
        self.assertFalse(result['real_site_capture_verified'])
        self.assertFalse(result['video_generated'])
    def test_checks_named(self):
        result=preflight(lambda url:{'ok':True},lambda name:{'ok':True})
        self.assertEqual(set(result['checks']),{'site_france','official_prices','french_geocoder','ffmpeg','ffprobe','playwright'})
    def test_bin_exists(self):
        self.assertTrue(check_binary('ffmpeg')['ok'])

if __name__=='__main__':unittest.main()
