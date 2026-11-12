# JelE Clipper: a small AI model on your own pc (plan F4.7, optional)
# llama.cpp (llama-server) with Qwen2.5 1.5B Instruct: about 1 GB, works without internet once it is downloaded.
# it writes titles, and turns a sentence like "make it shorter" into an editor action you can undo.
# the editor commands also work without the model: simple sentences are understood by fixed rules first.

LLM_TAG = 'engine-llama'
LLM_MODEL = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'
LLM_MODEL_URL = 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/' + LLM_MODEL
LLM = {'busy': False, 'error': '', 'pct': 0, 'step': '', 'proc': None, 'port': 0, 'lock': threading.Lock()}

def llm_dir(): return os.path.join(HERE, 'engine', 'llama')
def llm_exe():
    for n in ('llama-server.exe', 'llama-server'):
        p = os.path.join(llm_dir(), n)
        if os.path.exists(p): return p
    return os.path.join(llm_dir(), 'llama-server.exe')
def llm_model(): return os.path.join(DATA, 'models', LLM_MODEL)
def llm_ready(): return os.path.exists(llm_exe()) and os.path.exists(llm_model()) and os.path.getsize(llm_model()) > 300e6
def llm_status():
    return {'ready': llm_ready(), 'busy': LLM['busy'], 'error': LLM['error'], 'pct': LLM['pct'], 'step': LLM['step'], 'on': SET.get('llm', True) is not False,
            'running': bool(LLM['proc'] and LLM['proc'].poll() is None), 'win': os.name == 'nt'}

def _llm_get(url, dst, label, lo, hi):
    tmp = dst + '.part'
    req = urllib.request.Request(url, headers={'User-Agent': 'JelE-Clipper'})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as fh:
        total = int(r.headers.get('Content-Length') or 0); got = 0
        while True:
            b = r.read(1 << 20)
            if not b: break
            fh.write(b); got += len(b)
            if total: LLM['pct'] = int(lo + (hi - lo) * got / total)
            LLM['step'] = f'{label} ({got // 1048576} MB' + (f' of {total // 1048576} MB)' if total else ')')
    os.replace(tmp, dst)

def llm_install():
    """download llama-server (about 30 MB) and the model (about 1 GB). runs in the background"""
    import zipfile
    if LLM['busy']: return
    LLM.update(busy=True, error='', pct=0, step='Starting')
    try:
        if os.name != 'nt': raise RuntimeError('this only works on Windows')
        repo = re.sub(r'^(https?://)?(www\.)?github\.com/', '', (SET.get('update_repo') or 'JelE123/JelE-clipper')).strip('/')
        os.makedirs(llm_dir(), exist_ok=True); os.makedirs(os.path.dirname(llm_model()), exist_ok=True)
        z = os.path.join(llm_dir(), 'llama.zip')
        _llm_get(f'https://github.com/{repo}/releases/download/{LLM_TAG}/llama_win64.zip', z, 'Downloading the AI engine', 0, 4)
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.endswith('/') or '..' in n: continue
                with zf.open(n) as src, open(os.path.join(llm_dir(), os.path.basename(n)), 'wb') as dst: shutil.copyfileobj(src, dst)
        os.remove(z)
        if not os.path.exists(llm_model()) or os.path.getsize(llm_model()) < 300e6:
            _llm_get(LLM_MODEL_URL, llm_model(), 'Downloading the AI model', 4, 100)
        LLM.update(step='Ready', pct=100); log('The local AI model is installed')
    except Exception as e:
        LLM['error'] = str(e)[:200]; log('The local AI model could not be installed:', e)
    finally: LLM['busy'] = False

def llm_start():
    """start llama-server when it is not running yet (low priority, never during your stream). -> port or 0"""
    with LLM['lock']:
        if LLM['proc'] and LLM['proc'].poll() is None: return LLM['port']
        if not llm_ready() or SET.get('llm', True) is False: return 0
        if STATE.get('live') or CUR.get('id'): return 0   # your stream comes first
        import socket
        s_ = socket.socket(); s_.bind(('127.0.0.1', 0)); port = s_.getsockname()[1]; s_.close()
        args = [llm_exe(), '-m', llm_model(), '--host', '127.0.0.1', '--port', str(port), '-c', '4096', '-t', str(max(2, CORES // 2)), '-ngl', '99']
        try:
            LLM['proc'] = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=(0x08000000 | 0x00004000) if os.name == 'nt' else 0)
        except Exception as e: LLM['error'] = str(e)[:200]; return 0
        LLM['port'] = port
        for _ in range(120):   # loading the model takes a few seconds
            time.sleep(0.5)
            if LLM['proc'].poll() is not None: LLM['error'] = 'the AI engine stopped right away'; return 0
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as r:
                    if r.status == 200: return port
            except Exception: pass
        return 0

def llm_stop():
    p = LLM.get('proc')
    if p and p.poll() is None:
        try: p.terminate()
        except Exception: pass
    LLM['proc'] = None

def llm_chat(messages, max_tokens=200, temp=0.7, port=None):
    """one answer from the model, or '' when it is not there"""
    port = port or llm_start()
    if not port: return ''
    body = json.dumps({'messages': messages, 'max_tokens': max_tokens, 'temperature': temp, 'stream': False}).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode('utf-8', 'replace'))
        return (d.get('choices') or [{}])[0].get('message', {}).get('content', '') or ''
    except Exception as e:
        log('The local AI model did not answer:', e); return ''

def llm_titles(text, reasons, game='', lang='en', n=3, port=None):
    """3 short hooks for the top of the short, from what was said and why it is a moment"""
    lang_name = {'nl': 'Dutch', 'en': 'English'}.get(lang, 'English')
    msg = [{'role': 'system', 'content': f'You write hooks for gaming shorts on TikTok. Each hook is at most 6 words, in {lang_name}, in capitals, no hashtags, no emojis, no quotes. '
                                          'Only claim what really happened. Answer with one hook per line, nothing else.'},
           {'role': 'user', 'content': f'Game: {game or "unknown"}\nWhy it is a moment: {", ".join(reasons or [])}\nWhat the streamer said: "{(text or "")[:500]}"\nWrite {n} different hooks.'}]
    out = []
    for ln in llm_chat(msg, 120, 0.8, port).splitlines():
        t = re.sub(r'^[\s\-\d.)*#"]+', '', ln).strip().strip('"\'').upper()
        t = re.sub(r"[^\w' !?]", '', t).strip()
        if 2 <= len(t.split()) <= 8 and len(t) <= 40 and t not in out: out.append(t)
    return out[:n]

# ---------------------------------------------------------------- "make it shorter": a sentence -> an editor action
CMD_ACTIONS = ('shorter', 'longer', 'start_later', 'start_earlier', 'end_earlier', 'end_later', 'no_zoom', 'zoom', 'no_music', 'no_captions', 'captions',
               'style', 'title', 'no_effects', 'cut_silence', 'loop')
def _num(t, d):
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(s|sec|seconds?|seconde[n]?|sec\.)?', t)
    return float(m.group(1).replace(',', '.')) if m else d
def cmd_rules(text):
    """simple sentences in English and Dutch, without the model"""
    t = (text or '').lower().strip()
    if not t: return None
    n = _num(t, 0)
    R = [(r'\b(shorter|korter|cut it down|inkorten)\b', 'shorter', n or 5), (r'\b(longer|langer)\b', 'longer', n or 5),
         (r'\b(start|begin)\w*\b.*\b(later|after)\b|later (starten|beginnen)', 'start_later', n or 2), (r'\b(start|begin)\w*\b.*\b(earlier|eerder|sooner)\b|eerder (starten|beginnen)', 'start_earlier', n or 2),
         (r'\b(end|stop|eindig)\w*\b.*\b(earlier|eerder|sooner)\b|eerder (stoppen|eindigen)', 'end_earlier', n or 2), (r'\b(end|stop|eindig)\w*\b.*\b(later)\b|later (stoppen|eindigen)', 'end_later', n or 2),
         (r'\b(no|geen|without|zonder|remove|weg|take|haal)\b.*\bzoom', 'no_zoom', 0), (r'\bzoom\b.*\b(weg|uit|off)\b', 'no_zoom', 0), (r'\b(add|meer|more|wel)\b.*\bzoom|\bzoom (in|erin)\b', 'zoom', 0),
         (r'\b(no|geen|without|zonder)\b.*\b(music|muziek)|\b(music|muziek)\b.*\b(weg|uit|off)\b', 'no_music', 0),
         (r'\b(no|geen|without|zonder)\b.*\b(captions|ondertitels?|subtitles)|\b(captions|ondertitels?)\b.*\b(weg|uit|off)\b', 'no_captions', 0),
         (r'\b(captions|ondertitels?)\b.*\b(on|aan)\b', 'captions', 0),
         (r'\b(no|geen|without|zonder|remove)\b.*\b(effects?|effecten)\b|\b(effects?|effecten)\b.*\b(weg|uit|off)\b', 'no_effects', 0),
         (r'\b(silence|stilte|stiltes|boring|saai)\b', 'cut_silence', 0), (r'\bloop\b', 'loop', 0)]
    for rx, act, v in R:
        if re.search(rx, t): return {'action': act, 'value': v, 'by': 'rules'}
    m = re.search(r'\b(title|titel|hook)\b\s*[:=]?\s*["\']?(.+?)["\']?$', text or '', re.I)
    if m and len(m.group(2).split()) >= 1: return {'action': 'title', 'value': m.group(2).strip().upper()[:40], 'by': 'rules'}
    m = re.search(r'\b(purple|paars|classic|klassiek|clean|jele)\b', t)
    if m: return {'action': 'style', 'value': {'paars': 'purple', 'klassiek': 'classic'}.get(m.group(1), m.group(1)), 'by': 'rules'}
    return None

def cmd_parse(text):
    """a sentence -> {'action', 'value'} from the fixed list, or None. rules first, then the model"""
    r = cmd_rules(text)
    if r: return r
    if not llm_ready(): return None
    msg = [{'role': 'system', 'content': 'You turn a request about a video short into one action. Actions: ' + ', '.join(CMD_ACTIONS) +
            '. Answer only with JSON like {"action":"shorter","value":5}. value is seconds for time actions, a style name for style (jele, purple, classic, clean), the text for title, else 0.'},
           {'role': 'user', 'content': text}]
    a = llm_chat(msg, 60, 0.1)
    m = re.search(r'\{.*\}', a, re.S)
    if not m: return None
    try: d = json.loads(m.group(0))
    except Exception: return None
    if d.get('action') not in CMD_ACTIONS: return None
    v = d.get('value', 0)
    if d['action'] in ('shorter', 'longer', 'start_later', 'start_earlier', 'end_earlier', 'end_later'):
        try: v = max(0.5, min(20.0, float(v or 3)))
        except Exception: v = 3.0
    return {'action': d['action'], 'value': v, 'by': 'model'}

import atexit as _ae
_ae.register(llm_stop)
