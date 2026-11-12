# JelE Clipper: a small AI model on your own pc (plan F4.7, optional)
# llama.cpp (llama-server) with Qwen2.5 1.5B Instruct: about 1 GB, works without internet once it is downloaded.
# it writes titles, and turns a sentence like "make it shorter" into an editor action you can undo.
# the editor commands also work without the model: simple sentences are understood by fixed rules first.

LLM_TAG = 'engine-llama'
# two sizes: small runs on any pc, smart needs a real graphics card (it is far better at judging moments and writing titles)
LLM_MODELS = {
    'small': {'file': 'qwen2.5-1.5b-instruct-q4_k_m.gguf', 'url': 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf', 'mb': 1100, 'min': 300e6},
    'smart': {'file': 'Qwen2.5-7B-Instruct-Q4_K_M.gguf', 'url': 'https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf', 'mb': 4700, 'min': 4.0e9},
}
def llm_size():
    """which model: the one you chose, else smart when there is a real graphics card (not built into the processor)"""
    ch = SET.get('llm_size') or 'auto'
    if ch in LLM_MODELS: return ch
    try: g = ' '.join(gpu_names()).lower()
    except Exception: g = ''
    return 'smart' if re.search(r'rtx|gtx|radeon rx|rx \d{4}|arc a\d|arc b\d', g) else 'small'
LLM_MODEL = LLM_MODELS['small']['file']; LLM_MODEL_URL = LLM_MODELS['small']['url']
LLM = {'busy': False, 'error': '', 'pct': 0, 'step': '', 'proc': None, 'port': 0, 'lock': threading.Lock()}

def llm_dir(): return os.path.join(HERE, 'engine', 'llama')
def llm_exe():
    for n in ('llama-server.exe', 'llama-server'):
        p = os.path.join(llm_dir(), n)
        if os.path.exists(p): return p
    return os.path.join(llm_dir(), 'llama-server.exe')
def llm_model(size=None):
    """the model file: the chosen size if it is there, else any size that is there"""
    want = os.path.join(DATA, 'models', LLM_MODELS[size or llm_size()]['file'])
    if size or os.path.exists(want): return want
    for k in ('smart', 'small'):
        p_ = os.path.join(DATA, 'models', LLM_MODELS[k]['file'])
        if os.path.exists(p_) and os.path.getsize(p_) > LLM_MODELS[k]['min']: return p_
    return want
def llm_ready(): return os.path.exists(llm_exe()) and os.path.exists(llm_model()) and os.path.getsize(llm_model()) > 300e6
def llm_status():
    have = {k: os.path.exists(os.path.join(DATA, 'models', v['file'])) and os.path.getsize(os.path.join(DATA, 'models', v['file'])) > v['min'] for k, v in LLM_MODELS.items()}
    return {'ready': llm_ready(), 'size': llm_size(), 'have': have, 'mb': LLM_MODELS[llm_size()]['mb'], 'using': os.path.basename(llm_model()) if llm_ready() else '', 'busy': LLM['busy'], 'error': LLM['error'], 'pct': LLM['pct'], 'step': LLM['step'], 'on': SET.get('llm', True) is not False,
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
    """download llama-server (about 30 MB) and the model (1 or 4.7 GB). runs in the background"""
    import zipfile
    if LLM['busy']: return
    LLM.update(busy=True, error='', pct=0, step='Starting')
    try:
        if os.name != 'nt': raise RuntimeError('this only works on Windows')
        repo = re.sub(r'^(https?://)?(www\.)?github\.com/', '', (SET.get('update_repo') or 'JelE123/JelE-clipper')).strip('/')
        os.makedirs(llm_dir(), exist_ok=True); os.makedirs(os.path.dirname(llm_model()), exist_ok=True)
        z = os.path.join(llm_dir(), 'llama.zip')
        if not os.path.exists(llm_exe()): _llm_get(f'https://github.com/{repo}/releases/download/{LLM_TAG}/llama_win64.zip', z, 'Downloading the AI engine', 0, 4)
        if os.path.exists(z):
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    if n.endswith('/') or '..' in n: continue
                    with zf.open(n) as src, open(os.path.join(llm_dir(), os.path.basename(n)), 'wb') as dst: shutil.copyfileobj(src, dst)
            os.remove(z)
        M = LLM_MODELS[llm_size()]; dst = llm_model(llm_size())
        if not os.path.exists(dst) or os.path.getsize(dst) < M['min']:
            _llm_get(M['url'], dst, 'Downloading the AI model', 4, 100)
        llm_stop()   # the next question starts the new model
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
        args = [llm_exe(), '-m', llm_model(), '--host', '127.0.0.1', '--port', str(port), '-c', '8192', '-t', str(max(2, CORES // 2)), '-ngl', '99']
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
    rules = f'You write hooks for gaming clips on TikTok. Rules: at most 6 words, in {lang_name}, in capitals, no hashtags, no emojis, no quotes, no labels. Only claim what really happened. Reply with exactly {n} lines, one hook per line, nothing else.'
    ex_u = 'Valorant clip. The streamer says: "he is one hp, no way, I got him with the knife". Why it is a moment: you said "no way", chat went off.'
    ex_a = 'KNIFED HIM AT ONE HP\nNO WAY THAT WORKED\nTHE KNIFE NEVER MISSES' if lang != 'nl' else 'GEMESD OP EEN HP\nDIT KAN GEWOON NIET\nHET MES MIST NOOIT'
    msg = [{'role': 'system', 'content': rules}, {'role': 'user', 'content': ex_u}, {'role': 'assistant', 'content': ex_a},
           {'role': 'user', 'content': f'{game or "Gaming"} clip. The streamer says: "{(text or "")[:400]}". Why it is a moment: {", ".join(reasons or []) or "a big reaction"}.'}]
    out = []; raw = llm_chat(msg, 160, 0.8, port); LLM['last'] = raw[:400]
    for ln in re.split(r'[\n;|]+', raw):
        if re.match(r'^\s*[A-Za-z ]{2,14}:\s', ln) and not re.match(r'^\s*hook', ln, re.I): continue   # "Game: ...", "Why: ..." are not hooks
        t = re.sub(r'^\s*(hook\s*)?[\-\d.)*#:"\u2022]+\s*', '', ln, flags=re.I).strip().strip('"\'').upper()
        t = re.sub(r"[^\w' !?]", '', t).strip()
        w = t.split()
        if len(w) < 2: continue
        while len(' '.join(w)) > 40 and len(w) > 2: w.pop()   # too long: cut on a word
        t = ' '.join(w)
        if t not in out and not t.startswith(('HERE ARE', 'SURE')): out.append(t)
    return out[:n]

# ---------------------------------------------------------------- the AI judges the moments (after the stream)
def llm_judge(c, words, game='', lang='en', port=None):
    """one moment -> {'score': 1..10, 'why': short reason, 'title': hook} from what was said and what happened, or {}"""
    said = ' '.join(w[2] for w in words if c['start'] - 1 <= w[0] <= c['end'] + 1)[:900]
    sig = ', '.join(c.get('reasons') or []) or 'a loud moment'
    ev = ', '.join(f"{e.get('kind')} at {e.get('t', 0) - c['start']:.0f}s" for e in (c.get('events') or [])[:6]) if c.get('events') else ''
    lang_name = {'nl': 'Dutch', 'en': 'English'}.get(lang, 'English')
    msg = [{'role': 'system', 'content': 'You judge clips from a gaming stream for TikTok and YouTube Shorts. A great clip has a clear payoff: a funny line, a big reaction, '
            'an insane play, a fail, a story with an ending, or chat going wild. A bad clip is just talking, waiting, a menu, or nothing happening. '
            'Answer only with JSON: {"score": 1-10, "why": "max 8 words", "title": "hook of max 6 words in capitals, in ' + lang_name + ', only what really happened"}.'},
           {'role': 'user', 'content': 'Game: Valorant. Signals: you said "no way", chat went off, a kill. Duration 18s. What was said: "wait wait he is one hp no way NO WAY I got him with the knife chat did you see that"'},
           {'role': 'assistant', 'content': '{"score": 9, "why": "knife kill at one hp, huge reaction", "title": "KNIFED HIM AT ONE HP"}'},
           {'role': 'user', 'content': 'Game: Valorant. Signals: it suddenly got loud. Duration 25s. What was said: "yeah so I think we should buy now uh what do you guys want okay"'},
           {'role': 'assistant', 'content': '{"score": 2, "why": "just buy phase talk", "title": "BUY PHASE TALK"}'},
           {'role': 'user', 'content': f'Game: {game or "unknown"}. Signals: {sig}.' + (f' Game events: {ev}.' if ev else '') + f' Duration {c["end"] - c["start"]:.0f}s. What was said: "{said}"'}]
    a = llm_chat(msg, 90, 0.2, port)
    m = re.search(r'\{.*\}', a, re.S)
    if not m: return {}
    try: d = json.loads(m.group(0))
    except Exception: return {}
    try: sc = max(1, min(10, int(round(float(d.get('score'))))))
    except Exception: return {}
    return {'score': sc, 'why': str(d.get('why') or '')[:60], 'title': str(d.get('title') or '')[:40].upper()}

# ---------------------------------------------------------------- "make it shorter": a sentence -> editor actions
# rules first (English and Dutch, many ways to say it, several commands in one sentence), the local model only for the rest.
TIME_ACTS = ('shorter', 'longer', 'start_later', 'start_earlier', 'end_earlier', 'end_later', 'length')
CMD_ACTIONS = TIME_ACTS + ('start_at_peak', 'end_after_peak', 'zoom_off', 'zoom_on', 'zoom_here', 'music_off', 'music_on', 'music_quieter', 'music_louder',
               'captions_off', 'captions_on', 'captions_bigger', 'captions_smaller', 'captions_up', 'captions_down', 'style', 'anim', 'layout',
               'teaser_off', 'teaser_on', 'replay_off', 'replay_on', 'effects_off', 'stickers_off', 'killfeed_off', 'sfx_off', 'sfx_on',
               'title', 'cut_silence', 'keep_silence', 'loop_on', 'loop_off', 'bleep_on', 'bleep_off', 'cut_word', 'undo', 'export', 'preview')
_W = lambda *x: r'\b(?:' + '|'.join(x) + r')\b'
NEG = _W('no', 'geen', 'without', 'zonder', 'remove', 'delete', 'weg', 'uit', 'off', 'take', 'haal', 'stop', 'disable', 'verwijder', 'drop', 'kill', 'lose', 'get rid of', 'skip', "don't", 'dont', 'niet')
POS = _W('add', 'on', 'aan', 'enable', 'zet', 'met', 'with', 'wel', 'more', 'meer', 'put', 'give', 'want', 'wil', 'use', 'gebruik', 'turn on')
def _secs(t, default):
    """'4 seconds', '4s', 'twee seconden', 'a bit' (2), 'a lot' (6), 'half' -> seconds"""
    words = {'one': 1, 'een': 1, 'één': 1, 'two': 2, 'twee': 2, 'three': 3, 'drie': 3, 'four': 4, 'vier': 4, 'five': 5, 'vijf': 5, 'six': 6, 'zes': 6,
             'seven': 7, 'zeven': 7, 'eight': 8, 'acht': 8, 'nine': 9, 'negen': 9, 'ten': 10, 'tien': 10, 'fifteen': 15, 'vijftien': 15, 'twenty': 20, 'twintig': 20}
    m = re.search(r'(\d+(?:[.,]\d+)?)', t)
    if m: return float(m.group(1).replace(',', '.'))
    for k, v in words.items():
        if re.search(r'\b' + k + r'\b\s*(s|sec|second|seconde|seconds|seconden)', t): return float(v)
    if re.search(_W('a bit', 'beetje', 'little', 'slightly', 'tikkie', 'iets', 'bit'), t): return 1.5
    if re.search(_W('a lot', 'veel', 'much', 'way', 'flink', 'stuk', 'lot'), t): return 6.0
    return float(default)

def _one(t, raw):
    """one command -> an action or None"""
    neg = bool(re.search(NEG, t)); pos = bool(re.search(POS, t))
    has = lambda *x: bool(re.search(_W(*x), t))
    # undo / export / preview
    if re.fullmatch(r'\s*(undo|ongedaan( maken)?|terug|go back|ctrl\s*\+?\s*z)\s*', t): return {'action': 'undo', 'value': 0}
    if has('export', 'exporteer', 'render', 'maak hem', 'make it now', 'make the short', 'save it', 'opslaan') and not has('shorter', 'longer', 'korter', 'langer'): return {'action': 'export', 'value': 0}
    if has('preview', 'voorbeeld', 'show me', 'laat zien', 'watch it'): return {'action': 'preview', 'value': 0}
    # title
    m = re.search(r'\b(?:title|titel|hook|tekst bovenin|text at the top|text on top)\b\s*(?:to|naar|:|=|is|wordt|should be|moet)?\s*["“\']?(.+?)["”\']?\s*$', raw, re.I)
    if m and len(m.group(1).strip()) > 1 and not re.fullmatch(r'(off|uit|weg|away)', m.group(1).strip(), re.I): return {'action': 'title', 'value': m.group(1).strip().upper()[:40]}
    # cut out a word or sentence: "cut out where I say pizza", "haal het stuk weg waar ik sorry zeg"
    m = re.search(r'(?:where|waar|when|wanneer|the part|het stuk|stuk)\b.*?\b(?:i say|i said|ik zeg|ik zei|zeg|says|said)\s+["“\']?([\w\' ]{2,40}?)["”\']?\s*(?:zeg|says|said)?\s*$', t)
    if m and (neg or has('cut', 'knip')): return {'action': 'cut_word', 'value': m.group(1).strip()}
    m = re.search(r'\b(?:waar|wanneer|als)\s+ik\s+["\u201c\']?([\w\' ]{2,40}?)["\u201d\']?\s+(?:zeg|zei|roep|riep)\b', t)
    if m and (neg or has('knip', 'cut')): return {'action': 'cut_word', 'value': m.group(1).strip()}
    if re.search(r'\b(drags?|sleept|duurt te lang|too slow|te traag|boring at the end|saai aan het eind)\b', t):
        return {'action': 'end_earlier' if has('end', 'eind', 'einde', 'at the end', 'aan het eind') else 'start_later' if has('start', 'begin', 'begint', 'opening') else 'shorter', 'value': _secs(t, 3)}
    # time: where it starts and ends
    if has('start', 'begin', 'starts', 'begint', 'opening', 'begins'):
        if has('kill', 'peak', 'action', 'actie', 'hoogtepunt', 'moment', 'shot', 'schreeuw', 'scream', 'shout', 'climax', 'payoff'): return {'action': 'start_at_peak', 'value': 0}
        if has('later', 'after', 'na', 'subsequently', 'further', 'verder'): return {'action': 'start_later', 'value': _secs(t, 2)}
        if has('earlier', 'eerder', 'sooner', 'before', 'vroeger', 'eerst'): return {'action': 'start_earlier', 'value': _secs(t, 2)}
    if has('end', 'ending', 'eind', 'einde', 'eindig', 'eindigt', 'stop', 'stops', 'stopt', 'finish', 'ends'):
        if has('reaction', 'reactie', 'after the kill', 'na de kill'): return {'action': 'end_after_peak', 'value': 0}
        if has('later', 'after', 'verder', 'langer'): return {'action': 'end_later', 'value': _secs(t, 2)}
        if has('earlier', 'eerder', 'sooner', 'before', 'vroeger'): return {'action': 'end_earlier', 'value': _secs(t, 2)}
    m = re.search(r'(?:make it|maak (?:hem|het|de short)|length|lengte|duur|precies|exactly)\D{0,12}(\d+)\s*(?:s|sec|seconds?|seconden?)\b', t)
    if m and not has('shorter', 'longer', 'korter', 'langer'): return {'action': 'length', 'value': float(m.group(1))}
    if has('shorter', 'korter', 'inkorten', 'trim', 'tighter', 'strakker', 'snappier', 'too long', 'te lang', 'cut it down', 'compacter', 'kort'): return {'action': 'shorter', 'value': _secs(t, 3)}
    if has('longer', 'langer', 'too short', 'te kort', 'extend', 'verleng'): return {'action': 'longer', 'value': _secs(t, 3)}
    # boring bits
    if has('silence', 'silences', 'stilte', 'stiltes', 'boring', 'saai', 'saaie', 'dead air', 'pauzes', 'pauses', 'gaps'):
        return {'action': 'keep_silence' if (has('keep', 'houd', 'laat', 'leave') and not has('cut', 'knip', 'weg')) else 'cut_silence', 'value': 0}
    # zoom
    if has('zoom', 'zooms', 'inzoomen', 'zoomen', 'punch in', 'punch-in'):
        if has('here', 'hier', 'now', 'nu', 'this moment', 'dit moment'): return {'action': 'zoom_here', 'value': 0}
        return {'action': 'zoom_off' if neg and not has('more', 'meer', 'add') else 'zoom_on', 'value': 0}
    # music
    if has('music', 'muziek', 'song', 'liedje', 'beat', 'nummer'):
        if has('quieter', 'zachter', 'softer', 'lower', 'lager', 'minder hard', 'too loud', 'te hard'): return {'action': 'music_quieter', 'value': 0}
        if has('louder', 'harder', 'higher', 'luider', 'too quiet', 'te zacht'): return {'action': 'music_louder', 'value': 0}
        return {'action': 'music_off' if neg else 'music_on', 'value': 0}
    # captions
    if has('caption', 'captions', 'ondertitel', 'ondertitels', 'subtitles', 'subs', 'tekst', 'text', 'words', 'woorden'):
        for k, v in (('purple', 'purple'), ('paars', 'purple'), ('classic', 'classic'), ('klassiek', 'classic'), ('clean', 'clean'), ('simpel', 'clean'), ('jele', 'jele'), ('orange', 'jele'), ('oranje', 'jele')):
            if has(k): return {'action': 'style', 'value': v}
        for k, v in (('typewriter', 'type'), ('type', 'type'), ('bounce', 'bounce'), ('pop', 'pop'), ('per word', 'word'), ('one word', 'word'), ('per woord', 'word'), ('no animation', 'none'), ('geen animatie', 'none')):
            if has(k): return {'action': 'anim', 'value': v}
        if has('bigger', 'groter', 'larger', 'big', 'groot', 'too small', 'te klein'): return {'action': 'captions_bigger', 'value': 0}
        if has('smaller', 'kleiner', 'small', 'klein', 'too big', 'te groot'): return {'action': 'captions_smaller', 'value': 0}
        if has('higher', 'hoger', 'up', 'omhoog', 'top', 'boven'): return {'action': 'captions_up', 'value': 0}
        if has('lower', 'lager', 'down', 'omlaag', 'bottom', 'onder'): return {'action': 'captions_down', 'value': 0}
        return {'action': 'captions_off' if neg else 'captions_on', 'value': 0}
    # effects
    if has('teaser', 'opening glimpse', 'intro'): return {'action': 'teaser_off' if neg else 'teaser_on', 'value': 0}
    if has('replay', 'slow motion', 'slowmo', 'slow-mo', 'herhaling', 'vertraagd'): return {'action': 'replay_off' if neg else 'replay_on', 'value': 0}
    if has('sticker', 'stickers'): return {'action': 'stickers_off', 'value': 0} if neg else None
    if has('killfeed', 'kill feed'): return {'action': 'killfeed_off', 'value': 0} if neg else None
    if has('sound effects', 'sfx', 'geluidseffecten', 'boom', 'whoosh'): return {'action': 'sfx_off' if neg else 'sfx_on', 'value': 0}
    if has('effects', 'effecten', 'effect'): return {'action': 'effects_off', 'value': 0} if neg else None
    if has('bleep', 'piep', 'swear', 'swearing', 'vloeken', 'scheldwoorden', 'censor', 'censuur'): return {'action': 'bleep_off' if (neg and not has('bleep', 'piep', 'censor')) else 'bleep_on', 'value': 0}
    if has('loop', 'looping'): return {'action': 'loop_off' if neg else 'loop_on', 'value': 0}
    # layout
    if has('landscape', 'liggend', 'horizontal', 'youtube', '16:9', '16 9'): return {'action': 'layout', 'value': 'landscape'}
    if has('game only', 'alleen game', 'only game', 'only the game', 'zonder cam', 'without cam', 'no cam', 'geen cam'): return {'action': 'layout', 'value': 'gameonly'}
    if has('whole frame', 'hele beeld', 'full frame', 'like on stream', 'zoals op stream', 'blur'): return {'action': 'layout', 'value': 'frame'}
    if has('cam', 'webcam', 'facecam', 'camera') and (pos or has('top', 'boven', 'split')): return {'action': 'layout', 'value': 'split'}
    return None

def cmd_rules(text):
    """a sentence -> a list of actions, or None. several commands in one sentence are split on and / en / , / ; / then"""
    raw = (text or '').strip()
    if not raw: return None
    if re.match(r'^\s*(title|titel|hook)\b', raw, re.I):
        r = _one(raw.lower(), raw); return [r] if r else None
    parts = [p for p in re.split(r'\s*(?:,|;|\.\s|\band then\b|\bthen\b|\ben dan\b|\bdaarna\b|\band\b|\ben\b|\balso\b|\book\b|\bplus\b)\s*', raw, flags=re.I) if p and p.strip()]
    acts = []
    for p in parts:
        r = _one(p.lower(), p)
        if r and r not in acts: acts.append(r)
    if not acts:
        r = _one(raw.lower(), raw)
        if r: acts = [r]
    timed = [a for a in acts if a['action'] in TIME_ACTS]
    if len(timed) == 1 and re.search(r'\d', raw) and not any(re.search(r'\d', p) and _one(p.lower(), p) == timed[0] for p in parts):
        timed[0]['value'] = _secs(raw.lower(), timed[0]['value'])   # "a bit snappier, like 4 seconds": the number belongs to it
    return acts or None

def cmd_parse(text):
    """a sentence -> {'actions': [...], 'by': rules|model} or None"""
    r = cmd_rules(text)
    if r: return {'actions': r, 'by': 'rules'}
    if not llm_ready(): return None
    msg = [{'role': 'system', 'content': 'You turn a request about editing a gaming short into actions. Allowed actions: ' + ', '.join(CMD_ACTIONS) +
            '. Answer only with a JSON list like [{"action":"shorter","value":3}]. value: seconds for ' + ', '.join(TIME_ACTS) +
            '; jele, purple, classic or clean for style; pop, bounce, type, word or none for anim; split, frame, gameonly or landscape for layout; the text for title or cut_word; else 0.'},
           {'role': 'user', 'content': 'it drags on at the end and the music is too loud'}, {'role': 'assistant', 'content': '[{"action":"end_earlier","value":3},{"action":"music_quieter","value":0}]'},
           {'role': 'user', 'content': text}]
    a = llm_chat(msg, 120, 0.1)
    m = re.search(r'\[.*\]|\{.*\}', a, re.S)
    if not m: return None
    try: d = json.loads(m.group(0))
    except Exception: return None
    d = d if isinstance(d, list) else [d]
    out = []
    for x in d:
        if not isinstance(x, dict) or x.get('action') not in CMD_ACTIONS: continue
        v = x.get('value', 0)
        if x['action'] in TIME_ACTS:
            try: v = max(0.5, min(60.0, float(v or 3)))
            except Exception: v = 3.0
        out.append({'action': x['action'], 'value': v})
    return {'actions': out, 'by': 'model'} if out else None

import atexit as _ae
_ae.register(llm_stop)
