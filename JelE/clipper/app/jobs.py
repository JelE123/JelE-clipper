# JelE Clipper part: job queue. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- job queue
import queue
RIJ_F = os.path.join(DATA, 'rij.json')

class _State(dict):
    """shared app state; job, cancel, why and proc belong to the worker thread that runs the job (two can run at once)"""
    LOCAL = ('job', 'cancel', 'why', 'proc')
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._tl = threading.local(); self._jobs = {}
    def _d(self):
        d = getattr(self._tl, 'd', None)
        if d is None: d = self._tl.d = {}
        return d
    def jobs(self): return [j for j in list(self._jobs.values()) if j]
    def get(self, k, default=None):
        if k in self.LOCAL:
            d = self._d()
            if k == 'job': return d.get('job') if 'job' in d else (self.jobs() or [None])[0]
            if k == 'cancel': return bool(d.get('cancel') or (d.get('job') or {}).get('cancel'))
            return d.get(k, default)
        return super().get(k, default)
    def __getitem__(self, k):
        if k in self.LOCAL: return self.get(k)
        return super().__getitem__(k)
    def __setitem__(self, k, v):
        if k in self.LOCAL:
            self._d()[k] = v
            if k == 'job':
                tid = threading.get_ident()
                if v: self._jobs[tid] = v
                else: self._jobs.pop(tid, None)
            return
        super().__setitem__(k, v)

class JobQueue(queue.Queue):
    """a normal queue that also keeps a readable list of what is waiting, and saves itself so it survives a restart"""
    TITLES = {'remux': 'Converting the recording to MP4', 'proxy': 'Making a working copy'}
    def __init__(self):
        super().__init__(); self.pending = []; self.waiting = {}; self.items = []; self.running = {}; self.glock = threading.Lock(); self.slock = threading.Lock()
    def meta(self, kind, arg):
        if kind == 'render': return {'kind': kind, 'title': ('Preview: ' if arg.get('preview') else '') + (arg.get('hook') or arg.get('title') or ''), 'layout': arg.get('layout'), 'len': round(float(arg['end']) - float(arg['start'])), 'preview': bool(arg.get('preview'))}
        if kind == 'download': return {'kind': kind, 'title': arg.get('url', '')[:60]}
        if kind == 'analyse':
            try: t = load_sess(arg).get('title') or ''
            except Exception: t = ''
            return {'kind': kind, 'title': t}
        return {'kind': kind, 'title': self.TITLES.get(kind, '')}
    def put(self, item, *a, **k):
        kind, arg = item
        with self.slock: self.pending.append(self.meta(kind, arg)); self.items.append(item)
        super().put(item, *a, **k); self.save()
    def get(self, *a, **k):
        with self.glock:
            while True:
                item = super().get(*a, **k)
                with self.slock:
                    meta = self.pending.pop(0) if self.pending else {}
                    if self.items: self.items.pop(0)
                if not meta.get('skip'):
                    self.running[threading.get_ident()] = item; self.save(); return item
                self.save()
    def done(self):
        self.running.pop(threading.get_ident(), None); self.save()
    def put_front(self, item):
        """a quick preview goes before everything else"""
        kind, arg = item
        with self.slock: self.pending.insert(0, self.meta(kind, arg)); self.items.insert(0, item)
        with self.mutex:
            self.queue.appendleft(item); self.unfinished_tasks += 1; self.not_empty.notify()
    def remove(self, i):
        with self.slock:
            if 0 <= i < len(self.pending): self.pending[i]['skip'] = True
        self.save()
    def save(self):
        try:
            with self.slock:
                keep = list(self.running.values()) + [it for it, m in zip(self.items, self.pending) if not m.get('skip')]
            keep = [(kd, ag) for kd, ag in keep if not (isinstance(ag, dict) and ag.get('test'))]
            tmp = RIJ_F + '.tmp'; json.dump(keep, open(tmp, 'w', encoding='utf-8')); os.replace(tmp, RIJ_F)
        except Exception: pass
    def restore(self):
        try: items = json.load(open(RIJ_F, encoding='utf-8'))
        except Exception: return 0
        n = 0
        for kd, ag in items:
            try:
                if kd in ('analyse', 'remux', 'proxy'): load_sess(ag)
                elif kd == 'render': load_sess(ag['sid'])
                self.put((kd, ag)); n += 1
            except Exception: pass
        if n: log(f'The queue picks up where it was ({n} jobs)')
        return n

JOBS = JobQueue(); STATE = _State({'job': None, 'done': [], 'previews': {}})
ANALYSE_LOCK = threading.Lock()   # whisper is heavy: only one stream is analysed at a time

def is_live(): return bool(CUR['id'] or STATE.get('live'))
_CPU = {'last': None, 'hist': collections.deque(maxlen=3)}
def cpu_sample():
    """how busy the whole pc is (0-100), measured between two calls"""
    try:
        if os.name == 'nt':
            import ctypes
            i, k, u = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u)): return None
            idle, total = i.value, k.value + u.value   # kernel time includes idle time
        else:
            v = [int(x) for x in open('/proc/stat').readline().split()[1:]]
            idle, total = v[3] + (v[4] if len(v) > 4 else 0), sum(v)
    except Exception: return None
    last, _CPU['last'] = _CPU['last'], (idle, total)
    if not last or total <= last[1]: return None
    return round(100 * (1 - (idle - last[0]) / (total - last[1])))

def guard_loop():
    """measures every 5 seconds how busy the pc is, for pc_busy()"""
    while True:
        c = cpu_sample()
        if c is not None: _CPU['hist'].append(c)
        time.sleep(5)

_HOT = {'at': 0, 't': None}
def gpu_temp():
    """the graphics card's temperature in °C when it can be read (NVIDIA via nvidia-smi, else None). measured at most every 20 s"""
    if time.time() - _HOT['at'] < 20: return _HOT['t']
    _HOT['at'] = time.time(); t = None
    try:
        exe = shutil.which('nvidia-smi')
        if exe:
            r = subprocess.run([exe, '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=4, creationflags=NOWIN)
            vals = [int(x) for x in re.findall(r'\d+', r.stdout or '')]
            t = max(vals) if vals else None
        elif os.path.exists('/sys/class/drm'):
            for f in glob.glob('/sys/class/drm/card*/device/hwmon/hwmon*/temp1_input'):
                try: t = max(t or 0, int(open(f).read().strip()) // 1000)
                except Exception: pass
    except Exception: t = None
    _HOT['t'] = t; return t
def pc_hot(): return (gpu_temp() or 0) >= int(SET.get('hot_limit') or 85)

def pc_busy():
    """the pc is already at its limit (a heavy game, an export): new heavy work waits a moment.
    only counts when none of our own work is running, so the clipper never waits for itself"""
    h = list(_CPU['hist'])
    return bool(len(h) >= 3 and min(h) >= 92 and not STATE.jobs())

_DISK = {'at': 0, 'low': False}
def disk_low(limit_gb=2.0):
    """less than 2 GB free where the shorts or the sessions go: wait instead of breaking halfway"""
    if time.time() - _DISK['at'] > 10:
        try: _DISK['low'] = min(shutil.disk_usage(OUT).free, shutil.disk_usage(SESS).free) < limit_gb * 1e9
        except OSError: _DISK['low'] = False
        _DISK['at'] = time.time()
    return _DISK['low']

def pause_reason(kind=None, arg=None):
    """why heavy work waits right now: 'live' (you stream or record, so your stream does not drop frames),
    'disk' (almost no room left) or 'busy' (the pc is at its limit). None = go"""
    light = kind == 'download' or (kind == 'render' and isinstance(arg, dict) and (arg.get('preview') or arg.get('live')))
    if disk_low() and not (kind == 'render' and isinstance(arg, dict) and arg.get('preview')): return 'disk'
    if light or STATE.get('run_live'): return None
    if SET.get('pause_live', True) and is_live(): return 'live'
    if SET.get('pause_busy', True) and pc_busy(): return 'busy'
    if SET.get('pause_busy', True) and pc_hot(): return 'hot'   # the graphics card is too warm: wait until it cooled down
    return None

def paused(): return bool(pause_reason())

# ---- learning how long things take on this pc (for a real "time left")
TEMPO_F = os.path.join(DATA, 'tempo.json')
def tempo_load():
    try: return json.load(open(TEMPO_F, encoding='utf-8'))
    except Exception: return {}
def tempo_key(kind, arg):
    if kind == 'render': return 'render_' + ('voorbeeld' if arg.get('preview') else 'montage' if arg.get('parts') else (arg.get('layout') or SET.get('layout', 'split')))
    return kind
def tempo_units(kind, arg):
    if kind == 'render': return max(1.0, float(arg.get('end', 0)) - float(arg.get('start', 0)))
    if kind in ('analyse', 'remux', 'proxy'):
        try: return max(1.0, float(load_sess(arg).get('duration') or 0))
        except Exception: return 0
    return 0
def tempo_est(kind, arg):
    u = tempo_units(kind, arg); L = tempo_load().get(tempo_key(kind, arg)) or tempo_load().get(kind) or []
    if not u or len(L) < 2: return None
    L = sorted(L)[-12:]; rate = L[len(L) // 2]
    return round(rate * u + 2, 1)
def tempo_note(kind, arg, secs):
    u = tempo_units(kind, arg)
    if not u or secs < 1: return
    d = tempo_load()
    for k in {tempo_key(kind, arg), kind}:
        d.setdefault(k, []).append(round(secs / u, 4)); d[k] = d[k][-20:]
    try: json.dump(d, open(TEMPO_F, 'w', encoding='utf-8'))
    except Exception: pass

# ---- clear error messages instead of Python errors
ERRORS = collections.deque(maxlen=30)
def friendly(txt, stage=''):
    t = str(txt or '')
    rules = [(r'No space left|Errno 28|disk full', 'Your disk is full. Free up space in System > Storage and try again.'),
             (r'Permission denied|Errno 13|being used by another process|WinError 32', 'I am not allowed to open a file. Is it still open in another program (a video player, for example)?'),
             (r'No such file|Errno 2|niet gevonden|does not exist', 'A file was not found. Was the recording moved or deleted?'),
             (r'out of memory|MemoryError|CUDA error|Cannot allocate', 'Your PC ran out of memory. Close other heavy programs and try again.'),
             (r'moov atom|Invalid data found|End of file|corrupt', 'The recording is damaged or not finished yet. Record as MKV in OBS and this will not happen again.'),
             (r'Error while opening encoder|amf|nvenc|qsv', 'Your graphics card did not cooperate. I will use the processor from now on; or set Graphics card to "Processor only" in Settings.'),
             (r'gestopt|stopped', 'Stopped.'),
             (r'urlopen|timed out|Temporary failure|getaddrinfo|ConnectionError|HTTP Error', 'No internet connection, or the website is not responding. Try again later.')]
    for pat, msg in rules:
        if re.search(pat, t, re.I): return msg
    return f'Something went wrong{" while " + stage.lower() if stage else ""}. Make an error report in System so it can be fixed.'
def note_error(where, exc_text):
    ERRORS.append({'at': time.time(), 'where': where, 'error': scrub(exc_text)[-3000:]})

RENDER_EXTRA = ('cuts', 'cap_shift', 'bleep', 'bg', 'round', 'border', 'divider', 'cap_anim', 'loop', 'unsure_left', 'brand')
Q_WORDS = {}   # the words of each short in its own timeline, for the quality check
