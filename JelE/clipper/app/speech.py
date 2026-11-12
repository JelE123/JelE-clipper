# JelE Clipper part: speech to text. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- speech to text
_WHISPER = {}
LANG_TL = threading.local()   # a language for this one job (for example when you make a short again in another language)
def cur_lang(): return getattr(LANG_TL, 'v', None) or SET.get('language') or 'en'
def model_cached(name):
    hub = os.path.join(os.path.expanduser('~'), '.cache', 'huggingface', 'hub')
    key = name.replace('.', '-').replace('large-v3-turbo', 'large-v3-turbo')
    try: return any(key in d for d in os.listdir(hub))
    except OSError: return False

def whisper_ok():
    try:   # only look, do not load it: the model itself runs in the speech process
        import importlib.util
        return importlib.util.find_spec('faster_whisper') is not None
    except Exception:
        return False

def cuda_dlls():
    """graphics card support installed by the Full setup (nvidia pip packages): tell Windows where its files are"""
    if os.name != 'nt' or getattr(cuda_dlls, 'done', False): return
    cuda_dlls.done = True
    try:
        import site
        for sp in site.getsitepackages() + [site.getusersitepackages()]:
            for d in glob.glob(os.path.join(sp, 'nvidia', '*', 'bin')):
                try: os.add_dll_directory(d)
                except Exception: pass
                os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
    except Exception: pass

def has_cuda():
    cuda_dlls()
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False

CORES = os.cpu_count() or 4
_BAD_MODEL = set()
def speech_threads():
    """core limit: the speech model leaves cores free for your game, OBS and the app"""
    return max(2, min(16, CORES - 2 if CORES > 4 else CORES - 1))

def pick_model(purpose='captions', cuda=None):
    """auto: NVIDIA = large-v3. otherwise the processor: small.en to scan a whole stream (fast),
    large-v3-turbo for the captions of a short when the processor is strong enough (8+ cores)"""
    name = SET.get('whisper_model', 'auto')
    if cuda is None: cuda = has_cuda()
    if name == 'auto': name = 'large-v3' if cuda else ('large-v3-turbo' if purpose == 'captions' and CORES >= 8 else 'small.en')
    if name in _BAD_MODEL: name = 'medium.en' if purpose == 'captions' and 'medium.en' not in _BAD_MODEL else 'small.en'
    if cur_lang() != 'en': name = name.replace('.en', '')
    return name, cuda

def smaller_model(name, purpose):
    if name in ('small.en', 'small', 'base.en', 'base'): return None
    nxt = 'medium.en' if purpose == 'captions' and not name.startswith('medium') else 'small.en'
    return nxt if cur_lang() == 'en' else nxt.replace('.en', '')

def whisper_model(purpose='captions'):
    """the model inside the app itself: only used when the separate speech process cannot start"""
    from faster_whisper import WhisperModel
    name, cuda = pick_model(purpose)
    key = (name, cuda)
    thr = speech_threads()
    if key not in _WHISPER:
        log(f'Speech model "{name}" loading ({"graphics card" if cuda else "processor"}). The first time it gets downloaded, hang on.')
        prog('Loading the speech model' + ('' if model_cached(name) else ' (one-time download, ~1-2 GB)'))
        try: _WHISPER[key] = WhisperModel(name, device='cuda' if cuda else 'cpu', compute_type='float16' if cuda else 'int8', cpu_threads=thr)
        except Exception as e:
            if cuda:
                log('The graphics card does not work for the speech model, using the processor')
                name = name if name != 'large-v3' else 'small.en'; key = (name, False)
            else:
                log(f'Speech model "{name}" does not work ({str(e)[:80]}), picking another one'); _BAD_MODEL.add(name)
                name = 'medium.en' if purpose == 'captions' and name != 'medium.en' else 'small.en'; key = (name, False)
            if key not in _WHISPER: _WHISPER[key] = WhisperModel(name, device='cpu', compute_type='int8', cpu_threads=thr)
    return _WHISPER[key]

def total_ram_mb():
    try:
        if os.name == 'nt':
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [('len', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ('tot', 'avail', 'totpf', 'availpf', 'totv', 'availv', 'ext')]
            m = MS(); m.len = ctypes.sizeof(MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)): return int(m.tot / 1048576)
        else:
            return int(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1048576)
    except Exception: pass
    return 0

# ---------------------------------------------------------------- graphics card on any brand (AMD, Intel, NVIDIA) via whisper.cpp + Vulkan (plan F2.2)
WCPP_TAG = 'engine-whisper-vulkan-1.9.5'
WCPP_MODEL = 'ggml-large-v3-turbo-q5_0.bin'
WCPP = {'bad': False, 'busy': False, 'step': '', 'pct': 0, 'error': '', 'gpus': None}
def wcpp_dir(): return os.path.join(HERE, 'engine', 'whisper_vulkan')
def wcpp_exe():
    for n in ('whisper-cli.exe', 'whisper-cli'):
        p_ = os.path.join(wcpp_dir(), n)
        if os.path.exists(p_): return p_
    return None
def wcpp_model(): return os.path.join(DATA, 'models', WCPP_MODEL)
def wcpp_ready(): return bool(wcpp_exe()) and os.path.exists(wcpp_model()) and os.path.getsize(wcpp_model()) > 100e6
def gpu_names():
    """the graphics cards in this pc (Windows), for the choice in Settings"""
    if WCPP['gpus'] is None:
        WCPP['gpus'] = []
        if os.name == 'nt':
            try:
                r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', '(Get-CimInstance Win32_VideoController).Name'],
                                   capture_output=True, text=True, timeout=20, creationflags=NOWIN)
                WCPP['gpus'] = [x.strip() for x in r.stdout.splitlines() if x.strip() and 'basic' not in x.lower() and 'virtual' not in x.lower()]
            except Exception: pass
    return WCPP['gpus']
def use_wcpp():
    eng = SET.get('speech_engine', 'auto')
    if eng == 'cpu' or WCPP['bad'] or getattr(LIVE_TL, 'on', False) or not wcpp_ready(): return False   # during the stream: never on the graphics card
    return eng == 'gpu' or not has_cuda()
def wcpp_status():
    return {'ready': wcpp_ready(), 'busy': WCPP['busy'], 'step': WCPP['step'], 'pct': WCPP['pct'], 'error': WCPP['error'], 'gpus': gpu_names(),
            'engine': SET.get('speech_engine', 'auto'), 'cuda': has_cuda(), 'active': use_wcpp(), 'win': os.name == 'nt'}
def _download(url, dst, label, lo, hi):
    tmp = dst + '.part'
    req = urllib.request.Request(url, headers={'User-Agent': 'JelE-Clipper'})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as fh:
        total = int(r.headers.get('Content-Length') or 0); got = 0
        while True:
            b = r.read(1 << 20)
            if not b: break
            fh.write(b); got += len(b)
            if total: WCPP['pct'] = int(lo + (hi - lo) * got / total)
            WCPP['step'] = f'{label} ({got // 1048576} MB' + (f' of {total // 1048576} MB)' if total else ')')
    os.replace(tmp, dst)
def wcpp_install():
    """download the graphics card engine (about 10 MB) and its speech model (about 550 MB). runs in the background"""
    import zipfile
    if WCPP['busy']: return
    WCPP.update(busy=True, error='', pct=0, step='Starting')
    try:
        if os.name != 'nt': raise RuntimeError('this only works on Windows')
        repo = re.sub(r'^(https?://)?(www\.)?github\.com/', '', (SET.get('update_repo') or 'JelE123/JelE-clipper')).strip('/')
        os.makedirs(wcpp_dir(), exist_ok=True); os.makedirs(os.path.dirname(wcpp_model()), exist_ok=True)
        z = os.path.join(wcpp_dir(), 'engine.zip')
        _download(f'https://github.com/{repo}/releases/download/{WCPP_TAG}/whisper_vulkan_win64.zip', z, 'Downloading the graphics card engine', 0, 5)
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.endswith('/') or '..' in n: continue
                with zf.open(n) as src, open(os.path.join(wcpp_dir(), os.path.basename(n)), 'wb') as dst: shutil.copyfileobj(src, dst)
        os.remove(z)
        if not os.path.exists(wcpp_model()) or os.path.getsize(wcpp_model()) < 100e6:
            _download(f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{WCPP_MODEL}', wcpp_model(), 'Downloading the speech model', 5, 100)
        WCPP.update(step='Ready', pct=100, bad=False); log('Graphics card support for the speech model is installed')
    except Exception as e:
        WCPP['error'] = str(e)[:200]; log('Graphics card support could not be installed:', e)
    finally: WCPP['busy'] = False

class SpeechCrash(RuntimeError): pass
class SpeechProc:
    """the speech model in its own process (app/speechworker.py). It stays loaded between jobs (fast),
    runs at low priority with a core and memory limit, and when it crashes only that process stops:
    the app keeps going, notes it and starts a new one."""
    def __init__(self):
        self.p = None; self.q = None; self.lock = threading.Lock(); self.err = collections.deque(maxlen=40)
        self.broken = False; self.crashes = 0; self.memlimit = 0; self.cuda = None
    def alive(self): return bool(self.p and self.p.poll() is None)
    def _read(self, p, q):
        for ln in p.stdout:
            ln = ln.strip()
            if ln.startswith('{'):
                try: q.put(json.loads(ln))
                except ValueError: pass
        q.put(None)
    def _err(self, p):
        for ln in p.stderr:
            if ln.strip(): self.err.append(ln.rstrip()[:300])
    def start(self):
        import queue as _q
        if self.cuda is None: self.cuda = has_cuda()
        ram = total_ram_mb()
        mb = 0 if self.cuda or not ram else max(3000, int(ram * 0.6))   # on the processor: never more than 60% of your memory
        args = [sys.executable, '-u', os.path.join(HERE, 'app', 'speechworker.py')] + ([f'--memlimit={mb}'] if mb else [])
        self.err.clear()
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                  errors='replace', bufsize=1, cwd=HERE, creationflags=NOWIN | LOWPRIO_)
        self.q = _q.Queue()
        threading.Thread(target=self._read, args=(self.p, self.q), daemon=True).start()
        threading.Thread(target=self._err, args=(self.p,), daemon=True).start()
        try: m = self.q.get(timeout=90)
        except _q.Empty: m = None
        if not m or not m.get('hello'):
            self.stop(); raise SpeechCrash('the speech process did not start')
        self.memlimit = m.get('memlimit') or 0
        log(f'Speech process ready (pid {m.get("pid")}, low priority' + (f', max {self.memlimit // 1024} GB memory)' if self.memlimit else ')'))
    def stop(self):
        p, self.p = self.p, None
        if p:
            try: p.kill()
            except Exception: pass
    def run(self, req, on_prog=None):
        import queue as _q
        with self.lock:
            if not self.alive(): self.start()
            q = self.q
            self.p.stdin.write(json.dumps(req) + '\n'); self.p.stdin.flush()
            while True:
                try: m = q.get(timeout=2)
                except _q.Empty:
                    if STATE.get('cancel'): self.stop(); return None   # stopped by you: kill it right away
                    if not self.alive() and q.empty(): m = None
                    else: continue
                if m is not None and STATE.get('cancel'): self.stop(); return None
                if m is None:
                    self.crashes += 1; tail = ' | '.join(list(self.err)[-3:])
                    note_error('speech process', f'The speech process stopped (code {self.p.returncode if self.p else "?"}). {tail}')
                    self.stop(); raise SpeechCrash('the speech process stopped' + (f' ({tail[-160:]})' if tail else ''))
                if 'p' in m:
                    if on_prog: on_prog(m['p'])
                    continue
                return m
SPEECH = SpeechProc()

class _O:
    def __init__(self, d): self.__dict__.update(d)

def raw_transcribe(audio, wav, purpose, on_prog, mic):
    """the speech model's own output (segments with words). first choice: the separate speech process"""
    kw = dict(language=cur_lang() if cur_lang() != 'auto' else None, beam_size=5, word_timestamps=True, vad_filter=True,
              vad_parameters={'min_silence_duration_ms': 300, 'speech_pad_ms': 250, 'threshold': 0.4},
              condition_on_previous_text=False, no_speech_threshold=0.5, temperature=[0.0, 0.2, 0.4])
    own = [w.strip() for w in re.split(r'[,\n]+', SET.get('vocab') or '') if w.strip()]
    if use_wcpp() and not SPEECH.broken:   # graphics card of any brand
        base = gamewords.prompt_words(cur_game()) if gamewords else []
        req = {'cmd': 'wcpp', 'exe': wcpp_exe(), 'model_path': wcpp_model(), 'wav': wav, 'lang': cur_lang(), 'threads': speech_threads(),
               'prompt': ', '.join(base[-60:] + ['JelE'] + own)}
        try: m = SPEECH.run(req, on_prog)
        except SpeechCrash as e: m = {'err': 'fail', 'msg': str(e)}
        if m is None: return [], []
        if m.get('ok'):
            if not WCPP.get('said'): WCPP['said'] = True; log('The speech model runs on your graphics card')
            return [_O(dict(sg, words=[_O({'start': w[0], 'end': w[1], 'word': w[2], 'probability': w[3]}) for w in sg['words']])) for sg in m['segs']], []
        WCPP['bad'] = True; note_error('graphics card engine', m.get('msg') or '?')
        log('The graphics card engine did not work (' + (m.get('msg') or '?')[:120] + '). Using the processor from now on, the app keeps going.')
    if SET.get('speech_process', True) and not SPEECH.broken:
        name, cuda = pick_model(purpose, SPEECH.cuda)
        live = getattr(LIVE_TL, 'on', False)
        if live: name = 'small.en' if (SET.get('language') or 'en') == 'en' else 'small'   # during the stream: the light model, few cores
        base = gamewords.prompt_words(cur_game()) if gamewords else ['Valorant', 'Jett', 'Reyna', 'Raze', 'Sova', 'Omen', 'Killjoy', 'Vandal', 'Phantom', 'spike', 'defuse', 'ult']
        tries = 0
        while name and tries < 3:
            tries += 1
            if not (name, cuda) in getattr(SPEECH, 'loaded', set()):
                log(f'Speech model "{name}" loading ({"graphics card" if cuda else "processor"}). The first time it gets downloaded, hang on.')
                prog('Loading the speech model' + ('' if model_cached(name) else ' (one-time download, ~1-2 GB)'))
            req = {'cmd': 'transcribe', 'wav': wav, 'model': name, 'cuda': cuda, 'threads': max(2, CORES // 4) if live else speech_threads(), 'kw': kw,
                   'prompt_base': base, 'prompt_mine': ', '.join(['JelE'] + own)[-450:], 'vad': bool(mic)}
            try: m = SPEECH.run(req, on_prog)
            except SpeechCrash as e:
                if not SPEECH.p and 'did not start' in str(e):
                    log('The separate speech process does not start, using the speech model inside the app'); SPEECH.broken = True; break
                log(f'Speech model "{name}" stopped ({e}). Trying again with a lighter one, the app keeps running.')
                _BAD_MODEL.add(name); name = smaller_model(name, purpose); cuda = False if cuda and name else cuda
                continue
            if m is None: return [], []   # stopped
            if m.get('ok'):
                SPEECH.loaded = {(name, cuda)}
                return [_O(dict(sg, words=[_O({'start': w[0], 'end': w[1], 'word': w[2], 'probability': w[3]}) for w in sg['words']])) for sg in m['segs']], m.get('vad') or []
            if m.get('err') == 'load':
                if cuda: log('The graphics card does not work for the speech model, using the processor'); cuda = False; SPEECH.cuda = False
                else:
                    log(f'Speech model "{name}" does not work ({m.get("msg", "")[:80]}), picking another one'); _BAD_MODEL.add(name); name = smaller_model(name, purpose)
                continue
            if m.get('err') == 'memory':
                log(f'Speech model "{name}" needed too much memory, using a lighter one'); _BAD_MODEL.add(name); name = smaller_model(name, purpose); continue
            raise RuntimeError('Speech to text failed: ' + (m.get('msg') or '?'))
        if not SPEECH.broken: raise RuntimeError('The speech model keeps stopping on this pc. Pick a lighter model in Settings.')
    # fallback: the model inside the app
    model = whisper_model(purpose)
    kw['initial_prompt'] = vocab_prompt(model)
    try: segs, _ = model.transcribe(audio, hallucination_silence_threshold=1.0, **kw)
    except TypeError: segs, _ = model.transcribe(audio, **kw)       # older faster-whisper
    total = len(audio) / 16000.0
    out = []
    for sg in segs:
        if on_prog: on_prog(min(1.0, sg.end / max(1.0, total)))
        out.append(sg)
    vad = []
    if mic:
        try:
            from faster_whisper.vad import get_speech_timestamps, VadOptions
            vad = [(sp['start'] / 16000.0, sp['end'] / 16000.0) for sp in get_speech_timestamps(audio, VadOptions(threshold=0.55, min_speech_duration_ms=400, min_silence_duration_ms=300))]
        except Exception: pass
    return out, vad

VOICE_FILE = os.path.join(HERE, 'voicelines.txt')
_VL = {'t': 0, 'lines': []}
def voicelines():
    """lines from the game that should never become captions (announcer, agent lines). you can add your own in voicelines.txt"""
    try:
        m = os.path.getmtime(VOICE_FILE)
        if m != _VL['t']:
            _VL['lines'] = [norm_txt(l) for l in open(VOICE_FILE, encoding='utf-8') if l.strip() and not l.startswith('#')]; _VL['t'] = m
    except OSError: pass
    return _VL['lines']
def norm_txt(t): return re.sub(r'[^a-z0-9 ]', '', t.lower().replace('-', ' ')).strip()
def is_voiceline(text):
    import difflib
    t = norm_txt(text)
    if not t: return True
    for vl in voicelines():
        if not vl: continue
        if t == vl or (' ' in vl and vl in t and len(t) <= len(vl) + 12): return True
        if ' ' in vl and len(t.split()) <= 10 and difflib.SequenceMatcher(None, t, vl).ratio() > 0.82: return True
    return False

UNCLEAR = '\u2026'
PREVIEW_DIR = os.path.join(DATA, 'voorbeeld')   # shown as ... in the captions when you said something the model could not understand
UNSURE_TL = threading.local()   # words the model was not quite sure about (start times), for the yellow marks in the editor
def transcribe(wav, purpose='captions', on_prog=None):
    UNSURE_TL.v = []
    if not whisper_ok():
        log('faster-whisper is not installed, no captions'); return []
    # read the wav ourselves: newer PyAV versions break faster-whisper's own file reader
    import wave, numpy as np
    if not os.path.exists(wav): return []
    with wave.open(wav, 'rb') as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if len(audio) < 1600: return []
    segs, vad = raw_transcribe(audio, wav, purpose, on_prog, _WAVMIC.get(wav))
    words = []; dropped = 0; unclear = []   # unclear = (start, end) of speech the model could not turn into words
    for sg in segs:
        if getattr(sg, 'no_speech_prob', 0) > 0.7: continue
        txt = (sg.text or '').strip()
        # music: whisper marks it with notes or tags, lyrics are repetitive or very unsure
        if re.search(r'[\u266a\u266b]|\[(music|muziek|applause|laughter)|\((music|muziek)', txt, re.I) or getattr(sg, 'compression_ratio', 0) > 2.4 \
           or (getattr(sg, 'avg_logprob', 0) < -1.15 and getattr(sg, 'no_speech_prob', 0) > 0.3):
            if not re.search(r'[\u266a\u266b]|music|muziek', txt, re.I) and getattr(sg, 'compression_ratio', 0) <= 2.4 and sg.end - sg.start < 6:
                unclear.append((sg.start, sg.end))   # someone spoke, but it was too unclear to write down
            dropped += 1; continue
        if is_voiceline(txt): dropped += 1; continue
        for w in (sg.words or []):
            if getattr(w, 'probability', 1) < 0.2:   # not sure what was said: show that something was said
                if words and words[-1][2] == UNCLEAR and w.start - words[-1][1] < 0.6: words[-1] = (words[-1][0], round(w.end, 2), UNCLEAR)
                else: words.append((round(w.start, 2), round(w.end, 2), UNCLEAR))
                continue
            txt = w.word.strip()
            if not txt: continue
            if words and (txt[0] in "',.!?" or txt.lower() in ("'s", "'t", "'re", "'m", "'ll", "'ve", "'d")) and w.start - words[-1][1] < 0.15:
                words[-1] = (words[-1][0], w.end, words[-1][2] + txt); continue
            words.append((round(w.start, 2), round(w.end, 2), txt))
            if getattr(w, 'probability', 1) < 0.62: UNSURE_TL.v.append(round(w.start, 2))
    # with a mic-only track: speech the model skipped entirely also gets a "..."
    for a, b in vad:
        if b - a >= 0.5 and not any(w[0] < b and w[1] > a for w in words): unclear.append((a, min(b, a + 3)))
    for a, b in unclear:
        if not any(w[0] < b and w[1] > a for w in words): words.append((round(a, 2), round(b, 2), UNCLEAR))
    words.sort(key=lambda w: w[0])
    if dropped: log(f'{dropped} bits of game audio or music removed from the captions')
    return apply_fixes(words)
