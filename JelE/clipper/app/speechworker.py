# JelE Clipper speech worker: runs the speech model in its own process.
# If the model crashes or runs out of memory, only this process stops; the app keeps running and starts a new one.
# It runs at low priority, with a core limit and (on Windows) a memory limit, so it can never take your pc or stream down.
# Talks JSON over stdin/stdout, one message per line. Started by clipper.py, do not run it on its own.
import os, sys, json, wave, traceback


OUT = sys.stdout
sys.stdout = sys.stderr   # library prints go to the log, only our messages go to the app


def say(**m):
    OUT.write(json.dumps(m) + '\n'); OUT.flush()


def cuda_dlls():
    """graphics card support installed by the Full setup (nvidia pip packages): tell Windows where its files are"""
    if os.name != 'nt': return
    try:
        import site, glob
        for sp in site.getsitepackages() + [site.getusersitepackages()]:
            for d in glob.glob(os.path.join(sp, 'nvidia', '*', 'bin')):
                try: os.add_dll_directory(d)
                except Exception: pass
                os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass


def low_priority():
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)   # below normal
        else:
            os.nice(10)
    except Exception:
        pass


def memory_limit(mb):
    """Windows: put this process in a job object with a memory cap. Above the cap an allocation fails
    (the model stops with an error) instead of the whole pc starting to swap and freeze."""
    if os.name != 'nt' or not mb:
        return False
    try:
        import ctypes
        from ctypes import wintypes as w
        k = ctypes.windll.kernel32

        class BASIC(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', w.DWORD),
                        ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', w.DWORD),
                        ('Affinity', ctypes.c_size_t), ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]

        class IOC(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ('r', 'w', 'o', 'rb', 'wb', 'ob')]

        class EXT(ctypes.Structure):
            _fields_ = [('Basic', BASIC), ('Io', IOC), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
        k.CreateJobObjectW.restype = w.HANDLE
        job = k.CreateJobObjectW(None, None)
        if not job:
            return False
        info = EXT()
        info.Basic.LimitFlags = 0x00000100 | 0x00002000   # process memory limit + kill when the app's handle closes
        info.ProcessMemoryLimit = int(mb) * 1024 * 1024
        if not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return False
        return bool(k.AssignProcessToJobObject(job, k.GetCurrentProcess()))
    except Exception:
        return False


MODELS = {}


def get_model(name, cuda, threads):
    key = (name, cuda, threads)
    if key not in MODELS:
        from faster_whisper import WhisperModel
        MODELS.clear()   # one model at a time: never two big models in memory
        MODELS[key] = WhisperModel(name, device='cuda' if cuda else 'cpu', compute_type='float16' if cuda else 'int8', cpu_threads=threads)
    return MODELS[key]


def prompt_for(model, base, mine):
    tok = getattr(model, 'hf_tokenizer', None)

    def fits(txt):
        if tok is not None:
            try:
                return len(tok.encode(' ' + txt, add_special_tokens=False).ids) <= 215
            except Exception:
                pass
        return len(txt) <= 580
    base = list(base or [])
    while base and not fits(', '.join(base) + ', ' + mine):
        base = base[1:]
    return ', '.join(base + [mine])


def transcribe(req):
    import numpy as np
    try:
        model = get_model(req['model'], bool(req.get('cuda')), int(req.get('threads') or 4))
    except Exception as e:
        return say(err='load', msg=str(e)[:300])
    with wave.open(req['wav'], 'rb') as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    kw = dict(req.get('kw') or {})
    kw['initial_prompt'] = prompt_for(model, req.get('prompt_base'), req.get('prompt_mine') or '')
    try:
        segs, _ = model.transcribe(audio, hallucination_silence_threshold=1.0, **kw)
    except TypeError:
        segs, _ = model.transcribe(audio, **kw)       # older faster-whisper
    total = len(audio) / 16000.0
    out = []
    for sg in segs:
        say(p=round(min(1.0, sg.end / max(1.0, total)), 4))
        out.append({'start': sg.start, 'end': sg.end, 'text': sg.text or '', 'no_speech_prob': getattr(sg, 'no_speech_prob', 0),
                    'compression_ratio': getattr(sg, 'compression_ratio', 0), 'avg_logprob': getattr(sg, 'avg_logprob', 0),
                    'words': [[w.start, w.end, w.word, getattr(w, 'probability', 1)] for w in (sg.words or [])]})
    vad = []
    if req.get('vad'):
        try:
            from faster_whisper.vad import get_speech_timestamps, VadOptions
            vad = [[sp['start'] / 16000.0, sp['end'] / 16000.0] for sp in
                   get_speech_timestamps(audio, VadOptions(threshold=0.55, min_speech_duration_ms=400, min_silence_duration_ms=300))]
        except Exception:
            pass
    say(ok=True, segs=out, vad=vad)


# ---------------------------------------------------------------- graphics card on any brand (AMD, Intel, NVIDIA): whisper.cpp with Vulkan
def collapse_loops(words, ti=2):
    """the speech model sometimes gets stuck and says the same words again and again.
    a block of 2+ words that comes 3+ times in a row (or one word 6+ times) is kept only once"""
    import re as _r
    k = [_r.sub(r"[^\w']+", '', str(w[ti]).lower()) for w in words]
    out, i, n = [], 0, len(words)
    while i < n:
        hit = 0
        for L in range(1, 13):
            if i + L * 3 > n: break
            blk = k[i:i + L]
            if not any(blk): continue
            r = 1
            while i + (r + 1) * L <= n and k[i + r * L:i + (r + 1) * L] == blk: r += 1
            if r >= (6 if L == 1 else 3): hit = (L, r); break
        if hit:
            L, r = hit; out.extend(words[i:i + L]); i += L * r
        else:
            out.append(words[i]); i += 1
    return out


def parse_wcpp(path):
    """whisper-cli -ojf -ml 1 -sow: one segment per word, with the chance per token. -> segments like faster-whisper gives"""
    d = json.load(open(path, encoding='utf-8', errors='replace'))
    words = []
    for sg in d.get('transcription') or []:
        txt = sg.get('text') or ''
        if not txt.strip() or txt.strip().startswith('[_'): continue
        off = sg.get('offsets') or {}
        a, b = (off.get('from') or 0) / 1000.0, (off.get('to') or 0) / 1000.0
        ps = [t.get('p', 1.0) for t in sg.get('tokens') or [] if not (t.get('text') or '').startswith('[_')]
        words.append([a, b, txt, min(ps) if ps else 1.0])
    words = collapse_loops(words)
    segs, cur = [], []
    for w in words:   # words back into sentences: a new one after a pause
        if cur and (w[0] - cur[-1][1] > 0.8 or cur[-1][2].rstrip().endswith(('.', '?', '!'))):
            segs.append(cur); cur = []
        cur.append(w)
    if cur: segs.append(cur)
    return [{'start': c[0][0], 'end': c[-1][1], 'text': ''.join(w[2] for w in c), 'no_speech_prob': 0.0, 'compression_ratio': 1.0,
             'avg_logprob': 0.0, 'words': c} for c in segs], d.get('result', {}).get('language')


def transcribe_wcpp(req):
    """run whisper-cli (its own process again), report progress, answer like transcribe()"""
    import subprocess, tempfile, re as _re
    exe, model = req['exe'], req['model_path']
    out = os.path.join(tempfile.gettempdir(), f'jele_wcpp_{os.getpid()}')
    args = [exe, '-m', model, '-f', req['wav'], '-l', (req.get('lang') or 'en'), '-t', str(int(req.get('threads') or 4)),
            '-ojf', '-ml', '1', '-sow', '-pp', '-np', '-sns', '-mc', '0', '-of', out]
    if req.get('prompt'): args += ['--prompt', req['prompt'][:800]]
    if req.get('no_gpu'): args += ['-ng']
    p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors='replace',
                         creationflags=0x08000000 if os.name == 'nt' else 0)
    tail = []
    for ln in p.stderr:
        m = _re.search(r'progress =\s*(\d+)%', ln)
        if m: say(p=round(int(m.group(1)) / 100.0, 3))
        else: tail = (tail + [ln.strip()])[-12:]
    code = p.wait()
    if code != 0 or not os.path.exists(out + '.json'):
        return say(err='fail', msg=f'graphics card engine stopped (code {code}): ' + ' | '.join(tail[-3:])[-280:])
    try:
        segs, lang = parse_wcpp(out + '.json')
    finally:
        try: os.remove(out + '.json')
        except OSError: pass
    say(ok=True, segs=segs, vad=[], engine='vulkan', lang=lang)


def main():
    low_priority()
    cuda_dlls()
    mb = 0
    for a in sys.argv[1:]:
        if a.startswith('--memlimit='):
            mb = int(a.split('=', 1)[1] or 0)
    lim = memory_limit(mb)
    say(hello=True, pid=os.getpid(), memlimit=mb if lim else 0)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if req.get('cmd') == 'transcribe':
                transcribe(req)
            elif req.get('cmd') == 'wcpp':
                transcribe_wcpp(req)
            elif req.get('cmd') == 'ping':
                say(ok=True)
            elif req.get('cmd') == 'quit':
                break
        except MemoryError:
            say(err='memory', msg='out of memory'); MODELS.clear()
        except Exception as e:
            say(err='fail', msg=str(e)[:300], tb=traceback.format_exc()[-1500:])


if __name__ == '__main__':
    main()
