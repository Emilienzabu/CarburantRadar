import io
import json
import unittest
from urllib.error import HTTPError, URLError

import geocoding
import preflight_v18


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


LYON = json.dumps([{'nom': 'Lyon', 'code': '69123', 'centre': {'coordinates': [4.8, 45.7]}}]).encode()


def scripted(errors):
    """Opener raising the given errors in order, then answering with Lyon."""
    pending = list(errors)
    calls = []
    def opener(url, timeout):
        calls.append(url)
        if pending:
            raise pending.pop(0)
        return Resp(LYON)
    return opener, calls


def http(code):
    return HTTPError('https://example.org', code, 'x', {}, io.BytesIO(b''))


class GeocodingRetryTests(unittest.TestCase):
    def test_retries_network_then_5xx_then_succeeds(self):
        opener, calls = scripted([URLError('reset'), http(503)])
        self.assertEqual(geocoding.resolve('Lyon', opener=opener, sleep=lambda s: None).code, '69123')
        self.assertEqual(len(calls), 3)

    def test_bounded_attempts(self):
        opener, calls = scripted([URLError('a'), URLError('b'), URLError('c'), URLError('d')])
        with self.assertRaises(URLError):
            geocoding.resolve('Lyon', opener=opener, sleep=lambda s: None)
        self.assertEqual(len(calls), 3)

    def test_permanent_http_error_not_retried(self):
        opener, calls = scripted([http(404)])
        with self.assertRaises(HTTPError):
            geocoding.resolve('Lyon', opener=opener, sleep=lambda s: None)
        self.assertEqual(len(calls), 1)

    def test_ambiguity_never_retried_nor_guessed(self):
        two = json.dumps([{'nom': 'Saint-Sauveur', 'code': '12345', 'centre': {'coordinates': [2.1, 44.2]}},
                          {'nom': 'Saint-Sauveur', 'code': '54321', 'centre': {'coordinates': [3.2, 45.3]}}]).encode()
        calls = []
        def opener(url, timeout):
            calls.append(url)
            return Resp(two)
        with self.assertRaisesRegex(ValueError, 'ambiguë'):
            geocoding.resolve('Saint-Sauveur', opener=opener, sleep=lambda s: None)
        self.assertEqual(len(calls), 1)

    def test_invalid_attempts_rejected(self):
        for bad in (0, 4, '3'):
            with self.assertRaises(ValueError):
                geocoding.resolve('Lyon', attempts=bad)

    def test_backoff_delays(self):
        opener, _ = scripted([URLError('a'), URLError('b')])
        delays = []
        geocoding.resolve('Lyon', opener=opener, sleep=delays.append)
        self.assertEqual(delays, [1, 2])


class PreflightRetryTests(unittest.TestCase):
    class Ok:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return preflight_v18.GEO
        def read(self, n): return b'[{}]'

    def checker_with(self, errors):
        pending = list(errors)
        def opener(req, timeout):
            if pending:
                raise pending.pop(0)
            return self.Ok()
        return lambda url: preflight_v18.check_url(url, opener=opener)

    def test_http_error_keeps_status(self):
        result = preflight_v18.check_url('https://example.org', lambda req, timeout: (_ for _ in ()).throw(http(503)))
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 503)

    def test_geocoder_503_is_retried(self):
        result = preflight_v18.check_geocoder(checker=self.checker_with([http(503)]), sleep=lambda s: None)
        self.assertTrue(result['ok'])
        self.assertEqual(result['attempts'], 2)

    def test_geocoder_network_error_is_retried(self):
        result = preflight_v18.check_geocoder(checker=self.checker_with([URLError('reset')]), sleep=lambda s: None)
        self.assertTrue(result['ok'])
        self.assertEqual(result['attempts'], 2)

    def test_geocoder_404_not_retried(self):
        result = preflight_v18.check_geocoder(checker=self.checker_with([http(404), http(404)]), sleep=lambda s: None)
        self.assertFalse(result['ok'])
        self.assertEqual(result['attempts'], 1)

    def test_geocoder_persistent_5xx_bounded_and_blocking(self):
        result = preflight_v18.check_geocoder(checker=self.checker_with([http(503)] * 5), sleep=lambda s: None)
        self.assertFalse(result['ok'])
        self.assertEqual(result['attempts'], 3)


if __name__ == '__main__':
    unittest.main()
