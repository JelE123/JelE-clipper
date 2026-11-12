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
    key = (name, cuda)
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
