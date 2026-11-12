# JelE Clipper launcher: starts the Clipper without a black window and opens it in its own app window.
# It stays in the background as a small guard:
# - an icon next to the clock (Open, Clip now, Restart, Quit)
# - restarts the Clipper after an update, or when it stopped unexpectedly
# - a new version that does not start is put back to the previous one by itself
# Double-click the "JelE Clipper" shortcut. start.bat still works too, with the black window (handy for problems).
import os, sys, json, time, shutil, hashlib, threading, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
os.makedirs(DATA, exist_ok=True)
PORT = 8765
URL = f'http://localhost:{PORT}'
API = f'http://127.0.0.1:{PORT}'   # for our own checks: no IPv6 detour
LOG = os.path.join(DATA, 'clipper.log')
NOWIN = 0x08000000 if os.name == 'nt' else 0
RESTART = 75                      # exit code the Clipper uses for "start me again" (updates, going back)
STATE = {'proc': None, 'quit': False, 'tray': None}
QUIET = '--no-window' in sys.argv   # started by OBS: only the icon next to the clock, no window


def note(*a):
    try:
        with open(os.path.join(DATA, 'launcher.log'), 'a', encoding='utf-8') as fh:
            fh.write(time.strftime('[%Y-%m-%d %H:%M:%S] ') + ' '.join(str(x) for x in a) + '\n')
    except OSError:
        pass


def py(window=False):
    """pythonw (no window) next to the python that runs this launcher"""
    exe = sys.executable
    d = os.path.dirname(exe)
    w = os.path.join(d, 'pythonw.exe'); c = os.path.join(d, 'python.exe')
    if os.name == 'nt':
        return c if window and os.path.exists(c) else (w if os.path.exists(w) else exe)
    return exe


def running():
    try:
        urllib.request.urlopen(API + '/api/status', timeout=1.5).read(); return True
    except Exception:
        return False


def call(path, body=None):
    try:
        req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=5).read() or b'{}')
    except Exception:
        return {}


def deps():
    """install new packages only when requirements.txt changed (keeps the start fast)"""
    req = os.path.join(HERE, 'requirements.txt'); mark = os.path.join(DATA, 'requirements.hash')
    try: h = hashlib.sha1(open(req, 'rb').read()).hexdigest()
    except OSError: return
    try:
        if open(mark).read().strip() == h: return
    except OSError: pass
    note('installing packages')
    r = subprocess.run([py(True), '-m', 'pip', 'install', '-q', '--disable-pip-version-check', '-r', req], cwd=HERE, creationflags=NOWIN, capture_output=True, text=True)
    if r.returncode == 0:
        open(mark, 'w').write(h)
    else:
        note('pip failed', (r.stderr or '')[-400:])


def find_browser():
    pf = [os.environ.get(k) for k in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA') if os.environ.get(k)]
    for rel in (r'Microsoft\Edge\Application\msedge.exe', r'Google\Chrome\Application\chrome.exe', r'BraveSoftware\Brave-Browser\Application\brave.exe'):
        for base in pf:
            p = os.path.join(base, rel)
            if os.path.exists(p): return p
    return shutil.which('msedge') or shutil.which('google-chrome') or shutil.which('chromium')


def open_window():
    """the Clipper in its own window, without tabs or an address bar (Edge app mode, on every Windows pc)"""
    b = find_browser()
    if b:
        prof = os.path.join(DATA, 'venster')
        try:
            subprocess.Popen([b, f'--app={URL}', f'--user-data-dir={prof}', '--window-size=1440,920', '--no-first-run',
                              '--no-default-browser-check', '--disable-features=Translate'], creationflags=NOWIN)
            return
        except OSError:
            pass
    import webbrowser
    webbrowser.open(URL)


def start_clipper():
    try:   # keep the log of the previous run
        if os.path.exists(LOG) and os.path.getsize(LOG) > 0: os.replace(LOG, LOG.replace('.log', '_vorige.log'))
    except OSError:
        pass
    env = dict(os.environ, JELE_LAUNCHER='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    args = [py(), os.path.join(HERE, 'clipper.py'), '--no-browser'] + [a for a in sys.argv[1:] if a.startswith('--') and a != '--no-window']
    fh = open(LOG, 'a', encoding='utf-8', errors='replace')
    p = subprocess.Popen(args, cwd=HERE, env=env, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=NOWIN)
    fh.close()
    STATE['proc'] = p; note('clipper started, pid', p.pid)
    return p


def wait_ready(limit=60):
    t0 = time.time()
    while time.time() - t0 < limit:
        if running(): return True
        p = STATE['proc']
        if p and p.poll() is not None: return False
        time.sleep(0.3)
    return running()


def guard():
    """keeps the Clipper running: restart after an update, put the old version back when a new one does not start"""
    crashes = []
    while not STATE['quit']:
        p = start_clipper(); t0 = time.time()
        code = p.wait()
        if STATE['quit']: break
        note('clipper stopped, code', code)
        if code == RESTART:
            deps(); continue
        if code == 0: break                   # closed on purpose
        if os.path.exists(os.path.join(DATA, 'update_pending.json')) and time.time() - t0 < 90:
            note('new version does not start, going back')
            subprocess.run([py(), os.path.join(HERE, 'herstel.py')], cwd=HERE, creationflags=NOWIN)
            continue
        crashes = [c for c in crashes if time.time() - c < 300] + [time.time()]
        if len(crashes) > 3:
            note('stopped 4 times in 5 minutes, giving up'); show_problem(); break
        time.sleep(2)
    STATE['quit'] = True
    stop_tray()


def show_problem():
    """the Clipper keeps stopping: open the log so you can see why (and send it along)"""
    try:
        if os.name == 'nt': os.startfile(LOG)
    except OSError:
        pass


# ---------------------------------------------------------------- icon next to the clock
def tray():
    try:
        import pystray
        from PIL import Image
    except Exception:
        note('no tray icon (pystray not installed)'); return
    img = Image.open(os.path.join(HERE, 'icon.png'))

    def quit_(icon, item):
        STATE['quit'] = True
        call('/api/quit', {})
        p = STATE['proc']
        if p:
            try: p.wait(8)
            except Exception:
                try: p.kill()
                except Exception: pass
        icon.stop()

    def restart(icon, item):
        call('/api/quit', {'restart': True})

    def clip(icon, item):
        r = call('/api/clip')
        try: icon.notify('Clip marked' if r.get('ok') else 'Nothing marked: you are not recording', 'JelE Clipper')
        except Exception: pass

    menu = pystray.Menu(pystray.MenuItem('Open', lambda i, it: open_window(), default=True),
                        pystray.MenuItem('Clip now', clip),
                        pystray.MenuItem('Log', lambda i, it: show_problem()),
                        pystray.Menu.SEPARATOR,
                        pystray.MenuItem('Restart', restart),
                        pystray.MenuItem('Quit', quit_))
    icon = pystray.Icon('jele_clipper', img, 'JelE Clipper', menu)
    STATE['tray'] = icon
    icon.run()


def stop_tray():
    t = STATE['tray']
    if t:
        try: t.stop()
        except Exception: pass


def main():
    if running():                # already running: only open the window
        if not QUIET: open_window()
        return
    if not os.path.exists(os.path.join(DATA, 'requirements.hash')): deps()   # first start: the packages must be there before the Clipper runs
    g = threading.Thread(target=guard, daemon=True); g.start()
    if wait_ready():
        if not QUIET: open_window()
    else:
        note('clipper did not start within 60 s'); show_problem()
    deps()                       # new packages after an update, while you already work
    if not STATE['quit']: tray()                       # blocks until Quit (or returns at once without pystray)
    g.join()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        note(traceback.format_exc())
