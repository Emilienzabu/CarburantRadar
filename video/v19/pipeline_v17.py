"""V17 local orchestration: capture -> fresh official evidence -> audit -> draft MP4.

Read-only towards the site; NEVER uploads, publishes, or deploys.
Do not accept a pre-existing evidence JSON as proof: always fetch fresh evidence.
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from capture_france import capture
from official_adapter import create_evidence, fetch_official
from quality_gate import validate_capture
from render_verified import render


def probe_video(path, runner=subprocess.run):
    result = runner(['ffprobe', '-v', 'error', '-show_entries',
                     'stream=codec_type,codec_name,width,height,r_frame_rate',
                     '-show_entries', 'format=duration', '-of', 'json', str(path)],
                    capture_output=True, text=True, check=True, timeout=30)
    info = json.loads(result.stdout)
    streams = info.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if not video or (video.get('codec_name'), video.get('width'), video.get('height'), video.get('r_frame_rate')) != ('h264', 1080, 1920, '30/1'):
        raise ValueError('Nonconforming H.264 1080x1920 30 FPS video')
    if not audio or audio.get('codec_name') != 'aac':
        raise ValueError('Missing AAC audio track')
    duration = float(info.get('format', {}).get('duration', 0))
    if not 5.8 <= duration <= 6.3:
        raise ValueError('Incorrect duration')
    return {'video': 'h264', 'width': 1080, 'height': 1920, 'fps': 30, 'audio': 'aac', 'duration': duration}


def run_pipeline(city, fuel, output, *, insee=None, capturer=capture,
                 evidence_maker=create_evidence, validator=validate_capture,
                 renderer=render, prober=probe_video):
    """Fail closed: output is absent on any failure; capture/evidence are isolated.

    Injected functions exist solely for tests; production CLI uses real adapters.
    """
    output = Path(output)
    if output.suffix.lower() != '.mp4':
        raise ValueError('Output must be an MP4')
    if not city or not city.strip():
        raise ValueError('City required')
    if fuel not in {'Gazole', 'SP95', 'SP98', 'E10', 'E85', 'GPLc'}:
        raise ValueError('Unknown fuel')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='cr_v17_') as tmp:
        folder = Path(tmp) / 'captures'
        folder.mkdir()
        trace = capturer(city, fuel, str(folder), insee=insee)
        if not isinstance(trace, dict) or trace.get('verified_on_real_site') is not True:
            raise ValueError('Capture not verified on real site')
        trace_path = folder / 'trace.json'
        if not trace_path.is_file():
            raise ValueError('Capture trace missing')
        # Always fetch fresh official evidence; do not trust previously supplied JSON.
        evidence_maker(trace_path, folder / 'official_evidence.json')
        report = validator(folder)
        if report.get('ok') is not True:
            raise ValueError('Quality gate did not pass')
        staged = Path(tmp) / 'draft.mp4'
        renderer(folder, staged)
        if not staged.is_file() or staged.stat().st_size < 1024:
            raise ValueError('Render output missing or empty')
        media = prober(staged)
        # A draft remains a draft; no auto-publish. Atomic final move on same filesystem.
        shutil.copyfile(staged, output.with_suffix('.mp4.partial'))
        output.with_suffix('.mp4.partial').replace(output)
        return {'status': 'draft_only', 'publication_authorized': False,
                'city': report['city'], 'fuel': report['fuel'],
                'stations': report['stations'], 'quality': report['price_audit'],
                'media': media, 'output': str(output),
                'finished_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description='V17 verified read-only video pipeline')
    parser.add_argument('--city', required=True)
    parser.add_argument('--fuel', default='Gazole')
    parser.add_argument('--insee')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = run_pipeline(args.city, args.fuel, args.out, insee=args.insee)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
