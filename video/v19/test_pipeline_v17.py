import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from pipeline_v17 import run_pipeline, probe_video


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'video.mp4'
        self.calls = []

    def capture(self, city, fuel, folder, insee=None):
        self.calls.append(('capture', city, fuel, insee))
        Path(folder, 'trace.json').write_text('{}')
        return {'verified_on_real_site': True}

    def evidence(self, trace, output):
        self.calls.append(('evidence',))
        Path(output).write_text('{}')

    def gate(self, folder):
        self.calls.append(('gate',))
        return {'ok': True, 'city': 'Lyon', 'fuel': 'SP95', 'stations': 12, 'price_audit': {'verified': True}}

    def render(self, folder, out):
        self.calls.append(('render',))
        Path(out).write_bytes(b'x' * 2048)

    def probe(self, out):
        self.calls.append(('probe',))
        return {'video': 'h264'}

    def execute(self, **overrides):
        kwargs = dict(capturer=self.capture, evidence_maker=self.evidence,
                      validator=self.gate, renderer=self.render, prober=self.probe)
        fuel = overrides.pop('fuel', 'SP95')
        kwargs.update(overrides)
        return run_pipeline('Lyon', fuel, self.out, insee='69123', **kwargs)

    def test_happy_path(self):
        r = self.execute()
        self.assertEqual(r['status'], 'draft_only')
        self.assertFalse(r['publication_authorized'])
        self.assertEqual(self.out.stat().st_size, 2048)
        self.assertEqual([x[0] for x in self.calls], ['capture','evidence','gate','render','probe'])

    def test_city_not_hardcoded(self):
        self.execute()
        self.assertEqual(self.calls[0], ('capture','Lyon','SP95','69123'))

    def test_invalid_fuel(self):
        with self.assertRaises(ValueError): self.execute(fuel='INVALID')

    def test_capture_failure(self):
        with self.assertRaises(RuntimeError): self.execute(capturer=Mock(side_effect=RuntimeError('offline')))
        self.assertFalse(self.out.exists())

    def test_unverified_capture(self):
        with self.assertRaises(ValueError): self.execute(capturer=lambda *a, **k: {'verified_on_real_site': False})
        self.assertFalse(self.out.exists())

    def test_official_failure(self):
        with self.assertRaises(RuntimeError): self.execute(evidence_maker=Mock(side_effect=RuntimeError('feed offline')))
        self.assertFalse(self.out.exists())

    def test_quality_failure(self):
        with self.assertRaises(ValueError): self.execute(validator=Mock(side_effect=ValueError('price mismatch')))
        self.assertFalse(self.out.exists())

    def test_quality_not_ok(self):
        with self.assertRaises(ValueError): self.execute(validator=lambda folder: {'ok': False})
        self.assertFalse(self.out.exists())

    def test_render_failure(self):
        with self.assertRaises(RuntimeError): self.execute(renderer=Mock(side_effect=RuntimeError('ffmpeg')))
        self.assertFalse(self.out.exists())

    def test_probe_failure(self):
        with self.assertRaises(ValueError): self.execute(prober=Mock(side_effect=ValueError('wrong fps')))
        self.assertFalse(self.out.exists())

    def test_bad_extension(self):
        with self.assertRaises(ValueError): run_pipeline('Lyon','SP95',self.out.with_suffix('.avi'))

    def test_missing_city(self):
        with self.assertRaises(ValueError): run_pipeline('  ','SP95',self.out)

    def test_probe_valid(self):
        valid = {'streams': [{'codec_type':'video','codec_name':'h264','width':1080,'height':1920,'r_frame_rate':'30/1'},
                             {'codec_type':'audio','codec_name':'aac'}], 'format':{'duration':'6.01'}}
        runner = Mock(return_value=Mock(stdout=json.dumps(valid)))
        self.assertEqual(probe_video(self.out, runner=runner)['fps'],30)

    def test_probe_invalid_size(self):
        invalid = {'streams': [{'codec_type':'video','codec_name':'h264','width':720,'height':1280,'r_frame_rate':'30/1'},
                               {'codec_type':'audio','codec_name':'aac'}], 'format':{'duration':'6'}}
        with self.assertRaises(ValueError): probe_video(self.out, runner=Mock(return_value=Mock(stdout=json.dumps(invalid))))

    def test_probe_missing_audio(self):
        invalid = {'streams': [{'codec_type':'video','codec_name':'h264','width':1080,'height':1920,'r_frame_rate':'30/1'}], 'format':{'duration':'6'}}
        with self.assertRaises(ValueError): probe_video(self.out, runner=Mock(return_value=Mock(stdout=json.dumps(invalid))))


if __name__ == '__main__': unittest.main()
