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
        with urllib.request.urlopen(req, timeout=300) as r:   # a big model on the processor can take a while
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
            'an insane play, a fail, a story with an ending, or chat going wild. A bad clip is just talking, waiting, a menu, or nothing happening. ' + 'Score 1 to 3 for: mumbling or talking to yourself, quiet chatting, an end screen or scoreboard after a match, menus, lobby, queue, waiting, buy phase small talk. Score 7 or more only when a stranger on TikTok would laugh, be amazed or feel the hype. Be strict: most parts of a stream are a 2 to 5.' + ' '
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
    if re.search(r'\b(drags?|sleept|duurt te lang|too slow|te traag|boring at the end|saai aan het eind|flat|vlak|dies|kabbelt|fizzles)\b', t):
        return {'action': 'end_earlier' if has('end', 'ending', 'eind', 'einde', 'slot', 'at the end', 'aan het eind') else 'start_later' if has('start', 'begin', 'begint', 'opening') else 'shorter', 'value': _secs(t, 3)}
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

CMD_MISS = [0]
def cmd_rules(text):
    """a sentence -> a list of actions, or None. several commands in one sentence are split on and / en / , / ; / then"""
    raw = (text or '').strip()
    if not raw: return None
    if re.match(r'^\s*(title|titel|hook)\b', raw, re.I):
        r = _one(raw.lower(), raw); return [r] if r else None
    parts = [p for p in re.split(r'\s*(?:,|;|\.\s|\band then\b|\bthen\b|\ben dan\b|\bdaarna\b|\band\b|\ben\b|\balso\b|\book\b|\bplus\b)\s*', raw, flags=re.I) if p and p.strip()]
    acts = []; CMD_MISS[0] = 0
    for p in parts:
        r = _one(p.lower(), p)
        if r and r not in acts: acts.append(r)
        elif not r and len(re.findall(r'\w{3,}', p)) >= 2: CMD_MISS[0] += 1   # a part I did not understand
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
    if r and (not CMD_MISS[0] or not llm_ready()): return {'actions': r, 'by': 'rules'}
    if not llm_ready(): return None
    m_ = _cmd_model(text)
    if r and (not m_ or len(m_['actions']) <= len(r)): return {'actions': r, 'by': 'rules'}
    return m_

def _cmd_model(text):
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

# ---------------------------------------------------------------- what is this moment about? (the story, and what belongs to it)
MOMENT_TYPES = ('clutch', 'funny', 'fail', 'rage', 'hype', 'story', 'wholesome', 'skill', 'reaction')
def moment_timeline(c, words, why, step, scan=None, snd=None, a=None, b=None, texts=None):
    """everything that happens around a moment, second by second, as short lines a person (or the AI) can read.
    -> (lines, items): lines like '12s you: "wait he is one hp"', items as dicts for the rules"""
    a = max(0.0, c['t'] - 30) if a is None else a; b = (c['t'] + 15) if b is None else b
    items = []
    # what you said, as sentences
    cur = []
    for w in [w for w in words if a <= w[0] <= b and w[2] != UNCLEAR]:
        if cur and (w[0] - cur[-1][1] > 0.7 or re.search(r'[.!?]$', cur[-1][2])): items.append({'t': cur[0][0], 'e': cur[-1][1], 'k': 'say', 'v': ' '.join(x[2] for x in cur)}); cur = []
        cur.append(w)
    if cur: items.append({'t': cur[0][0], 'e': cur[-1][1], 'k': 'say', 'v': ' '.join(x[2] for x in cur)})
    # signals per step: chat, game events, sounds, markers
    last = {}
    for i in range(max(0, int(a / step)), min(len(why), int(b / step) + 1)):
        w_ = why[i] or {}; t = i * step
        for k, lab in (('chat', 'chat'), ('sound', 'sound'), ('game', 'game'), ('marker', 'marker'), ('tclip', 'chat clip'), ('audio', 'loud')):
            if k in w_ and t - last.get(k, -99) >= 2.5:
                v = w_[k]
                if k == 'chat': v = f'{v} messages in 10s'
                elif k == 'game': v = (v.get('label') or v.get('kind') or 'event') if isinstance(v, dict) else str(v)
                elif k == 'marker': v = 'you pressed Clip'
                elif k == 'tclip': v = 'someone clipped this on Twitch'
                elif k == 'audio': v = 'it suddenly got loud'
                items.append({'t': t, 'k': lab, 'v': str(v)}); last[k] = t
    if snd:
        for i in range(max(0, int(a / step)), min(len(snd), int(b / step) + 1)):
            r = snd[i]; t = i * step
            if r.get('shots') and t - last.get('shot', -99) >= 2: items.append({'t': t, 'k': 'game sound', 'v': f"{r['shots']} gunshot{'s' if r['shots'] > 1 else ''}"}); last['shot'] = t
            if r.get('laugh', 0) > 0.45 and t - last.get('laugh', -99) >= 3: items.append({'t': t, 'k': 'you', 'v': 'laughing'}); last['laugh'] = t
            if r.get('scream', 0) > 0.5 and t - last.get('scream', -99) >= 3: items.append({'t': t, 'k': 'you', 'v': 'screaming'}); last['scream'] = t
    for x in scan or []:
        if not (a <= x['t'] <= b): continue
        if x['state'] != 'playing' and t_ok(last, 'scr_' + x['state'], x['t'], 6): items.append({'t': x['t'], 'k': 'screen', 'v': {'dead': 'you are dead', 'spectate': 'spectating', 'menu': 'a menu', 'buy': 'buy phase', 'end': 'END SCREEN: the match is over, scoreboard'}.get(x['state'], x['state'])})
        for e in x.get('events') or []:
            if t_ok(last, 'ev_' + e, x['t'], 8): items.append({'t': x['t'], 'k': 'screen', 'v': {'round_win': 'round won', 'round_loss': 'round lost', 'win': 'match won', 'loss': 'match lost'}.get(e, e)})
    for g in texts or []:   # text that appears on screen: a message in the game chat, the killfeed, a banner
        if a <= g['t'] <= b: items.append({'t': g['t'], 'k': 'on screen (' + g['region'] + ')', 'v': g['text'][:90], 'box': g['box'], 'region': g['region']})
    ws_ = [w for w in words if a <= w[0] <= b]
    if ws_:
        unc = sum(1 for w in ws_ if w[2] == UNCLEAR) / len(ws_)
        if unc > 0.3: items.append({'t': ws_[0][0], 'k': 'speech', 'v': f'{int(unc * 100)}% of the words are unclear (mumbling)'})
    if not any(x['k'] in ('game', 'game sound', 'screen', 'chat', 'marker', 'chat clip', 'you') for x in items):
        items.append({'t': a, 'k': 'note', 'v': 'no game events, no gunshots, no chat activity, no laughing or screaming in this part'})
    items.sort(key=lambda x: x['t'])
    lines = [f"{x['t'] - a:4.0f}s {'you say' if x['k'] == 'say' else x['k']}: " + (f'"{x["v"]}"' if x['k'] in ('say',) or x['k'].startswith('on screen') else x['v']) for x in items]
    return lines, items, a

def t_ok(last, k, t, gap):
    if t - last.get(k, -99) >= gap: last[k] = t; return True
    return False

def brief_rules(c, items, a, peak):
    """the story without the AI: payoff = the strongest thing near the peak, start = the sentence that sets it up, end = when the reaction is over"""
    says = [x for x in items if x['k'] == 'say']
    big = [x for x in items if x['k'] in ('game', 'game sound', 'you', 'marker', 'screen') or (x['k'] == 'say' and SAY_STRONG.search(x['v']))]
    pay = min(big, key=lambda x: abs(x['t'] - peak))['t'] if big else peak
    # the start: the first sentence (within 20 s before the payoff) after a pause of 1.5 s, so the clip starts with a full thought
    start = max(a, pay - 10)
    pre = [x for x in says if pay - 20 <= x['t'] <= pay - 3]
    for i, x in enumerate(pre):
        prev_end = pre[i - 1]['e'] if i else -99
        if x['t'] - prev_end >= 1.5 or SETUP.search(x['v']): start = x['t'] - 0.4; break
    # the end: the last sentence or laugh that belongs to the reaction (gaps under 2.5 s), at most 8 s after the payoff
    end = pay + 2.5
    for x in [x for x in items if x['t'] > pay and x['k'] in ('say', 'you', 'chat')]:
        if x['t'] - end > 2.5 or x['t'] > pay + 8: break
        end = (x.get('e') or x['t'] + 1.0) + 0.6
    # the cause: what you react to. you read something from the screen -> when it showed up; else the last kill, death, bang or new killfeed line before your reaction
    cause, focus = None, None
    try:
        txt_ = [{'t': x['t'], 'text': x['v'], 'box': x.get('box'), 'region': x.get('region')} for x in items if x['k'].startswith('on screen')]
        g_, t_ = read_aloud(txt_, [x for x in says if pay - 12 <= x['t'] <= pay + 3])   # only what you say around your reaction
        if g_: cause = t_; focus = {'t': round(t_, 2), 'dur': 3.0, 'box': g_['box'], 'region': g_['region'], 'text': g_['text']}
    except Exception: pass
    if cause is None:
        trig = [x['t'] for x in items if (x['k'] in ('game', 'game sound') or (x['k'] == 'screen' and 'dead' in x['v']) or x['k'] == 'on screen (killfeed)') and pay - 8 <= x['t'] <= pay + 0.5]
        if trig: cause = max(trig)
    if cause is not None:
        # start close before what you react to: the sentence just before it (up to 10 s), else 4 s before it.
        # a message you read out loud may be long before your reaction, then the clip simply starts at the message
        pre_c = [x for x in says if cause - 10 <= x['t'] <= cause - 0.5]
        start = (pre_c[0]['t'] - 0.4) if pre_c else max(a, cause - 4)
        start = min(start, cause - 2.5)
    kinds = ' '.join(x['v'].lower() for x in items if abs(x['t'] - pay) < 6)
    typ = 'funny' if 'laugh' in kinds else 'fail' if ('dead' in kinds or 'round lost' in kinds) else 'clutch' if ('round won' in kinds or 'ace' in kinds or 'clutch' in kinds) else 'hype'
    return {'start': round(start, 1), 'payoff': round(pay, 1), 'end': round(min(end, pay + 8), 1), 'type': typ, 'about': '', 'zoom': [round(pay, 2)],
            'cause': round(cause, 2) if cause is not None else None, 'focus': focus,
            'replay': typ == 'clutch' and cause is not None and not focus, 'layout': 'split' if typ == 'funny' else None, 'music': {'funny': 'funny', 'clutch': 'hype', 'fail': 'funny'}.get(typ), 'by': 'rules'}

def llm_brief(c, lines, a, game='', lang='en', port=None):
    """the AI reads the timeline and says what the moment is about and how to edit it"""
    if not lines: return {}
    lang_name = {'nl': 'Dutch', 'en': 'English'}.get(lang, 'English')
    sysm = ('You are the editor of gaming shorts. You get a timeline of a stream, second by second: what the streamer says, game sounds, what is on screen, chat. '
            'Find the ONE story in it: the setup (where it starts making sense), the cause (the second the thing the streamer reacts to happens or first appears on screen: a kill, a death, a weird angle, a message in the game chat), '
            'the payoff (the big reaction) and where the reaction is over. When the streamer reads a chat message out loud, the cause is the second the message line says "on screen" (NOT when it is read), and the clip must start before it. '
            'Reacting to trash talk, a toxic or funny chat message, a weird angle or a lucky shot is good content (score 6 to 8 when the reaction is strong). '
            'Then decide the edit. Answer only with JSON: {"about": "what happens, max 12 words", "type": one of ' + '/'.join(MOMENT_TYPES) +
            ', "start": seconds, "cause": seconds, "payoff": seconds, "end": seconds, "zoom": [seconds, max 2, on the payoff or a big reaction], '
            '"replay": true only for an insane play (clutch, multi kill, crazy shot) worth seeing twice, else false, "focus": "chat" when the story is a chat message, "killfeed" when it is a kill or death in the killfeed, else "none", '
            '"layout": "split" when the face/reaction matters, "gameonly" when the play matters, "music": "hype"/"funny"/"tension"/"chill"/"none", '
            '"title": "hook, max 6 words, capitals, in ' + lang_name + '", "score": 1-10}. A good short is 12 to 35 seconds. Never start in the middle of a sentence. ' + 'Score 1 to 3 for: mumbling or talking to yourself, quiet chatting, an end screen or scoreboard after a match, menus, lobby, queue, waiting, buy phase small talk. Score 7 or more only when a stranger on TikTok would laugh, be amazed or feel the hype. Be strict: most parts of a stream are a 2 to 5.')
    ex_u = ('Game: Valorant. Timeline:\n   0s you say: "okay I will hold B alone"\n   6s game sound: 2 gunshots\n   9s you say: "wait wait they are all coming"\n  12s game sound: 4 gunshots\n'
            '  13s game: kill\n  14s game: kill\n  15s you: screaming\n  16s you say: "NO WAY I got all three"\n  17s chat: 22 messages in 10s\n  20s you say: "chat did you see that"\n  27s you say: "okay buy phase what do we get"')
    ex_a = '{"about": "holds B alone and wins a 1v3", "type": "clutch", "start": 8.5, "cause": 12, "payoff": 15, "end": 21.5, "zoom": [14, 16], "replay": true, "focus": "none", "layout": "split", "music": "hype", "title": "HELD B ALONE VS THREE", "score": 9}'
    msg = [{'role': 'system', 'content': sysm}, {'role': 'user', 'content': ex_u}, {'role': 'assistant', 'content': ex_a},
           {'role': 'user', 'content': f'Game: {game or "unknown"}. Timeline:\n' + '\n'.join(lines[:70])}]
    ans = llm_chat(msg, 400, 0.2, port); LLM['last_brief'] = ans[:600]
    m = re.search(r'\{.*\}', ans, re.S) or re.search(r'\{.*', ans, re.S)
    if not m: return {}
    js = m.group(0)
    d = None
    for fix_ in (js, js + '}', js + '"}', re.sub(r',\s*"[^"]*"?\s*:?\s*[^,}]*$', '', js) + '}'):   # an answer cut off at the end still counts
        try: d = json.loads(fix_); break
        except Exception: continue
    if not isinstance(d, dict): return {}
    try:
        st, pay, en = float(d['start']) + a, float(d['payoff']) + a, float(d['end']) + a
    except Exception: return {}
    try: cause = float(d.get('cause')) + a if d.get('cause') is not None else None
    except Exception: cause = None
    if cause is not None and not (st - 5 <= cause <= pay + 1): cause = None
    if not (st < pay < en) or en - st < 6 or en - st > 60: return {}
    zs = []
    for z in d.get('zoom') or []:
        try:
            z = float(z) + a
            if st < z < en: zs.append(round(z, 2))
        except Exception: pass
    return {'about': str(d.get('about') or '')[:90], 'type': d.get('type') if d.get('type') in MOMENT_TYPES else 'hype',
            'start': round(st, 1), 'payoff': round(pay, 1), 'end': round(en, 1), 'zoom': zs[:2], 'replay': bool(d.get('replay')) and d.get('type') in ('clutch', 'skill'),
            'cause': round(cause, 2) if cause is not None else None, 'focus_kind': d.get('focus') if d.get('focus') in ('chat', 'killfeed') else None,
            'layout': d.get('layout') if d.get('layout') in ('split', 'gameonly', 'frame') else None,
            'music': d.get('music') if d.get('music') in ('hype', 'funny', 'tension', 'chill', 'none') else None,
            'title': str(d.get('title') or '')[:40].upper(), 'score': d.get('score'), 'by': 'ai'}

MOOD_WORDS = {'hype': r'hype|epic|trap|phonk|energy|drop|bass', 'funny': r'funny|fun|silly|meme|goofy|comedy', 'tension': r'tension|suspense|dark|intense|tense',
              'chill': r'chill|lofi|lo-fi|calm|relax|soft', 'none': r'^$'}
def music_for_mood(mood):
    """a song from your music folder whose name fits the mood (hype, funny, tension, chill), or None"""
    if not mood or mood == 'none': return None
    rx = re.compile(MOOD_WORDS.get(mood, mood), re.I)
    fs = [f for f in music_list() if rx.search(f)]
    import random as _rnd
    return _rnd.choice(fs) if fs else None

def brief_merge(ai, rules, items):
    """the AI knows what it is about; the rules are strict about timing. keep the AI's story, fix timing that cannot be right:
    a start with less than 4 s before the payoff, a reaction that goes on for more than 9 s, a start or end in the middle of a sentence"""
    if not ai: return rules
    b = dict(ai)
    # the cause: when you read a message from the screen, the rules know exactly when it appeared (that wins)
    if rules.get('focus'): b['cause'] = rules['cause']; b['focus'] = rules['focus']
    elif b.get('cause') is None: b['cause'] = rules.get('cause')
    elif b.get('focus_kind'):   # the AI says chat or killfeed: take the text in that place closest to its cause
        cand = [x for x in items if x['k'] == 'on screen (' + b['focus_kind'] + ')' and abs(x['t'] - b['cause']) <= 6]
        if cand:
            g = min(cand, key=lambda x: abs(x['t'] - b['cause'])); b['focus'] = {'t': round(g['t'], 2), 'dur': 3.0, 'box': g['box'], 'region': g['region'], 'text': g['v']}
    if b.get('cause') is not None and b['start'] > b['cause'] - 2: b['start'] = round(b['cause'] - 2.5, 1)
    if b['payoff'] - b['start'] < 4: b['start'] = min(rules['start'], b['payoff'] - 4)
    if b['end'] - b['payoff'] > 9: b['end'] = rules['end']
    if b['end'] - b['payoff'] < 1.5: b['end'] = max(b['end'], rules['end'])
    says = [x for x in items if x['k'] == 'say']
    for x in says:   # never start or stop in the middle of a sentence
        if x['t'] < b['start'] < x['e'] and b['payoff'] - x['t'] <= 20: b['start'] = round(x['t'] - 0.3, 1)
        if x['t'] < b['end'] < x['e'] and x['e'] - b['payoff'] <= 10: b['end'] = round(x['e'] + 0.5, 1)
    b['zoom'] = [z for z in (b.get('zoom') or []) if b['payoff'] - 3 <= z <= b['end']][:2] or [b['payoff']]
    return b

# ---------------------------------------------------------------- stories: moments that belong together (a setup now, the payoff minutes later)
PROMISE = re.compile(r"\b(i'?m gonna|i am going to|i will|i'll|watch me|watch this|let me|i bet|ik ga|let op|kijk maar|you'?ll see|this round i)\b.{0,40}\b(ace|clutch|win|kill|one ?tap|carry|drop|destroy|1v\d|get him|get them|beat|revenge|wraak)", re.I)
RESULT = re.compile(r"\b(i told you|told you|i did it|i said it|zei het toch|did it|called it|as promised|revenge|payback|wraak|got him back|remember him|that guy again)\b", re.I)
STORY_STOP = set('''the a an and or but to of in on at for is are was were be been it its this that i you he she we they me my your his her our their with as so just like what
oh god yeah okay ok no yes bro dude man guys chat wait why how who when where there here then than now really very got get go going gonna want know think did do does not dont can cant
one two three kill kills killed dead died round game team enemy enemies shot shots head nice good bad gg lets let'''.split())

def _story_toks(texts):
    out = set()
    for t in texts:
        for w in re.findall(r"[A-Za-z][A-Za-z0-9_']{3,}", t or ''):
            lw = w.lower().strip("'")
            if lw not in STORY_STOP: out.add(lw)
    return out

def link_stories(moments, words, max_gap=2400):
    """pairs of moments that tell one story together: a promise and its result, a toxic player and getting him back,
    a name or a joke that comes back. -> [{'a': mid, 'b': mid, 'why': ..., 'label': ...}]"""
    if len(moments) < 2: return []
    cnt = collections.Counter(w[2].lower().strip(".,!?'\"") for w in words)
    def text_of(m):
        ws = [w[2] for w in words if m['start'] - 1 <= w[0] <= m['end'] + 1]
        br = m.get('brief') or {}
        return ' '.join(ws), [br.get('about') or '', (br.get('focus') or {}).get('text') or '', m.get('title') or '']
    info = []
    for m in moments:
        t, extra = text_of(m)
        toks = {x for x in _story_toks([t] + extra) if cnt.get(x, 0) <= 4}   # rare words: names, things only said here
        info.append((m, t, extra, toks))
    out = []
    for i, (ma, ta, xa, ka) in enumerate(info):
        for mb, tb, xb, kb in info[i + 1:]:
            gap = mb['start'] - ma['end']
            if gap < 15 or gap > max_gap: continue
            why = None; label = None
            if PROMISE.search(ta) and ((mb.get('vision') or {}).get('events') or any(r in ' '.join(mb.get('reasons', [])) for r in ('won', 'ace', 'clutch', 'kill', 'fight'))):
                why = 'you said you would do it, and you did'; label = 'AND THEN...'
            elif RESULT.search(tb) and (ka & kb or PROMISE.search(ta)):
                why = 'you come back to it later'; label = 'LATER...'
            elif ka & kb:
                shared = sorted(ka & kb, key=lambda x: cnt.get(x, 0))[:3]
                focus_a = ((ma.get('brief') or {}).get('focus') or {}).get('text') or ''
                if any(x in focus_a.lower() for x in shared): why = f'"{shared[0]}" shows up again'; label = 'GUESS WHO...'
                elif len(shared) >= 2: why = 'the same thing comes back: ' + ', '.join(shared[:2]); label = 'LATER...'
            if why: out.append({'a': ma['id'], 'b': mb['id'], 'why': why, 'label': label, 'gap': round(gap)})
    return out[:8]

def llm_link(moments, port=None):
    """the AI reads one line per moment and says which ones belong to one story"""
    if len(moments) < 2: return []
    rows = [f"{i}: at {int(m['t'] // 60)}:{int(m['t'] % 60):02d} - {((m.get('brief') or {}).get('about') or m.get('title') or '')[:80]} | said: {' '.join((m.get('text') or '').split()[:18])}" for i, m in enumerate(moments[:24])]
    msg = [{'role': 'system', 'content': 'You get moments from one gaming stream. Find pairs that tell ONE story together when you put them after each other: a promise and the result, '
            'a toxic player and getting revenge on him, a fail and doing it right later, a joke or a name that comes back. Only real links. Answer only with JSON: '
            '[{"a": index, "b": index, "why": "max 10 words"}], or [] when there are none.'},
           {'role': 'user', 'content': '0: at 3:10 - says he will ace this round | said: watch me ace this round chat\n1: at 9:40 - toxic player insults him in chat | said: he said I am trash\n2: at 4:02 - gets four kills and the ace | said: ACE I TOLD YOU\n3: at 15:20 - kills the toxic player | said: remember me xToxicGuy'},
           {'role': 'assistant', 'content': '[{"a": 0, "b": 2, "why": "promised an ace and got it"}, {"a": 1, "b": 3, "why": "revenge on the toxic player"}]'},
           {'role': 'user', 'content': '\n'.join(rows)}]
    a = llm_chat(msg, 200, 0.1, port)
    m = re.search(r'\[.*\]', a, re.S)
    if not m: return []
    try: d = json.loads(m.group(0))
    except Exception: return []
    out = []
    for x in d if isinstance(d, list) else []:
        try:
            ia, ib = int(x['a']), int(x['b'])
            if 0 <= ia < len(moments) and 0 <= ib < len(moments) and ia != ib:
                A, Bm = sorted([moments[ia], moments[ib]], key=lambda m: m['t'])
                if Bm['start'] - A['end'] >= 15: out.append({'a': A['id'], 'b': Bm['id'], 'why': str(x.get('why') or '')[:80], 'label': 'LATER...', 'by': 'ai'})
        except Exception: continue
    return out[:6]
