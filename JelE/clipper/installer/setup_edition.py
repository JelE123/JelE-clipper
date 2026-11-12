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
            say('No NVIDIA graphics card found: the speech model runs on the processor')
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
