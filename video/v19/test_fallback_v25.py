import tempfile
import unittest
from pathlib import Path
from pipeline_v17 import run_pipeline


class FallbackV25Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'draft.mp4'
        self.events = []

    def capture(self, city, fuel, folder, insee=None):
        self.events.append(('capture', city, insee))
        Path(folder, 'trace.json').write_text('{}')
        return {'verified_on_real_site': True}

    def evidence(self, trace, output):
        city = next(x[1] for x in reversed(self.events) if x[0] == 'capture')
        self.events.append(('evidence', city))
        if city in self.fail_cities:
            raise self.fail_cities[city]
        Path(output).write_text('{}')

    def gate(self, folder):
        self.events.append(('gate',))
        return {'ok': True, 'city': self.events[-2][1], 'fuel': 'Gazole',
                'stations': 3, 'price_audit': {'verified': True}}

    def render(self, folder, out):
        self.events.append(('render',))
        Path(out).write_bytes(b'x' * 2048)

    def probe(self, path):
        self.events.append(('probe',))
        return {'video': 'h264'}

    def run_case(self, fallbacks=None):
        return run_pipeline('Lyon', 'Gazole', self.output,
                            insee='69123', fallback_cities=fallbacks,
                            capturer=self.capture, evidence_maker=self.evidence,
                            validator=self.gate, renderer=self.render, prober=self.probe)

    def test_fallback_recaptures_and_renders_only_valid_city(self):
        self.fail_cities = {'Lyon': ValueError('Price timestamp stale or in future: station_id=69007012')}
        result = self.run_case(['Marseille'])
        self.assertTrue(result['fallback_used'])
        self.assertEqual(result['city'], 'Marseille')
        self.assertEqual(result['attempted_cities'], ['Lyon', 'Marseille'])
        self.assertEqual([e for e in self.events if e[0] == 'capture'],
                         [('capture', 'Lyon', '69123'), ('capture', 'Marseille', None)])
        self.assertEqual([e[0] for e in self.events].count('render'), 1)
        self.assertTrue(self.output.exists())

    def test_all_stale_fail_closed(self):
        self.fail_cities = {c: ValueError('Price timestamp stale or in future: station_id=1')
                            for c in ['Lyon', 'Marseille']}
        with self.assertRaisesRegex(ValueError, 'No verified city available'):
            self.run_case(['Marseille'])
        self.assertFalse(self.output.exists())
        self.assertNotIn(('render',), self.events)

    def test_mismatch_does_not_fallback(self):
        self.fail_cities = {'Lyon': ValueError('Price mismatch')}
        with self.assertRaisesRegex(ValueError, 'Price mismatch'):
            self.run_case(['Marseille'])
        self.assertEqual([e for e in self.events if e[0] == 'capture'], [('capture', 'Lyon', '69123')])

    def test_network_error_does_not_fallback(self):
        self.fail_cities = {'Lyon': RuntimeError('feed offline')}
        with self.assertRaisesRegex(RuntimeError, 'feed offline'):
            self.run_case(['Marseille'])
        self.assertFalse(self.output.exists())

    def test_no_fallback_is_fail_closed(self):
        self.fail_cities = {'Lyon': ValueError('Price timestamp stale or in future: station_id=1')}
        with self.assertRaisesRegex(ValueError, 'No verified city available'):
            self.run_case()

    def test_valid_first_city_no_fallback(self):
        self.fail_cities = {}
        result = self.run_case(['Marseille'])
        self.assertFalse(result['fallback_used'])
        self.assertEqual(result['attempted_cities'], ['Lyon'])

    def test_duplicate_fallback_rejected(self):
        self.fail_cities = {}
        with self.assertRaisesRegex(ValueError, 'Duplicate city'):
            self.run_case(['lyon'])

    def test_too_many_fallbacks_rejected(self):
        self.fail_cities = {}
        with self.assertRaisesRegex(ValueError, 'Up to three'):
            self.run_case(['A', 'B', 'C', 'D'])


if __name__ == '__main__':
    unittest.main()
