# JelE Clipper setup: Light or Full. Run by the setup after the packages are installed.
#   light: nothing extra, the speech model downloads the first time it is needed
#   full:  graphics card support for the speech model (NVIDIA) and the speech models right away
import os, sys, json, shutil, subprocess, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data')
os.makedirs(DATA, exist_ok=True)


def say(*a):
    print(time.strftime('[%H:%M:%S]'), *a, flush=True)


def nvidia():
    smi = shutil.which('nvidia-smi') or os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'NVIDIA Corporation', 'NVSMI', 'nvidia-smi.exe')
    try:
        r = subprocess.run([smi, '--query-gpu=name', '--format=csv,noheader'], capture_output=True, text=True, timeout=20)
        return r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ''
    except Exception:
        return ''


def gpus():
    """AMD and Intel graphics cards (NVIDIA uses its own support)"""
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', '(Get-CimInstance Win32_VideoController).Name'], capture_output=True, text=True, timeout=30)
        return [x.strip() for x in r.stdout.splitlines() if x.strip() and any(k in x.lower() for k in ('radeon', 'amd', 'arc', 'intel(r) iris xe'))]
    except Exception:
        return []


def get(url, dst):
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'JelE-Clipper-Setup'})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst + '.part', 'wb') as fh:
        shutil.copyfileobj(r, fh, 1 << 20)
    os.replace(dst + '.part', dst)


def engine():
    """whisper.cpp with Vulkan and its speech model: the speech model on an AMD or Intel graphics card"""
    import zipfile
    d = os.path.join(HERE, 'engine', 'whisper_vulkan'); os.makedirs(d, exist_ok=True)
    z = os.path.join(d, 'engine.zip')
    get('https://github.com/JelE123/JelE-clipper/releases/download/engine-whisper-vulkan-1.9.5/whisper_vulkan_win64.zip', z)
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if n.endswith('/') or '..' in n: continue
            with zf.open(n) as src, open(os.path.join(d, os.path.basename(n)), 'wb') as dst: shutil.copyfileobj(src, dst)
    os.remove(z)
    m = os.path.join(DATA, 'models'); os.makedirs(m, exist_ok=True)
    say('Downloading the speech model for the graphics card (about 550 MB)')
    get('https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin', os.path.join(m, 'ggml-large-v3-turbo-q5_0.bin'))


def main():
    ed = (sys.argv[1] if len(sys.argv) > 1 else 'light').lower()
    info = {'edition': ed, 'at': time.time(), 'gpu': ''}
    ok = True
    if ed == 'full':
        gpu = nvidia(); info['gpu'] = gpu
        if gpu:
            say('NVIDIA graphics card:', gpu, '- installing graphics card support for the speech model')
            r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-warn-script-location', '--disable-pip-version-check',
                                'nvidia-cublas-cu12', 'nvidia-cudnn-cu12==9.*'])
            ok = r.returncode == 0
        else:
            other = gpus()
            if other:
                say('Graphics card:', ', '.join(other), '- installing graphics card support (Vulkan) for the speech model')
                try: engine(); info['gpu'] = ', '.join(other); info['engine'] = 'vulkan'
                except Exception as e: say('Graphics card support could not be installed:', e, '- you can install it later in Settings > Captions'); ok = False
            else:
                say('No graphics card found for the speech model: it runs on the processor')
        try:
            sys.path.insert(0, HERE)
            from faster_whisper.utils import download_model
            names = ['large-v3', 'small.en'] if gpu else ['large-v3-turbo', 'small.en']
            for n in names:
                say('Downloading speech model', n); download_model(n)
        except Exception as e:
            say('Downloading the speech models failed:', e, '- the Clipper downloads them when it needs them'); ok = False
    try:   # the packages are in: the launcher does not have to check them again at the first start
        import hashlib
        open(os.path.join(DATA, 'requirements.hash'), 'w').write(hashlib.sha1(open(os.path.join(HERE, 'requirements.txt'), 'rb').read()).hexdigest())
    except OSError: pass
    json.dump(info, open(os.path.join(DATA, 'install.json'), 'w', encoding='utf-8'), indent=2)
    say('Done:', ed)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
