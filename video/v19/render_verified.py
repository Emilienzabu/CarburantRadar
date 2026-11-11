"""Render only verified live-site captures, with measured camera targets.

No synthetic screenshot or price can pass this gate. This is a draft render,
never a permission to publish. ffmpeg and Pillow required.
"""
import argparse
import json
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageOps

STEPS = (('choose_fuel', '01_carburant.png'), ('locate', '02_localisation.png'), ('results', '03_resultats.png'))


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
    steps = manifest.get('steps')
    if not isinstance(steps,list) or len(steps)<3:
        raise ValueError('Incomplete action trace')
    files=[]
    for (action,filename),step in zip(STEPS,steps):
        if step.get('action') != action:
            raise ValueError('Unexpected action order')
        bbox=step.get('bbox') or {}
        if any(not isinstance(bbox.get(k),(int,float)) or not math.isfinite(bbox[k]) for k in ('x','y','width','height')):
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
            # capture_france uses 390x844 at DPR=3
            if bbox['x']+bbox['width'] > im.width/3+1 or bbox['y']+bbox['height'] > im.height/3+1:
                raise ValueError('Target outside viewport')
        files.append(file)
    if not manifest.get('displayed_prices'):
        raise ValueError('No displayed prices verified')
    if not isinstance(manifest.get('geographic_audit'),dict):
        raise ValueError('Geographic audit missing')
    return manifest,files


def compose(im, center, zoom, size=(1080,1920)):
    """At zoom 1, preserve entire phone screenshot; pan towards the measured target.
    Never add a dark mask over the app. Camera transforms are continuous.
    """
    ow,oh=size; sw,sh=im.size
    # Fill frame at zoom 1 while keeping entire image: narrow side margins.
    scale=min(ow/sw,oh/sh)*zoom
    tw,th=round(sw*scale),round(sh*scale)
    scaled=im.resize((tw,th),Image.Resampling.BICUBIC)
    canvas=Image.new('RGB',size,(19,24,33))
    # Keep focus in frame; at zoom=1 the center is naturally locked.
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
    for step in manifest['steps'][:3]:
        b=step['bbox']; targets.append(((b['x']+b['width']/2)*3,(b['y']+b['height']/2)*3))
    # Continuous pan and zoom; transitions are eased, never reset per scene.
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
            # Crossfade only near the scene change, preserving continuous camera focus.
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
