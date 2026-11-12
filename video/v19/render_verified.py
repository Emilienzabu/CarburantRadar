"""Render verified real-site captures into a draft MP4; never publish."""
import argparse
import json
import math
import subprocess
from pathlib import Path
from PIL import Image

STEPS = (('choose_fuel', '01_carburant.png'), ('locate', '02_localisation.png'), ('results', '03_resultats.png'))
ONBOARDING = ('continue_without_account', 'skip_tutorial')


def selected_steps(manifest):
    """Allow verified onboarding before the required, ordered camera actions."""
    steps = manifest.get('steps')
    if not isinstance(steps, list):
        raise ValueError('Incomplete action trace')
    idx = 0
    seen = set()
    while idx < len(steps) and isinstance(steps[idx], dict) and steps[idx].get('action') in ONBOARDING:
        step = steps[idx]
        action = step['action']
        if action in seen or step.get('verified') is not True:
            raise ValueError('Unverified or duplicate onboarding action')
        if action == 'continue_without_account' and 'skip_tutorial' in seen:
            raise ValueError('Onboarding actions out of order')
        seen.add(action)
        idx += 1
    chosen = steps[idx:]
    if len(chosen) != len(STEPS) or tuple(s.get('action') if isinstance(s, dict) else None for s in chosen) != tuple(a for a, _ in STEPS):
        raise ValueError('Unexpected action order')
    return chosen


def ease(t):
    t = max(0.0, min(1.0, float(t)))
    return t*t*t*(t*(t*6-15)+10)


def validate_capture_set(folder):
    folder = Path(folder)
    manifest = json.loads((folder/'trace.json').read_text(encoding='utf-8'))
    if manifest.get('verified_on_real_site') is not True or manifest.get('geolocation_verified_in_app') is not True:
        raise ValueError('Live-site and geolocation proofs required')
    if manifest.get('source') not in ('https://carburantradar.fr/france/', 'https://www.carburantradar.fr/france/'):
        raise ValueError('Untrusted screenshot source')
    if not manifest.get('city_scenario') or not manifest.get('insee'):
        raise ValueError('Missing city identity')
    if manifest.get('fuel') not in {'Gazole','SP95','SP98','E10','E85','GPLc'}:
        raise ValueError('Unknown fuel')
    steps = selected_steps(manifest)
    files=[]
    for (action,filename),step in zip(STEPS,steps):
        bbox=step.get('bbox') or {}
        if any(isinstance(bbox.get(k),bool) or not isinstance(bbox.get(k),(int,float)) or not math.isfinite(bbox[k]) for k in ('x','y','width','height')):
            raise ValueError('Invalid camera target')
        if bbox['width']<=0 or bbox['height']<=0 or bbox['x']<0 or bbox['y']<0:
            raise ValueError('Invisible camera target')
        file=folder/filename
        if not file.is_file(): raise FileNotFoundError(file)
        with Image.open(file) as im:
            im.verify()
        with Image.open(file) as im:
            if im.width < 1080 or im.height < 1920:
                raise ValueError('Screenshot resolution too low')
            if bbox['x']+bbox['width'] > im.width/3+1 or bbox['y']+bbox['height'] > im.height/3+1:
                raise ValueError('Target outside viewport')
        files.append(file)
    if not manifest.get('displayed_prices'):
        raise ValueError('No displayed prices verified')
    if not isinstance(manifest.get('geographic_audit'),dict):
        raise ValueError('Geographic audit missing')
    return manifest,files


def compose(im, center, zoom, size=(1080,1920)):
    ow,oh=size; sw,sh=im.size
    scale=min(ow/sw,oh/sh)*zoom
    tw,th=round(sw*scale),round(sh*scale)
    scaled=im.resize((tw,th),Image.Resampling.BICUBIC)
    canvas=Image.new('RGB',size,(19,24,33))
    cx,cy=center
    x=round(ow/2-cx*scale); y=round(oh/2-cy*scale)
    x=min(0,max(ow-tw,x)) if tw>=ow else (ow-tw)//2
    y=min(0,max(oh-th,y)) if th>=oh else (oh-th)//2
    canvas.paste(scaled,(x,y))
    return canvas


def render(folder,output,fps=30,seconds=6,zoom=1.25):
    if fps!=30 or seconds!=6 or not 1<=zoom<=1.4:
        raise ValueError('Unsupported render parameters')
    manifest,files=validate_capture_set(folder)
    images=[Image.open(p).convert('RGB') for p in files]
    targets=[]
    for step in selected_steps(manifest):
        b=step['bbox']; targets.append(((b['x']+b['width']/2)*3,(b['y']+b['height']/2)*3))
    keyframes=[(0,0,1.0),(.65,0,zoom),(1.4,0,zoom),(2.0,1,zoom),(3.3,1,zoom),(4.0,2,zoom),(5.25,2,zoom),(6,2,1.0)]
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    cmd=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24','-video_size','1080x1920','-framerate','30','-i','pipe:0','-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=44100','-t','6','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-shortest',str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for n in range(fps*seconds):
            t=n/fps
            for k in range(len(keyframes)-1):
                a,b=keyframes[k:k+2]
                if a[0]<=t<=b[0]: break
            f=ease((t-a[0])/(b[0]-a[0]))
            z=a[2]+(b[2]-a[2])*f
            ia,ib=a[1],b[1]
            if ia==ib:
                frame=compose(images[ia],targets[ia],z)
            else:
                ca=compose(images[ia],targets[ia],z)
                cb=compose(images[ib],targets[ib],z)
                frame=Image.blend(ca,cb,f)
            proc.stdin.write(frame.tobytes())
        proc.stdin.close(); err=proc.stderr.read(); ret=proc.wait()
        if ret: raise RuntimeError(err.decode(errors='replace'))
    finally:
        if proc.poll() is None: proc.kill()
        for im in images: im.close()
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--captures',required=True);p.add_argument('--out',required=True)
    args=p.parse_args();print(render(args.captures,args.out))
