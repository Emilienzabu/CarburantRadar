"""Verified draft pipeline with bounded fallback on stale official prices only.

Each fallback redoes the real browser capture and independent official audit.
No publication, deployment or upload is performed.
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from capture_france import capture
from official_adapter import create_evidence
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


def _stale_official_price(exc):
    # Only the explicitly identified timestamp failure is eligible for fallback.
    # Mismatches, network errors, missing prices, and all other failures stop.
    return isinstance(exc, ValueError) and str(exc).startswith('Price timestamp stale or in future:')


def run_pipeline(city, fuel, output, *, insee=None, fallback_cities=None,
                 capturer=capture, evidence_maker=create_evidence,
                 validator=validate_capture, renderer=render, prober=probe_video):
    output = Path(output)
    if output.suffix.lower() != '.mp4':
        raise ValueError('Output must be an MP4')
    if not isinstance(city, str) or not city.strip():
        raise ValueError('City required')
    if fuel not in {'Gazole', 'SP95', 'SP98', 'E10', 'E85', 'GPLc'}:
        raise ValueError('Unknown fuel')
    fallbacks = list(fallback_cities or [])
    if len(fallbacks) > 3 or any(not isinstance(c, str) or not c.strip() for c in fallbacks):
        raise ValueError('Up to three nonempty fallback cities allowed')
    names = [city.strip()] + [c.strip() for c in fallbacks]
    if len(set(c.casefold() for c in names)) != len(names):
        raise ValueError('Duplicate city in fallback sequence')

    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    failures = []
    with tempfile.TemporaryDirectory(prefix='cr_v25_') as tmp:
        root = Path(tmp)
        for index, candidate in enumerate(names):
            folder = root / ('capture_' + str(index))
            folder.mkdir()
            # Never reuse any evidence or screenshot from a previous candidate.
            trace = capturer(candidate, fuel, str(folder), insee=insee if index == 0 else None)
            if not isinstance(trace, dict) or trace.get('verified_on_real_site') is not True:
                raise ValueError('Capture not verified on real site')
            trace_path = folder / 'trace.json'
            if not trace_path.is_file():
                raise ValueError('Capture trace missing')
            try:
                evidence_maker(trace_path, folder / 'official_evidence.json')
            except ValueError as exc:
                if _stale_official_price(exc):
                    failures.append({'city': candidate, 'reason': str(exc)})
                    print('V25: rejected stale-price candidate: ' + candidate + ': ' + str(exc), flush=True)
                    if index + 1 < len(names):
                        continue
                    raise ValueError('No verified city available; stale official prices: ' + '; '.join(x['city'] for x in failures)) from exc
                raise
            report = validator(folder)
            if report.get('ok') is not True:
                raise ValueError('Quality gate did not pass')
            staged = root / 'draft.mp4'
            renderer(folder, staged)
            if not staged.is_file() or staged.stat().st_size < 1024:
                raise ValueError('Render output missing or empty')
            media = prober(staged)
            partial = output.with_suffix('.mp4.partial')
            try:
                shutil.copyfile(staged, partial)
                partial.replace(output)
            finally:
                partial.unlink(missing_ok=True)
            return {'status': 'draft_only', 'publication_authorized': False,
                    'city': report['city'], 'fuel': report['fuel'],
                    'stations': report['stations'], 'quality': report['price_audit'],
                    'media': media, 'output': str(output),
                    'fallback_used': index > 0, 'attempted_cities': names[:index + 1],
                    'finished_at': datetime.now(timezone.utc).isoformat()}
    raise ValueError('No verified city available')


def main():
    parser = argparse.ArgumentParser(description='V25 verified draft-only video pipeline')
    parser.add_argument('--city', required=True)
    parser.add_argument('--fuel', default='Gazole')
    parser.add_argument('--insee')
    parser.add_argument('--fallback-city', action='append', default=[],
                        help='Try this city if the previous candidate has stale official prices; max 3')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = run_pipeline(args.city, args.fuel, args.out, insee=args.insee,
                          fallback_cities=args.fallback_city)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
