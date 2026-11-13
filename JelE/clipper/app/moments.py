# JelE Clipper part: finding the moments. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- finding the moments
HYPE = re.compile(r'\b(lul|kekw|omegalul|lmao+|lmfao|lol+|w+|clip|clipit|clip it|no way|wtf|what|omg|pog+|poggers|holy|ace|clutch|insane|crazy|nice+|gg|sheesh|bro|nah+|yoo+|goated|cracked)\b|\?{3,}|!{3,}', re.I)
# things you say when something clip-worthy happens
SAY_HYPE = GameRe(r"\b(no+ way|oh my god|oh my gosh|omg|let'?s go+|lets go+|what the|wha+t|bro+|yo+|holy|insane|crazy|ace|clutch|one tap|onetap|no+|yes+|wow|sheesh|are you kidding|are you serious|how did|did you see|i can'?t believe|nah+|wait|oh no|get out|sick|beautiful|perfect|unreal|disgusting|nasty|cracked)\b", 'hype')
SAY_STRONG = GameRe(r"\b(no+ way|oh my god|oh my gosh|let'?s go+|lets go+|what the|holy|insane|crazy|ace|clutch|one tap|are you kidding|are you serious|i can'?t believe|unreal|disgusting|cracked|sheesh)\b", 'strong')
SETUP = re.compile(r"\b(watch this|wait for it|look at this|let me cook|kijk dit|let op|wacht maar|check this)\b", re.I)
SAY_LAUGH = re.compile(r'\b(ha(ha)+|he(he)+|lmao|lol)\b', re.I)
# you say the moment should be a clip, in English or Dutch: the strongest reason there is
CLIP_SAY = re.compile(r"(someone |somebody |iemand |yo |oh |ok |okay |bro )?(clip (that|it|this|dat|die|het|deze|em|'m)|clipt? dat|that'?s a clip|thats a clip|dat is een clip|dit moet een clip|dat moet (een clip|geclipt)|dit moet geclipt|clip clip|clippen)\b")
try: import gamewords             # agents, abilities, maps, weapons, callouts and stream talk (gamewords.py)
except Exception: gamewords = None

def vocab_prompt(model=None):
    """the built-in Valorant words plus your own word list (names of teammates, emotes).
    The speech model only reads the last ~220 word pieces of this text, so your own words go last
    and the built-in list is shortened from the front (least important words first) until it fits."""
    own = [w.strip() for w in re.split(r'[,\n]+', SET.get('vocab') or '') if w.strip()]
    mine = ', '.join(['JelE'] + own)[-450:]
    base = gamewords.prompt_words(cur_game()) if gamewords else ['Valorant', 'Jett', 'Reyna', 'Raze', 'Sova', 'Omen', 'Killjoy', 'Vandal', 'Phantom', 'spike', 'defuse', 'ult']
    tok = getattr(model, 'hf_tokenizer', None)
    def fits(txt):
        if tok is not None:
            try: return len(tok.encode(' ' + txt, add_special_tokens=False).ids) <= 215
            except Exception: pass
        return len(txt) <= 580
    while base and not fits(', '.join(base) + ', ' + mine): base = base[1:]
    return ', '.join(base + [mine])

LEARN_F = os.path.join(DATA, 'word_learn.json')
_LEARN = {'d': None}
def word_learn():
    if _LEARN['d'] is None:
        try: _LEARN['d'] = json.load(open(LEARN_F, encoding='utf-8'))
        except Exception: _LEARN['d'] = {}
    return _LEARN['d']
def _wk(t): return re.sub(r"^[^\w']+|[^\w']+$", '', (t or '').lower())
def word_learn_add(heard, fixed, prev='', nxt=''):
    """you changed a word in the editor: remember it, with the words around it (no question, no pop-up)"""
    h, f = _wk(heard), (fixed or '').strip()
    if not h or not f or h == f.lower() or h == '\u2026' or ' ' in h: return
    d = word_learn(); e = d.setdefault(h, {}).setdefault(f, {'n': 0, 'ctx': []})
    e['n'] += 1; e['at'] = time.time()
    for c in (_wk(prev), _wk(nxt)):
        if c and c not in e['ctx']: e['ctx'] = (e['ctx'] + [c])[-12:]
    try: json.dump(d, open(LEARN_F, 'w', encoding='utf-8'), indent=1)
    except Exception: pass
def learned_words():
    """the words you taught me, for the speech model: it then leans towards them when it is not sure"""
    out = []
    for h, fs in word_learn().items():
        for f, e in fs.items():
            if f not in out: out.append(f)
    return out[-60:]

def apply_fixes(words, game=None):
    """the right spelling of game words (also names that sound almost the same), then your own corrections"""
    if gamewords and words and SET.get('game_words', True):
        try:
            words = gamewords.fix(words, UNCLEAR, game or cur_game())
            words = gamewords.soundalike(words, UNCLEAR, game or cur_game())
        except Exception: traceback.print_exc()
    rules = [(str(a).strip(), str(b).strip()) for a, b in (SET.get('fixes') or []) if str(a).strip()]
    L = word_learn()
    if (not rules and not L) or not words: return words
    out = []
    for i, w in enumerate(words):
        t = w[2]
        for a, b in rules:
            if re.fullmatch(re.escape(a) + r"([.,!?']*)", t, re.I): t = b + re.sub(r'^' + re.escape(a), '', t, flags=re.I)
        k = _wk(t)
        if k in L:   # what you changed before: twice or more = always; once = when the words around it match last time
            f, e = max(L[k].items(), key=lambda x: x[1]['n'])
            near = {_wk(x[2]) for x in words[max(0, i - 2):i] + words[i + 1:i + 3]}
            if e['n'] >= 2 or near & set(e.get('ctx') or []):
                t = re.sub(re.escape(re.sub(r"^[^\w']+|[^\w']+$", '', t)), f, t, count=1, flags=re.I) if re.sub(r"^[^\w']+|[^\w']+$", '', t) else f
        out.append((w[0], w[1], t) if len(w) == 3 else tuple([w[0], w[1], t] + list(w[3:])))
    return out

SWEAR = re.compile(r"^(fuck\w*|f\*+\w*|motherfuck\w*|shit\w*|bullshit|bitch\w*|asshole\w*|cunt\w*|dick(head)?s?|pussy|whore|slut|nigg\w*|fag\w*|retard\w*|kanker\w*|kut|tering|tyfus|hoer)\W*$", re.I)
def censor(t):
    m = re.match(r"^(\W*)(\w)(\w*)(\W*)$", t)
    return (m.group(1) + m.group(2) + '*' * max(2, len(m.group(3))) + m.group(4)) if m else t

def audio_env(path, step=0.5):
    """loudness per half second (dB) in the voice band, read straight from ffmpeg"""
    import numpy as np
    sr = 8000; n = int(sr * step)
    amap = mic_map(path)
    p = subprocess.Popen([FF, '-hide_banner', '-loglevel', 'error', '-i', path] + amap + ['-vn', '-ac', '1', '-ar', str(sr), '-af', 'highpass=f=250,lowpass=f=3400', '-f', 's16le', '-'],
                         stdout=subprocess.PIPE, creationflags=NOWIN)
    out = []; rest = b''
    while True:
        b = p.stdout.read(n * 2 * 240)
        if not b: break
        b = rest + b; k = len(b) // (n * 2) * (n * 2); rest = b[k:]
        a = np.frombuffer(b[:k], dtype=np.int16).astype(np.float32).reshape(-1, n) / 32768.0
        out.extend((20 * np.log10(np.sqrt((a ** 2).mean(axis=1)) + 1e-6)).tolist())
    p.wait()
    return out

def zscore_rolling(x, win, floor=1e-3, prop=0.0):
    import numpy as np
    x = np.asarray(x, dtype=np.float32)
    if len(x) == 0: return x
    from numpy.lib.stride_tricks import sliding_window_view
    win = max(3, min(win, len(x)))
    w = sliding_window_view(x, win)                       # only real windows, no copied edge values
    idx = np.clip(np.arange(len(x)) - win // 2, 0, len(w) - 1)   # at the start/end use the first/last full window
    med_w = np.median(w, axis=1); mad_w = np.median(np.abs(w - med_w[:, None]), axis=1)
    med = med_w[idx]; mad = mad_w[idx]
    return (x - med) / np.maximum(1.4826 * mad, np.maximum(floor, prop * np.abs(med)))

def audio_tracks(path):
    """the audio tracks in a recording: [{'n': 1, 'title': 'Mic'}, ...]. OBS writes the track names you gave them into the file"""
    p = subprocess.run([FF, '-hide_banner', '-i', path], capture_output=True, text=True, creationflags=NOWIN, errors='replace')
    out = []; lines = p.stderr.splitlines()
    for i, ln in enumerate(lines):
        if re.search(r'Stream #0:\d+.*: Audio:', ln):
            title = ''
            for nx in lines[i + 1:i + 6]:
                if 'Stream #' in nx: break
                m = re.match(r'\s+(title|handler_name)\s*:\s*(.+)', nx)
                if m and not title and m.group(2).strip().lower() not in ('soundhandler', 'sound handler'): title = m.group(2).strip()
            out.append({'n': len(out) + 1, 'title': title})
    return out

def silence_ratio(path, track, at):
    """how much of 20 seconds on this track is (almost) silent. a mic with noise suppression is quiet a lot, game audio almost never"""
    import numpy as np
    r = subprocess.run([FF, '-v', 'error', '-ss', f'{at:.1f}', '-t', '20', '-i', path, '-map', f'0:a:{track-1}', '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', '-'],
                       capture_output=True, creationflags=NOWIN)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < 8000: return None
    x = x[:len(x) // 800 * 800].reshape(-1, 800)
    db = 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-6)
    return float((db < -48).mean())

_MIC = {}
def find_mic(path):
    """which audio track is only your voice. 0 = none found, use everything"""
    if path in _MIC: return _MIC[path]
    tr = audio_tracks(path); pick = 0; why = 'only 1 audio track, using all audio'
    named = [t for t in tr if re.search(r'\b(mic|microfoon|microphone|voice|stem|me)\b', t['title'], re.I)]
    if named: pick = named[0]['n']; why = f'track {pick} is called "{named[0]["title"]}"'
    elif len(tr) >= 2:
        dur = probe_duration(path) or 60
        spots = [dur * f for f in (0.25, 0.5, 0.75)]
        sil = {}
        for t in tr[1:]:   # track 1 is (almost) always the full mix
            v = [silence_ratio(path, t['n'], a) for a in spots]; v = [x for x in v if x is not None]
            if v: sil[t['n']] = sum(v) / len(v)
        full = [silence_ratio(path, 1, a) for a in spots]; full = sum(x for x in full if x is not None) / max(1, len([x for x in full if x is not None]))
        if sil:
            best = max(sil, key=sil.get)
            if 0.25 <= sil[best] <= 0.97 and sil[best] > full + 0.2: pick = best; why = f'track {best} is often quiet, that looks like your mic'
            else: why = 'no separate mic track found, using all audio and filtering out voicelines'
    _MIC[path] = (pick, why, tr)
    log('Audio:', why)
    return _MIC[path]

# OBS track numbers are not the same as the audio streams in the file: when OBS records tracks 1, 2 and 6,
# the file has 3 audio streams and OBS track 6 is the 3rd. The Clipper remembers which tracks OBS recorded.
_TMAP = {}
def track_map(path):
    """the OBS track number of every audio stream in this recording, e.g. [1, 2, 6]. None = unknown"""
    if path in _TMAP: return _TMAP[path]
    m = None
    try:
        for s_ in list_sess():
            if path in (s_.get('path'), s_.get('live_path')) and s_.get('rec_tracks'): m = s_['rec_tracks']; break
    except Exception: pass
    n = len(audio_tracks(path)) if os.path.exists(path) else 0
    if m and n and len(m) != n: m = None          # the file does not match what OBS said: do not guess
    if not m and n and obs.ok:
        cur = obs_rec_tracks()
        if cur and len(cur) == n: m = cur
    if m: _TMAP[path] = m      # unknown is not remembered: OBS can connect later
    return m
def obs_track_of(path, stream):
    m = track_map(path); return m[stream - 1] if m and 0 < stream <= len(m) else stream
def stream_of(path, track):
    """the audio stream in the file for an OBS track number, or None when that track is not in this recording"""
    m = track_map(path)
    if m: return m.index(track) + 1 if track in m else None
    n = len(audio_tracks(path))
    return track if 0 < track <= n else None

def mic_map(path):
    mt = int(SET.get('mic_track') or 0)
    if mt > 0:
        st = stream_of(path, mt)
        if st: return ['-map', f'0:a:{st-1}']
        if not _TMAP.get(('said', path)): _TMAP[('said', path)] = True; log(f'Track {mt} is not in this recording, finding your mic myself')
        mt = 0
    if mt == 0: mt = find_mic(path)[0]
    return ['-map', f'0:a:{mt-1}'] if mt > 0 else []

_WAVMIC = {}
def friend_words(path, a, b, work):
    """plan F2.3: what your friends say (their own OBS track, for example Discord), as words with times"""
    ft = int(SET.get('friends_track') or 0)
    if ft <= 0: return []
    st_ = stream_of(path, ft); mic = mic_map(path)
    if not st_ or (mic and mic[1] == f'0:a:{st_ - 1}'): return []
    wav = os.path.join(work, 'fr.wav')
    r = run(['-y', '-ss', f'{max(0, a):.2f}', '-t', f'{b - a:.2f}', '-i', path, '-map', f'0:a:{st_ - 1}', '-vn', '-af', 'highpass=f=70,lowpass=f=7800', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav], capture_output=True)
    if not os.path.exists(wav): return []
    fl_ = (SET.get('friends_lang') or '').strip(); old_ = getattr(LANG_TL, 'v', None)
    try:
        if fl_: LANG_TL.v = fl_   # your friends can speak another language than you (you Dutch, a friend English)
        return [[round(x + a, 2), round(y + a, 2), w] for x, y, w in transcribe(wav, 'captions') if w != UNCLEAR]
    except Exception: traceback.print_exc(); return []
    finally: LANG_TL.v = old_
_AF_OK = {'ok': True}
def extract_wav(path, start, dur, out):
    amap = mic_map(path); _WAVMIC[out] = bool(amap)
    base = ['-y', '-ss', f'{max(0, start):.2f}', '-t', f'{dur:.2f}', '-i', path] + amap + ['-vn']
    tail = ['-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', out]
    if _AF_OK['ok']:
        # clean the voice a bit: rumble out, quiet words up. helps the speech model
        r = run(base + ['-af', 'highpass=f=70,lowpass=f=7800,afftdn=nf=-25,dynaudnorm=f=200:g=11'] + tail, capture_output=True, text=True, errors='replace')
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000: return True
        if getattr(LIVE_TL, 'on', False) or getattr(LIVE_TL, 'reading', False): return False   # a file that is still being recorded: try again later
        _AF_OK['ok'] = False; log('Audio filter does not work with this ffmpeg, continuing without it:', (r.stderr or '').strip()[-200:])
    r = run(base + tail, capture_output=True, text=True, errors='replace')
    if r.returncode != 0 or not os.path.exists(out):
        if amap:   # the chosen track does not work: use all audio
            _MIC[path] = (0, 'mic track does not work', _MIC.get(path, (0, '', []))[2])
            r = run(['-y', '-ss', f'{max(0, start):.2f}', '-t', f'{dur:.2f}', '-i', path, '-vn'] + tail, capture_output=True, text=True, errors='replace')
        if r.returncode != 0 or not os.path.exists(out):
            log('Getting the audio out of the recording failed:', (r.stderr or '').strip()[-300:]); return False
    return True

def said_start(words, want, en):
    """a start near `want` that falls in a pause between sentences, so the clip does not begin mid-sentence"""
    best, bs = max(0.0, want), -1.0
    for a, b in zip(words, words[1:]):
        g = b[0] - a[1]
        if want - 4 <= b[0] <= want + 4 and b[0] < en - 6:
            sc = g - abs(b[0] - want) * 0.05
            if g > 0.35 and sc > bs: best, bs = max(0.0, b[0] - 0.25), sc
    return best

def sentence_cut(words, peak, L, dur):
    """clip start and end on natural pauses: start before the moment, end once the reaction is over"""
    gaps = []   # (time, size) pauses between words
    for a, b in zip(words, words[1:]):
        if b[0] - a[1] >= 0.45: gaps.append((a[1], b[0] - a[1]))
    # end: first real pause 2-12 s after the peak
    end = None
    for g, size in gaps:
        if peak + 2 <= g <= peak + 12 and size >= 0.6: end = g + 0.8; break
    if end is None: end = peak + 6
    # start: a pause about 10 s before the peak (enough build-up to get it, not so much that people swipe away).
    # a story ("watch this", "wait for it") may start earlier, up to the longest length you set
    want = 10.0 if not any(SETUP.search(w[2]) for w in words if peak - 20 <= w[0] <= peak - 3) else 16.0
    lo = max(end - L, peak - want - 6)
    cand = [(abs((g + min(size, 0.6) - 0.25) - (peak - want)), g + min(size, 0.6) - 0.25) for g, size in gaps if lo <= g + min(size, 0.6) - 0.25 <= peak - 4]
    start = min(cand)[1] if cand else max(end - L, peak - want)
    return max(0, start), min(dur, end)

def analyse(sid):
    import numpy as np
    s = load_sess(sid)
    path = s.get('path')
    if not path or not os.path.exists(path):
        s['status'] = 'recording not found'; save_sess(s); log('Recording not found:', path); return
    relisten_ = bool(s.pop('relisten', None))
    s['status'] = 'analyseren'; save_sess(s); log('Analysing:', os.path.basename(path)); prog('Checking audio and chat', 2)
    GAME_TL.v = game_quick(s)['id']
    dur = probe_duration(path); step = 0.5
    try: env = audio_env(path, step)
    except Exception: log('Audio analysis failed'); traceback.print_exc(); env = []
    if env and max(env) < -70:   # the chosen track is silent: fall back to all audio
        log('The chosen audio track is silent, using all audio'); _MIC[path] = (0, 'mic track silent', _MIC.get(path, (0, '', []))[2]); env = audio_env(path, step)
    dur = max(dur, len(env) * step)
    if dur < 5:
        s['status'] = 'recording too short or unreadable'; save_sess(s); log('Could not read the length of the recording:', path); return
    s['duration'] = dur; log(f'Recording is {fmt(dur)} long')
    try:   # which audio the captions listen to, shown with the stream (plan F2.3)
        mt = int(SET.get('mic_track') or 0)
        if mt > 0: s['mic'] = {'track': mt, 'why': f'you picked track {mt} in Settings'}
        elif mt < 0: s['mic'] = {'track': 0, 'why': 'you picked all audio in Settings'}
        else: pk, wy, _ = find_mic(path); s['mic'] = {'track': obs_track_of(path, pk) if pk else 0, 'why': wy}
        save_sess(s)
    except Exception: pass
    T = int(dur / step) + 1
    score = np.zeros(T, dtype=np.float32); why = [dict() for _ in range(T)]
    # 1. getting loud (voice band). the first and last seconds are skipped: starting the recording is not a moment
    try:
        if env:
            z = zscore_rolling(env, int(90 / step), floor=3.0)
            z = np.convolve(np.clip(z, 0, 8), np.ones(4) / 4, mode='same')
            skip_a, skip_b = int(10 / step), len(z) - int(4 / step)
            for i in range(min(T, len(z))):
                if i < skip_a or i > skip_b: continue
                if z[i] > 2.0: score[i] += 0.7 * (z[i] - 2.0); why[i]['audio'] = 1
    except Exception: log('Audio analysis failed'); traceback.print_exc()
    # 1a. what you hear without words: laughing, screaming, cheering, a fight (plan F2.5)
    snd = None
    if SET.get('sounds', True):
        try:
            prog('Listening for laughing, screams and fights', 3)
            snd = stream_cache(sid, 'sound', [src_key(path), dur, step, 2], lambda: sound_events(path, dur, step, lambda f: prog(None, 3 + 2 * f)))   # kept: searching again skips this
            ssc, swhy = sound_moments(snd, step)
            for i in range(min(T, len(ssc))):
                if ssc[i] > 0 and (i < int(10 / step) or i > T - int(4 / step)): continue
                score[i] += ssc[i]
                if swhy[i]: why[i]['sound'] = swhy[i]
            cnt_ = {k: int(sum(1 for w_ in swhy if w_ and w_.startswith(k))) for k in ('you laughed', 'you screamed', 'cheering', 'a fight')}
            s = load_sess(sid); s['sounds'] = {k.split()[-1]: v for k, v in cnt_.items()}; save_sess(s)
            log('Heard without words: ' + ', '.join(f'{k} {v // 2}s' for k, v in cnt_.items() if v) if any(cnt_.values()) else 'Heard without words: nothing special')
        except Exception: log('Listening for sounds did not work'); traceback.print_exc()
    # 1b. what you say, over the whole recording (always with an NVIDIA card or a strong processor, else up to 30 min)
    ALL = []
    if SET.get('smart', True) and whisper_ok() and (dur <= 1800 or has_cuda() or (CORES >= 8 and dur <= 5 * 3600)):
        work0 = os.path.join(sdir(sid), 'tmp_full'); os.makedirs(work0, exist_ok=True)
        chunk = LIVE_CHUNK; a0 = 0.0; nchunks = int(math.ceil(dur / chunk)); UNSURE = []
        live = live_cache(sid, path); reused = 0
        tkey_ = {'src': src_key(path), 'lang': cur_lang(), 'model': SET.get('whisper_model', 'auto'), 'v': 1}
        try:   # searched before with the same settings: reuse what was heard (with the unsure words already filled in)
            if not relisten_ and json.load(open(os.path.join(sdir(sid), 'transcript_key.json'), encoding='utf-8')) == tkey_:
                ALL = [tuple(w) for w in json.load(open(os.path.join(sdir(sid), 'transcript.json'), encoding='utf-8'))]; UNSURE = load_unsure(sid)
                if ALL: a0 = dur + 1; log('Reusing what was heard last time (same video, same settings)')
        except Exception: pass
        while a0 < dur:
            c_ = live['chunks'].get(str(int(a0))) if live else None
            if c_ is not None and a0 + chunk + 2 <= dur:   # already heard during the stream: no need to listen again
                ALL += [tuple(w) for w in c_['words'] if w[0] >= (ALL[-1][0] + 0.01 if ALL else 0)]; UNSURE += c_.get('unsure') or []
                reused += 1; a0 += chunk; continue
            s = load_sess(sid); s['status'] = f'luisteren ({int(a0 // chunk) + 1}/{nchunks})'; save_sess(s); prog('Listening to the whole stream', 5 + 70 * a0 / dur)
            wav = os.path.join(work0, 'c.wav'); extract_wav(path, a0, min(chunk + 2, dur - a0), wav)
            try:
                ALL += [(round(a + a0, 2), round(b + a0, 2), w) for a, b, w in transcribe(wav, 'scan', lambda f, a0=a0: prog(None, 5 + 70 * min(dur, a0 + f * chunk) / dur)) if a + a0 >= (ALL[-1][0] + 0.01 if ALL else 0)]
                UNSURE += [round(u + a0, 2) for u in getattr(UNSURE_TL, 'v', [])]
            except Exception: traceback.print_exc()
            a0 += chunk
        if reused:
            log(f'{reused} of {nchunks} parts were already heard during the stream')
            try: json.dump({'live': True}, open(os.path.join(sdir(sid), 'transcript_bron.json'), 'w'))
            except OSError: pass
        shutil.rmtree(work0, ignore_errors=True)
        ALL = collapse_loops(ALL)
        try:
            json.dump(ALL, open(os.path.join(sdir(sid), 'transcript.json'), 'w', encoding='utf-8'))
            json.dump(tkey_, open(os.path.join(sdir(sid), 'transcript_key.json'), 'w', encoding='utf-8'))
            sg_ = speech_game(ALL)
            if sg_:
                s_ = load_sess(sid); s_['game_speech'] = sg_; save_sess(s_); GAME_TL.v = game_quick(s_)['id']
            json.dump(sorted(set(UNSURE)), open(os.path.join(sdir(sid), 'twijfel.json'), 'w', encoding='utf-8'))
        except Exception: pass
        for k, (a, b, w) in enumerate(ALL):
            i = int(a / step)
            if not (0 <= i < T): continue
            phrase = ' '.join(x[2] for x in ALL[k:k + 3] if x[0] - a < 1.5)   # catches "no way", "oh my god"
            m1 = SAY_STRONG.match(re.sub(r'[^\w\' ]', '', phrase)) or (SAY_STRONG.search(w) and SAY_STRONG.search(w))
            v = 1.0 if m1 else 1.2 if SAY_LAUGH.search(w) else 0.5 if SAY_HYPE.search(w) else 0   # words alone count little: "oh my god" happens all the time
            if m1: w = m1.group(0)
            if v:
                for j in range(max(0, i - 2), min(T, i + 3)):
                    score[j] += v * (1 - abs(j - i) * 0.25)
                    if v > why[j].get('sv', 0): why[j]['say'] = w; why[j]['sv'] = v
        # talking fast and a lot at once is a reaction too
        cnt = np.zeros(T, dtype=np.float32)
        for a, b, w in ALL:
            i = int(a / step)
            if 0 <= i < T: cnt[i] += 1
        rate = np.convolve(cnt, np.ones(int(6 / step)), mode='same') / 6.0
        thr_ = max(3.2, float(np.percentile(rate[rate > 0], 92))) if (rate > 0).any() else 3.2   # fast for YOU in this stream, not a fixed number
        for i in range(T):
            if rate[i] > thr_: score[i] += (rate[i] - thr_) * 0.4; why[i]['talk'] = 1   # talking fast alone is weak: it needs a reason close by (see below)
    # 2. chat going off (shifted back: chat reacts a few seconds after the moment)
    chat = load_chat(sid); delay = float(SET.get('chat_delay', 6))
    if chat:
        cnt = np.zeros(T, dtype=np.float32); hype = np.zeros(T, dtype=np.float32); users = [set() for _ in range(T)]; same = {}
        for t, u, msg in chat:
            i = int((t - delay) / step)
            if 0 <= i < T:
                cnt[i] += 1; users[i].add(u)
                if HYPE.search(msg): hype[i] += 1
                k_ = re.sub(r'\W+', '', (msg or '').lower())[:20]
                if k_: same.setdefault((int(i * step // 10), k_), set()).add(u)
        for (b10, k_), us_ in same.items():   # a chat wave: 3+ people typing the same thing (the same emote, "W", "LMAO") in 10 seconds
            if len(us_) >= 3:
                i = min(T - 1, int(b10 * 10 / step)); hype[i] += 0.5 * len(us_)
        k = int(10 / step)
        uniq = np.array([len(x) for x in users], dtype=np.float32)
        c10 = np.convolve(cnt, np.ones(k), mode='same'); h10 = np.convolve(hype, np.ones(k), mode='same'); u10 = np.convolve(uniq, np.ones(k), mode='same')
        zc = zscore_rolling(c10, int(240 / step), floor=2.0, prop=0.35)
        for i in range(T):
            v = max(0, zc[i] - 1.5) + 0.6 * h10[i] + 0.15 * max(0, u10[i] - 3)
            if v > 0.5: score[i] += v; why[i]['chat'] = int(c10[i]); why[i]['hype'] = int(h10[i])
    # 2b. your real matches: multikills, aces, clutches
    md = match_events(s) if gprof().get('matchdata') else None
    if md:
        s = load_sess(sid); s['game_events'] = md['events']; s['game_kills'] = md['kills']; save_sess(s)
        for e in md['events']:
            i0, i1 = int(max(0, e['t0'] - 2) / step), int(e['t'] / step)
            for j in range(max(0, i0), min(T, i1 + int(2 / step))):
                score[j] += e['strength']; why[j]['game'] = e
    # 2c. Twitch clips your viewers made
    tcl = twitch_clip_times(s)
    if tcl:
        s = load_sess(sid); s['twitch_clips'] = tcl; save_sess(s)
        for c_ in tcl:
            i = int(c_['t'] / step)
            for j in range(max(0, i - int(6 / step)), min(T, i + int(3 / step))):
                score[j] += 9; why[j]['tclip'] = c_
    # 2d. you said "clip that" / "clip it": counts like the clip button
    said_clip = []   # (start, end) of the words "clip that"
    for i_, w in enumerate(ALL):
        seg = [x for x in ALL[i_:i_ + 4] if x[0] - w[0] < 2.5]
        ph = re.sub(r"[^\w' ]", '', ' '.join(x[2] for x in seg).lower())
        m_ = CLIP_SAY.match(ph)
        if m_ and (not said_clip or w[0] - said_clip[-1][0] > 10):
            n_ = len(m_.group(0).split()); said_clip.append((w[0], seg[min(n_, len(seg)) - 1][1]))
    if said_clip:
        s = load_sess(sid); have = [m['t'] for m in s.get('markers', [])]
        for t_, e_ in said_clip:
            if not any(abs(t_ - 2 - h) < 8 for h in have): s.setdefault('markers', []).append({'t': round(t_ - 2, 2), 'src': 'stem', 'note': '', 'said': [round(t_, 2), round(e_, 2)]})
        save_sess(s); log(f'You said "clip that" {len(said_clip)}x, those count as the Clip button')
    # talk moments: stretches where you talk a lot and people laugh (for the highlights video)
    if ALL:
        talk = []; tw_ = 30.0; t_ = 0.0
        while t_ < dur - tw_:
            seg = [w for w in ALL if t_ <= w[0] < t_ + tw_]; txt = ' '.join(w[2] for w in seg)
            sc_ = len(seg) / tw_ + 1.5 * len(SAY_LAUGH.findall(txt)) + 0.5 * len(SAY_HYPE.findall(txt))
            talk.append((round(sc_, 2), round(t_, 1))); t_ += 10.0
        talk.sort(reverse=True); picked = []
        for sc_, t_ in talk:
            if sc_ < 2.0 or len(picked) >= 12: break
            if all(abs(t_ - p_) > 35 for _, p_ in picked): picked.append((sc_, t_))
        s = load_sess(sid); s['talk'] = [{'a': t_, 'b': t_ + tw_, 'score': sc_} for sc_, t_ in picked]; save_sess(s)
    # 3. your own clip markers count the most
    for m in s.get('markers', []):
        i = int(m['t'] / step)
        for j in range(max(0, i - int(8 / step)), min(T, i + 1)):
            score[j] += 12; why[j]['marker'] = m.get('src', 'knop')
    # rough candidates
    L = float(SET['clip_len'])
    want = int(SET['max_clips'])
    smart = SET.get('smart', True) and whisper_ok()
    # a reaction needs a reason: what you say only counts fully when something else happens close by
    # (the game, gunshots, laughing or screaming, chat, a sudden loud bit, a marker). "oh my god" on its own is not a moment
    other_ = np.zeros(T, dtype=bool)
    for i in range(T):
        w_ = why[i]
        if any(k in w_ for k in ('game', 'sound', 'chat', 'marker', 'tclip')): other_[i] = True   # not 'audio': talking loud is not a reason by itself
    near_ = np.convolve(other_.astype(np.float32), np.ones(int(10 / step)), mode='same') > 0
    for i in range(T):
        if 'say' in why[i] and not near_[i] and not CLIP_SAY.search(str(why[i].get('say', '')).lower()): score[i] *= 0.4
    order = np.argsort(-score); taken = []; cands = []
    for i in order:
        if len(cands) >= (want * 2 + 4 if smart else want): break
        if score[i] < 1.0 and (len(cands) >= min(3, int(dur // 90)) or score[i] < 0.35): break   # a calm stream still gets a few to choose from
        t = i * step
        if any(abs(t - u) < max(10.0, L * 0.4) for u in taken): continue   # two different things 15 s apart are two moments (copies are removed later)
        taken.append(t)
        w = why[i]; mk = 'marker' in w
        said = None
        if mk:
            mm_ = min(s.get('markers', []), key=lambda m: abs(m['t'] - t)); t = mm_['t'] - 2; said = mm_.get('said')
        reasons = []
        g = w.get('game')
        if g: reasons.append(f"{g['label']} in round {g['round']}" + (f" on {g['map']}" if g.get('map') else '')); t = g['t'] - 1
        if w.get('tclip'): reasons.append(f"Twitch clip by {w['tclip']['by'] or 'a viewer'}")
        if mk: reasons.insert(0, (f'you said "clip that" at {fmt(said[0])}' if said else {'paneel': 'Clip button', 'sneltoets': 'Clip hotkey', 'chat': '!clip in chat', 'website': 'Clip button', 'streamdeck': 'Stream Deck', 'stem': 'you said "clip that"'}.get(w['marker'], 'Clip button')))
        if w.get('chat'): reasons.append(f"chat went off ({w['chat']} messages in 10 sec)")
        if w.get('hype'): reasons.append(f"{w['hype']}x LUL, W, clip and the like")
        if w.get('sound'): reasons.append(w['sound'])
        if w.get('audio') and not w.get('sound'): reasons.append('it suddenly got loud')
        if w.get('say'): reasons.append(f'you said "{w["say"].strip(".,!?")}"')
        cands.append({'id': uuid.uuid4().hex[:8], 't': round(t, 1), 'score': round(float(score[i]), 1), 'reasons': reasons or ['standout moment'], 'marker': mk, 'game': g, 'said': said})
    # fine pass: listen to what you say around each moment
    if smart and cands:
        s['status'] = f'luisteren (0/{len(cands)})'; save_sess(s)
        work = os.path.join(sdir(sid), 'tmp_an'); os.makedirs(work, exist_ok=True)
        for n, c in enumerate(cands):
            a0 = max(0, c['t'] - L - 4); a1 = min(dur, c['t'] + 16)
            if ALL: words = [w for w in ALL if a0 <= w[0] <= a1]
            else:
                wav = os.path.join(work, 'w.wav'); extract_wav(path, a0, a1 - a0, wav)
                try: words = [(round(a + a0, 2), round(b + a0, 2), w) for a, b, w in transcribe(wav, 'scan')]
                except Exception: traceback.print_exc(); words = []
            near = [w for w in words if c['t'] - 8 <= w[0] <= c['t'] + 8]
            txt = ' '.join(w[2] for w in near)
            hy = len(SAY_HYPE.findall(txt)); la = len(SAY_LAUGH.findall(txt))
            rate = len(near) / 16.0
            st_ = len(SAY_STRONG.findall(txt))
            boost = 0 if ALL else 0.5 * hy + 1.0 * st_ + 1.2 * la + max(0, rate - 2.2) * 0.8   # with the full transcript this is already in the score
            c['score'] = round(c['score'] + boost, 1)
            if hy and not any(r.startswith('you said') for r in c['reasons']): c['reasons'].append(f'you reacted ("{SAY_HYPE.search(txt).group(0)}")')
            if la: c['reasons'].append('there was laughing')
            # peak = your last hype word near the moment, else the moment itself
            hw = [w for w in near if SAY_HYPE.search(w[2]) or SAY_LAUGH.search(w[2])]
            peak = hw[-1][0] if hw else c['t']
            if c['marker']: peak = min(peak, c['t'] + 1)
            if c.get('game'): peak = max(peak, c['game']['t'] + 1)
            st, en = sentence_cut(words, peak, L, dur) if words else (max(0, c['t'] - L * 0.7), min(dur, c['t'] + L * 0.3))
            if c.get('game'):   # the whole play must be in it: from the first kill to just after the last
                st = max(0, min(st, c['game']['t0'] - 4)); en = min(dur, max(en, c['game']['t'] + 2.5))
                if en - st > L + 15: st = max(0, en - L - 15)
            if c.get('said'):   # "clip that": the moment is what happened before, and it ends right after you say it
                en = min(dur, c['said'][1] + 0.6); st = said_start(words, en - L, en)
            elif env:   # a reaction without words (a scream, laughing, cheering) belongs to the moment: do not cut it off (plan F2.6)
                if '_envmed' not in locals(): _envmed = float(np.median(env))
                i_ = int(en / step); n_ = 0
                while i_ < len(env) and env[i_] > _envmed + 9 and n_ < 8: i_ += 1; n_ += 1
                if n_: en = min(dur, i_ * step + 0.6); c['reasons'].append('the reaction is kept whole') if n_ >= 3 else None
            if env and not c.get('said'):   # no dead air at the start or the end: begin when something happens, stop when it is over
                if '_envmed' not in locals(): _envmed = float(np.median(env))
                act = lambda t_: (0 <= int(t_ / step) < len(env) and env[int(t_ / step)] > _envmed + 4) or any(abs(w[0] - t_) < 0.6 for w in words)
                t_ = st
                while t_ < peak - 7.5 and not act(t_) and not act(t_ + 0.5): t_ += 0.5   # keep at least 7 s of build-up (the game can be the build-up)
                if t_ - st >= 3: st = t_ - 0.4
                t_ = en
                while t_ > peak + 2.5 and not act(t_) and not act(t_ - 0.5): t_ -= 0.5
                if en - t_ >= 1.5: en = t_ + 0.6
            lt_ = SET.get('learn_timing') or {}   # what you told me before: "starts too early", "the reaction is cut off"
            if not c.get('said'): st = max(0, min(peak - 3, st - float(lt_.get('lead') or 0)))
            en = min(dur, max(peak + 1.5, en + float(lt_.get('tail') or 0)))
            c['start'], c['end'] = round(st, 1), round(en, 1)
            c['words'] = [w for w in words if st - 1 <= w[0] <= en + 1]
            try:
                fw_ = friend_words(path, st - 1, en + 1, work)
                if fw_: c['friend_words'] = fw_
            except Exception: traceback.print_exc()
            c['text'] = ' '.join(w[2] for w in c['words'])[:400]
            c['title'] = title_from(near, hw) or fact_title(c) or fallback_title(c, s)
            if not title_fits(c['title'], c): c['title'] = fact_title(c) or fallback_title(c, s)
            c['hooks'] = hook_options(near, hw, c, s)
            s = load_sess(sid); s['status'] = f'luisteren ({n+1}/{len(cands)})'; save_sess(s); prog('Picking the moments', 75 + 23 * (n + 1) / len(cands))
        shutil.rmtree(work, ignore_errors=True)
    else:
        for c in cands:
            if c.get('said'): st = c['said'][1] + 0.6 - L
            elif c['marker']: st = c['t'] + 7 - L
            else: st = c['t'] - L * 0.72
            c['start'] = round(max(0, st), 1); c['end'] = round(min(dur, max(0, st) + L), 1)
    # what happens on screen (plan F2.4): no moments in a menu, no long spectating at the end, round and match results as reasons
    if cands and SET.get('vision', True) and vision_ok():
        try:
            gid = GAME_TL.v or 'other'
            for n, c in enumerate(cands):
                prog('Looking at the picture', 75 + 23 * (n + 1) / len(cands))
                st, en = c.get('start', 0), c.get('end', 0)
                if en - st < 2: continue
                if SET.get('smile_scan', True) and not c.get('no_cam'):   # your face on cam: smiling or laughing near the peak counts as a reaction
                    try:
                        cam_ = cam_at(s, st) if SET.get('cam_auto', True) else SET['cam']; sw_, _ = probe_size(path); k_ = sw_ / 1920.0
                        rc_ = tuple(int(v * k_) for v in cam_)
                        sm_ = stream_cache(sid, 'smile', [src_key(path), round(c['t'] - 4, 1), rc_], lambda: smile_scan(path, max(0, c['t'] - 4), 9, rc_))
                        if len(sm_) >= 2 and 'you smiled on cam' not in c['reasons']: c['reasons'].append('you smiled on cam'); c['score'] = round(c['score'] * 1.1 + 0.3, 1); c['smile'] = len(sm_)
                    except Exception: pass
                vs_ = stream_cache(sid, 'vision', [src_key(path), round(max(0, st - 1), 1), round(min(dur, en + 4), 1), gid, 2], lambda: vision_scan(path, max(0, st - 1), min(dur, en + 4), gid)); c['_scan'] = vs_
                j = vision_judge(vs_, st, en + 4, c['t'])
                if not j: continue
                c['vision'] = {k: j.get(k) for k in ('menu', 'end', 'buy', 'dead_at', 'spectate_from', 'events', 'score', 'hp')}
                if (j.get('hp') or 999) <= 30 and 'round_win' in j['events']: c['score'] = round(c['score'] * 1.3 + 1, 1)   # won the round on almost no health
                if j['menu'] > 0.6:
                    c['score'] = round(c['score'] * 0.25, 1); c['reasons'].append('mostly a menu on screen')
                    if not any('chat' in r_ or 'friend' in r_ for r_ in c['reasons']) and not c.get('marker'): c['drop'] = True   # lobby, agent select, queue: out (unless chat or a marker)
                elif j.get('end', 0) > 0.4: c['score'] = round(c['score'] * 0.15, 1); c['drop_soft'] = True   # the end screen: talking while the scoreboard shows is almost never a moment
                elif j['buy'] > 0.7: c['score'] = round(c['score'] * 0.6, 1)
                if j.get('spectate_from') and j['spectate_from'] > c['t'] + 2 and j['spectate_from'] + 1.5 < en and not c.get('said'):
                    c['end'] = round(max(st + 6, j['spectate_from'] + 1.5), 1); c['reasons'].append('ends before the spectating')
                if 'win' in j['events'] or 'round_win' in j['events']: c['score'] = round(c['score'] + 1.5, 1)
                for r_ in j['reasons']:
                    if r_ not in c['reasons']: c['reasons'].append(r_)
            log('Looked at the picture of ' + str(len(cands)) + ' moments')
        except Exception: log('Looking at the picture did not work'); traceback.print_exc()
    # every moment needs something that really happened, not only words: the game (a kill, an event), gunshots, laughing or screaming,
    # chat going off, a marker, a Twitch clip, or something on screen (round won, you died). talking alone ("oh my god", "bro", "what") is out,
    # unless the AI later says it is really good (7 or more)
    EVID = ('game', 'sound', 'chat', 'marker', 'tclip')
    for c in cands:
        st_, en_ = c.get('start', c['t'] - 10), c.get('end', c['t'] + 5)
        ev_ = any(k in why[i] for i in range(max(0, int(st_ / step)), min(T, int(en_ / step) + 1)) for k in EVID)
        vi_ = c.get('vision') or {}
        if vi_.get('events') or vi_.get('dead_at'): ev_ = True
        if not ev_ and not c.get('said'): c['no_evidence'] = True
    # which agent you play (the agent select screen), for the AI's story, the title and the hashtags
    if cands and (GAME_TL.v or '') == 'valorant' and SET.get('agent_scan', True) and ((md or {}).get('agents') or (vision_ok() and (SET.get('speed_mode') or 'normal') != 'fast')):
        try:
            ags_ = (md or {}).get('agents') or stream_cache(sid, 'agents', [src_key(path), round(dur)], lambda: agent_scan(path, dur))   # match data knows it, else the agent select screen
            for c in cands:
                pre_ = [a_ for t_, a_ in ags_ if t_ <= c['t']]
                if pre_: c['agent'] = pre_[-1]
            if ags_: log('You played ' + ', '.join(dict.fromkeys(a_ for _, a_ in ags_)))
        except Exception: traceback.print_exc()
    # what is this moment about? a timeline of everything that happens (what you say, shots, laughing, the screen, chat),
    # then the story: where it starts making sense, the payoff, where the reaction is over, and the edit that belongs to it
    if cands and SET.get('brief', True):
        try:
            top = sorted(cands, key=lambda c: -c['score'])[:int(speed_n('judge') if (SET.get('speed_mode') or 'normal') != 'normal' else (SET.get('llm_judge_n') or 30))]
            port = (llm_use('small') if llm_two() else llm_start()) if llm_ready() and SET.get('llm_judge', True) else 0   # both models there: the small one reads all 30 fast
            gname = (GP.get(GAME_TL.v or '') or {}).get('name', GAME_TL.v or '') if GP else (GAME_TL.v or '')
            for n, c in enumerate(top):
                if c.get('said'): continue   # "clip that" moments keep the cut around what you asked
                prog('Working out what each moment is about', 86 + 4 * (n + 1) / len(top))
                texts_ = []
                if n < int(SET.get('screen_text_n') or speed_n('screen')) and vision_ok():   # the text on screen around it: chat messages, killfeed
                    try: texts_ = stream_cache(sid, 'screen', [src_key(path), round(max(0, c['t'] - 60), 1), round(min(dur, c['t'] + 12), 1)], lambda: screen_texts(path, max(0, c['t'] - 60), min(dur, c['t'] + 12)))
                    except Exception: traceback.print_exc()
                    nm_ = []   # names on the screen (chat, killfeed): the doubt check uses them to spell names right
                    for g_ in texts_ or []:
                        tx_ = g_.get('text') or ''
                        if g_.get('region') == 'chat':
                            m_ = re.match(r"\s*(?:\([^)]*\)\s*|\[[^\]]*\]\s*)?([\w#.-]{3,20})\s*:", tx_)
                            if m_: nm_.append(m_.group(1).split('#')[0])
                        elif g_.get('region') == 'killfeed': nm_ += [x for x in re.findall(r'[A-Za-z][\w.-]{2,15}', tx_) if x.upper() != x or len(x) > 4]
                    if nm_: c['screen_names'] = list(dict.fromkeys(nm_))[:20]
                    kb_ = killer_name(texts_)
                    if kb_: c['killed_by'] = kb_   # the death screen says who killed you: used for revenge stories
                lines, items, a0 = moment_timeline(c, ALL or c.get('words') or [], why, step, c.get('_scan'), snd, max(0, c['t'] - 60), c['t'] + 15, texts_)
                if c.get('agent'): lines.insert(0, f"The streamer plays {c['agent']}.")
                rb_ = brief_rules(c, items, a0, c['t'])
                b_ = brief_merge(llm_brief(c, lines, a0, gname, SET.get('language') or 'en', port) if port else {}, rb_, items)
                if not b_: continue
                st, en = max(0, b_['start']), min(dur, b_['end'])
                if en - st < 6: en = min(dur, st + 6)
                if en - st > L + 10:
                    keep_ = b_.get('cause') if b_.get('cause') is not None else b_['payoff']
                    st = min(max(st, b_['payoff'] - (L + 10) * 0.7), keep_ - 2.5)   # never cut away what you react to
                    if en - st > 60: st = en - 60
                c['start'], c['end'] = round(float(st), 1), round(float(en), 1); c['t'] = float(b_['payoff'])
                def _fl(v): return float(v) if hasattr(v, 'item') else ([_fl(x) for x in v] if isinstance(v, list) else v)
                c['brief'] = {k: _fl(b_.get(k)) for k in ('about', 'type', 'cause', 'payoff', 'zoom', 'replay', 'focus', 'layout', 'music', 'by', 'context')
                              if b_.get(k) is not None and b_.get(k) is not False and not (isinstance(b_.get(k), (str, list)) and len(b_.get(k)) == 0)}
                if b_.get('about'): c['reasons'].insert(0, b_['about'][0].lower() + b_['about'][1:])
                c['evidence'] = evidence_lines(items, c['start'], c['end'])
                fo_ = (c['brief'].get('focus') or {}) if isinstance(c['brief'].get('focus'), dict) else {}
                if fo_.get('region') == 'chat':   # who wrote the message you reacted to
                    m_ = re.match(r"\s*(?:\([^)]*\)\s*|\[[^\]]*\]\s*)?([\w#.-]{3,20})\s*:", fo_.get('text') or '')
                    if m_: c['chat_name'] = m_.group(1).split('#')[0]   # what the AI saw, heard and read: shown as "Why?" on the card
                t_ = tidy_title(b_.get('title') or '')
                if t_ and title_fits(t_, c): c['title'] = t_; c['hooks'] = [t_] + [h for h in (c.get('hooks') or []) if h != t_][:2]
                if b_.get('by') == 'ai':
                    try:
                        sc_ = max(1, min(10, int(b_.get('score') or 5))); c['ai'] = {'score': sc_, 'why': b_.get('about', '')}
                        strong_ = bool(rb_.get('focus')) or (rb_.get('cause') is not None and any(k_ in ' '.join(c['reasons']) for k_ in ('screamed', 'laughed', 'chat went', 'messages')))
                        c['score'] = round(c['score'] * max(1.0 if strong_ else 0, 0.2 + 0.16 * sc_), 1)   # the AI decides: a 10 counts almost double, a 4 or lower is out
                        if sc_ <= 4 and not strong_: c['drop'] = True   # ...unless the facts are clear: you read a message from the screen, or a real cause plus a scream or laugh
                    except Exception: pass
                if any(x['k'] == 'speech' for x in items) and any(x['k'] == 'note' for x in items):
                    c['score'] = round(c['score'] * 0.35, 1)   # mumbling while nothing happens: not a moment (with or without the AI)
            if port:   # with the AI, a moment it did not look at can never beat one it liked
                for c in cands:
                    if c not in top: c['score'] = round(c['score'] * 0.6, 1)
            log(f'Worked out the story of {len(top)} moments' + (' with the AI' if port else ''))
        except Exception: log('Working out the story did not work'); traceback.print_exc()
    for c in cands: c.pop('_scan', None)
    # the AI judges the best candidates (local model, only after the stream): a mark from 1 to 10, why, and a better title
    if cands and SET.get('llm_judge', True) and llm_ready():
        try:
            top = sorted(cands, key=lambda c: -c['score'])[:int(SET.get('llm_judge_n') or 20)]
            port = llm_start(); gid = GAME_TL.v or ''
            gname = (GP.get(gid) or {}).get('name', gid) if GP else gid
            for n, c in enumerate(top):
                if not port: break
                if c.get('ai'): continue   # already judged while working out the story
                prog('The AI is judging the moments', 90 + 9 * (n + 1) / len(top))
                j = llm_judge(c, ALL or c.get('words') or [], gname, SET.get('language') or 'en', port)
                if not j: continue
                c['ai'] = j; c['score'] = round(c['score'] * (0.2 + 0.16 * j['score']), 1)
                if j['score'] <= 3: c['drop'] = True
                if j['score'] >= 8 and j.get('why'): c['reasons'].insert(0, 'AI: ' + j['why'].lower())
                elif j['score'] <= 3: c['reasons'].append('AI: ' + (j.get('why') or 'not much happens').lower())
                t_ = tidy_title(j.get('title') or '')
                if t_ and title_fits(t_, c) and j['score'] >= 5:
                    c['title'] = t_; c['hooks'] = [t_] + [h for h in (c.get('hooks') or []) if h != t_][:2]
            log(f'The AI judged {len(top)} moments')
        except Exception: log('The AI could not judge the moments'); traceback.print_exc()
    try: story_bonus(ALL, cands, s)
    except Exception: traceback.print_exc()
    for c in cands:
        c['feat'] = moment_keys(c); p2_ = taste2_prob(c['feat'])   # your personal score model (after 12 choices)
        if p2_ is not None:
            c['score'] = round(c['score'] * (0.5 + p2_) * (0.3 if blocked_kind(c['reasons']) else 1), 1); c['taste'] = round(p2_, 2)
            if p2_ >= 0.7: c['reasons'].append('you often keep clips like this')
            elif p2_ <= 0.25: c['reasons'].append('you often throw clips like this away')
        else:
            tm_ = taste_mult(c['reasons'], (c.get('end') or 0) - (c.get('start') or 0) or None)
            c['score'] = round(c['score'] * tm_, 1)
            if tm_ >= 1.2: c['reasons'].append('you often keep clips like this')
        if not (c.get('brief') or {}).get('context'):
            rc_ = rule_context(c)
            if rc_: c.setdefault('brief', {})['context'] = rc_
        if not c.get('title'): c['title'] = fallback_title(c, load_sess(sid))
        if not c.get('hooks'): c['hooks'] = hook_options([], [], c, load_sess(sid))   # learn from what you kept before
    for c in cands:   # only words, nothing happened: out, unless the AI says it is really good
        if c.get('no_evidence') and not ((c.get('ai') or {}).get('score', 0) >= 7): c['drop'] = True
    # side by side: the AI compares the best ones two at a time and fixes the order
    if SET.get('llm_judge', True) and SET.get('ai_compare', True):
        try:
            if llm_ready():
                sw_ = compare_top([c for c in cands if not c.get('drop')], llm_use('smart') if llm_two() else llm_start())   # the smart one decides on the best
                if sw_: log(f'The AI compared the best moments side by side and changed the order {sw_} time(s)')
        except Exception: traceback.print_exc()
    # what the AI threw out stays out. nothing good enough? then no moments, and the app says so (no forced bad clips)
    kept_ = [c for c in cands if not c.get('drop')]
    if len(kept_) < len(cands): log(f'The AI threw out {len(cands) - len(kept_)} moments that are not good enough')
    no_good = None
    if cands and not kept_:
        b_ = max(cands, key=lambda c: c['score'])
        no_good = {'n': len(cands), 'best': b_.get('title') or '', 'why': ((b_.get('ai') or {}).get('why') or '; '.join(b_.get('reasons', [])[:2]))[:140]}
        log(f'Nothing in this stream was good enough for a short ({len(cands)} candidates checked)')
    cands = kept_
    # no near-copies: when two clips mostly overlap, keep the best one (and its reasons)
    best = []
    for c in sorted(cands, key=lambda c: -c['score']):
        a1, b1 = c.get('start', c['t'] - L * 0.7), c.get('end', c['t'] + L * 0.3)
        dup = next((d for d in best if min(b1, d.get('end', d['t'] + L * 0.3)) - max(a1, d.get('start', d['t'] - L * 0.7)) > 0.4 * min(b1 - a1, d.get('end', 0) - d.get('start', 0) or L)), None)
        if dup: dup['reasons'] = list(dict.fromkeys(dup['reasons'] + c['reasons']))[:5]; continue
        best.append(c)
    moments = sorted(best[:want], key=lambda m: m['t'])
    # the doubt check: words the speech model was not sure about, inside the moments you get, are heard again and filled in
    if ALL and moments and SET.get('doubt_check', True):
        try:
            prog('Checking unsure words', 99)
            nms_ = [n_ for m in moments for n_ in (m.get('screen_names') or [])]
            new_, left_, opts_, nfix_ = doubt_pass(sid, path, ALL, load_unsure(sid), [(m['start'] - 1, m['end'] + 1) for m in moments], nms_, budget=speed_n('doubt'))
            if nfix_ or opts_:
                ALL = new_
                json.dump(ALL, open(os.path.join(sdir(sid), 'transcript.json'), 'w', encoding='utf-8'))
                json.dump(left_, open(os.path.join(sdir(sid), 'twijfel.json'), 'w', encoding='utf-8')); save_opts(sid, opts_)
                for m in moments:
                    m['words'] = [w for w in ALL if m['start'] - 1 <= w[0] <= m['end'] + 1]; m['text'] = ' '.join(w[2] for w in m['words'])[:400]
        except Exception: log('The doubt check did not work'); traceback.print_exc()
    for m in moments:
        th = os.path.join(sdir(sid), f"thumb_{m['id']}.jpg")
        run(['-y', '-ss', str(m['t']), '-i', path, '-frames:v', '1', '-vf', 'scale=480:-2', th])
    # stories: moments that belong together (a promise and the result, a toxic player and getting him back, something that comes back)
    stories = []
    try:
        links = link_stories(moments, ALL)
        # a promise you made ("watch me ace this round") is often not a moment by itself: look for it in everything you said
        for k_, w_ in enumerate(ALL):
            ph_ = ' '.join(x[2] for x in ALL[k_:k_ + 10] if x[0] - w_[0] < 4)
            if PROMISE.match(ph_) or (PROMISE.search(ph_) and PROMISE.search(ph_).start() == 0):
                res_ = next((m for m in moments if 15 <= m['start'] - w_[0] <= 1200 and ((m.get('vision') or {}).get('events') or (m.get('vision') or {}).get('dead_at')
                             or any(r in ' '.join(m.get('reasons', [])) for r in ('won', 'ace', 'clutch', 'fight', 'kill', 'died', 'lost')))), None)
                if res_ and not any(l_['b'] == res_['id'] for l_ in links):
                    fail_ = any(r in ' '.join(res_.get('reasons', [])) for r in ('died', 'lost')) or (res_.get('brief') or {}).get('type') == 'fail'
                    links.append({'a': None, 'a_t': (max(0, w_[0] - 3), min(dur, w_[0] + 6)), 'b': res_['id'], 'gap': round(res_['start'] - w_[0]),
                                  'why': 'famous last words: you said you would do it, and then this' if fail_ else 'you said you would do it, and you did', 'label': 'FAMOUS LAST WORDS...' if fail_ else 'AND THEN...'})
        if llm_ready() and SET.get('llm_judge', True) and len(moments) >= 2:
            for l_ in llm_link(sorted(moments, key=lambda m: m['t']), llm_start()):
                if not any(x.get('a') == l_['a'] and x['b'] == l_['b'] for x in links): links.append(l_)
        byid = {m['id']: m for m in moments}
        # revenge: the player who killed you, or who was toxic in chat, shows up in your killfeed later
        try:
            for A_ in sorted(moments, key=lambda m: m['t']):
                nm_ = A_.get('killed_by') or A_.get('chat_name')
                if not nm_: continue
                for B_ in [m for m in moments if 15 <= m['start'] - A_['end'] <= 2400][:6]:
                    names_ = B_.get('screen_names')
                    if names_ is None and vision_ok():
                        names_ = [w_ for g_ in screen_texts(path, B_['start'], B_['end']) if g_.get('region') == 'killfeed' for w_ in re.findall(r'[A-Za-z][\w.-]{2,15}', g_.get('text') or '')]
                        B_['screen_names'] = names_
                    if any(same_name(nm_, x) for x in names_ or []):
                        tox_ = bool(A_.get('chat_name'))
                        links.append({'a': A_['id'], 'b': B_['id'], 'by': 'rules', 'label': 'REVENGE' if not tox_ else 'GUESS WHO...',
                                      'why': (f'{nm_} was toxic in chat, and later you got him' if tox_ else f'{nm_} killed you, and later you got him back')}); break
        except Exception: traceback.print_exc()
        # the AI checks the weak links (only shared words): do these two really tell one story?
        if llm_ready() and SET.get('llm_judge', True):
            try:
                port_ = llm_start(); keep_ = []
                for l_ in links:
                    if l_.get('by', 'rules') == 'rules' and l_.get('a') and (l_['why'].startswith('the same thing') or 'shows up again' in l_['why']):
                        if not llm_story_ok(byid.get(l_['a']), byid.get(l_['b']), l_['why'], port_): continue
                    keep_.append(l_)
                links = keep_
            except Exception: traceback.print_exc()
        def part_of(m):
            br_ = m.get('brief') or {}; pk_ = br_.get('cause') or m['t']
            return max(m['start'], pk_ - 14), min(m['end'], max(pk_, m['t']) + 8)
        def a_parts(A_):
            """the first moment: one piece, or two when you react to a chat message a while after it appeared (message, then your reaction)"""
            br_ = A_.get('brief') or {}; cz_ = br_.get('cause'); py_ = br_.get('payoff') or A_['t']
            fo_ = br_.get('focus') if isinstance(br_.get('focus'), dict) else {}
            if cz_ is not None and fo_.get('region') == 'chat' and py_ - cz_ > 9:
                return [(max(A_['start'], cz_ - 2), cz_ + 3.5, ''), (py_ - 3.5, min(A_['end'], py_ + 4), 'THEN...')]
            a1, a2 = part_of(A_); return [(a1, a2, '')]
        for l_ in links[:6]:
            B_ = byid.get(l_['b']); A_ = byid.get(l_['a']) if l_.get('a') else None
            if not B_: continue
            pa_ = a_parts(A_) if A_ else [(l_['a_t'][0], l_['a_t'][1], '')]; b1, b2 = part_of(B_)
            gap_ = b1 - pa_[-1][1]; gl = f'{int(gap_ // 60)} MINUTES LATER' if gap_ >= 120 else 'LATER...' if gap_ >= 30 else 'THEN...'
            if l_.get('label') and l_['label'] not in ('LATER...', 'THEN...'): gl = l_['label']
            stories.append({'id': uuid.uuid4().hex[:8], 'why': l_['why'], 'by': l_.get('by', 'rules'), 'title': (B_.get('title') or '')[:40], 'hook': l_.get('label') or '',
                            'parts': [{'sid': sid, 'a': round(x[0], 1), 'b': round(x[1], 1), 'label': x[2]} for x in pa_] + [{'sid': sid, 'a': round(b1, 1), 'b': round(b2, 1), 'label': gl}],
                            'mids': [A_['id'] if A_ else None, B_['id']]})
        # the whole match in under a minute: the best moments in order, with the score between them
        if len(moments) >= 3 and SET.get('match_story', True):
            mt_ = sorted(sorted(moments, key=lambda m: -m['score'])[:4], key=lambda m: m['t']); parts_ = []; tot_ = 0
            for k_, m in enumerate(mt_):
                br_ = m.get('brief') or {}; pk_ = br_.get('payoff') or m['t']; cz_ = br_.get('cause')
                a_ = max(m['start'], (cz_ - 3) if cz_ is not None else pk_ - 7); b_ = min(m['end'], pk_ + 4)
                if tot_ + (b_ - a_) > 58: break
                sc_ = (m.get('vision') or {}).get('score')
                lab_ = '' if k_ == 0 else (f'ROUND {sc_[0]}-{sc_[1]}' if sc_ else 'THEN...')
                parts_.append({'sid': sid, 'a': round(a_, 1), 'b': round(b_, 1), 'label': lab_}); tot_ += b_ - a_
            if len(parts_) >= 3:
                stories.append({'id': uuid.uuid4().hex[:8], 'why': f'the whole stream in {int(tot_)} seconds: your {len(parts_)} best moments in order', 'by': 'rules', 'kind': 'match',
                                'title': 'THE WHOLE MATCH IN 60 SECONDS', 'hook': 'THE WHOLE MATCH IN 60 SECONDS', 'parts': parts_, 'mids': [m['id'] for m in mt_[:len(parts_)]]})
        if stories: log(f'Found {len(stories)} stories: moments that belong together')
    except Exception: traceback.print_exc()
    s = load_sess(sid); s['moments'] = moments + [m for m in s.get('moments', []) if m.get('manual')]; s['stories'] = [x for x in s.get('stories', []) if x.get('edited')] + stories;   # stories you made yourself stay
    s['no_good'] = no_good
    try:
        s['best5'] = best_with_variety(moments); s['baseline'] = stream_baseline(sid, ALL, dur)
        for m in moments:
            pv_ = predict_views(m.get('feat'))
            if pv_: m['pred'] = pv_   # how a moment like this usually does (from the views you filled in)
        s['summary'] = stream_summary(moments, stories, llm_start() if (llm_ready() and SET.get('llm_judge', True)) else None)
        tl_ = set(s.get('tclip_learned') or [])
        for m in moments:   # a viewer clipped it: the personal model learns that this kind of moment is good
            if 'tclip' in (m.get('feat') or []) and int(m['t']) not in tl_: taste2_note(m['feat'], True); tl_.add(int(m['t']))
        s['tclip_learned'] = sorted(tl_)
    except Exception: traceback.print_exc()
    s['duration'] = dur; s['status'] = 'klaar'; save_sess(s)   # keep clips you picked yourself
    log(f'Done: {len(moments)} moments found in {s["title"]}')
    made = [(float(x.get('start') or 0), float(x.get('end') or 0)) for x in s.get('shorts', [])]
    def has_short(m):   # searching again must not make the same shorts twice
        return any(min(m['end'], e) - max(m['start'], a_) > 0.5 * max(1.0, m['end'] - m['start']) for a_, e in made)
    auto_pick = [m for m in sorted(moments, key=lambda m: -m['score']) if not has_short(m)][:int(SET.get('auto_shorts_n', 3))]
    if SET.get('auto_shorts'):
        for m in auto_pick:
            pre = next((p for p in SET.get('presets', []) if p.get('name') == SET.get('auto_preset')), {})
            lrn = learned_look(game_for(sid, m['start']))['auto'] if SET.get('learn_look', True) else {}
            lrn = {k: v for k, v in lrn.items() if k not in pre}   # your own preset wins over what was learned
            br = m.get('brief') or {}; story = {}
            if br.get('layout') and 'layout' not in pre and 'layout' not in lrn: story['layout'] = br['layout']   # the story says: the reaction matters (cam) or the play (game)
            mf = music_for_mood(br.get('music')) if SET.get('auto_music', True) else None
            if mf: story['music'] = {'file': mf, 'vol': 0.22, 'duck': True}
            JOBS.put(('render', {'sid': sid, 'start': m['start'], 'end': m['end'], 'title': m.get('title', ''), 'hook': m.get('title', ''), 'captions': SET['captions'], 'mid': m['id'], 'auto': True,
                                 **story, **lrn, **({'learned': sorted(lrn)} if lrn else {}),
                                 **{k: v for k, v in pre.items() if k in ('layout', 'style', 'cap_scale', 'cap_y', 'progress', 'endcard', 'zoom', 'jumpcut', 'sfx', 'cam_h', 'game_x')}}))
        n_auto = len(auto_pick)
        if n_auto: log(f'Making the best {n_auto} shorts automatically, they will show up in your inbox'); STATE['auto_left'] = STATE.get('auto_left', 0) + n_auto
    notify('Stream checked', f'{len(moments)} moments found in {s["title"]}.' + (' Making your shorts now.' if SET.get('auto_shorts') and auto_pick else ''))

def fallback_title(c, s=None):
    """a hook when nothing clear was said: your !clip note, or what made the moment stand out"""
    if c.get('game'):
        g = c['game']; return f"{g['label']}{' WITH THE ' + g['weapon'].upper() if g.get('weapon') and g['label'] in ('ACE', '4K') else ''}"[:40]
    if c.get('marker') and s:
        near = [m for m in s.get('markers', []) if abs(m['t'] - c['t']) < 12 and (m.get('note') or '').strip()]
        if near: return near[0]['note'].strip()[:36]
    ks = reason_keys(c.get('reasons'))
    if 'laugh' in ks: return "I CAN'T STOP LAUGHING"
    if 'scream' in ks: return 'I LOST IT'
    if 'fight' in ks: return 'WHAT A FIGHT'
    if 'chat' in ks: return 'CHAT WENT CRAZY'
    if 'marker' in ks: return 'WAIT FOR IT...'
    return 'WATCH THIS'

def hook_options(near, hw, c, s):
    """up to 3 different hooks to choose from"""
    out = []; src = []
    def add(x, why='standard'):
        x = re.sub(r'\s+', ' ', (x or '').strip().upper())
        if x and x not in out and title_fits(x, c) and not CLIP_SAY.search(x.lower()): out.append(x); src.append(why)
    add(title_from(near, hw), 'what you said')
    add(fact_title(c), 'the match data')
    if near:   # the second best phrase
        phrases = []; cur = [near[0]]
        for a, b in zip(near, near[1:]):
            if b[0] - a[1] > 0.35 or re.search(r'[.!?]$', a[2]): phrases.append(cur); cur = []
            cur.append(b)
        phrases.append(cur)
        ranked = sorted(phrases, key=lambda ph: -(len(SAY_STRONG.findall(' '.join(w[2] for w in ph))) * 3 + len(SAY_HYPE.findall(' '.join(w[2] for w in ph)))))
        for ph in ranked[:3]:
            t = re.sub(r"[^\w' !?]", '', ' '.join(w[2] for w in ph[:6] if w[2] != UNCLEAR)).strip()
            t = tidy_title(t)
            if t and not SAY_LAUGH.fullmatch(t.lower()): add(t, 'what you said')
    add(fallback_title(c, s), 'why it is a moment')
    g = c.get('game')
    if g: add({'ACE': 'THEY NEVER STOOD A CHANCE', '4K': 'ONE MORE AND IT WAS AN ACE'}.get(g['label'], 'HOW DID I WIN THIS'))
    else:
        hk = gprof().get('hooks') or []
        if hk: add(hk[(int(c.get('t', 0)) // 7) % len(hk)])
    add('WAIT FOR IT...')
    c['hooks_src'] = src[:3]   # where each title comes from, shown when you pick one
    return out[:3]

_DANGLE = {'I', "I'M", 'IM', 'THE', 'A', 'AN', 'TO', 'AND', 'OR', 'BUT', 'OF', 'IN', 'ON', 'AT', 'MY', 'YOUR', 'SO', 'IF', 'WITH', 'FOR', "IT'S", 'UH', 'UM', 'LIKE', 'JUST', 'HAVE', 'GONNA', 'DE', 'HET', 'EEN', 'EN', 'IK', 'JE', 'IS', 'DAT', 'DIE'}
def tidy_title(t):
    """a spoken title must read like a hook: no half words at the end, at least 2 real words.
    one word ("NO", "YO", "4") or a name alone is not a title"""
    w = re.sub(r"[^\w' !?]", '', (t or '').upper()).split()
    while w and w[-1].strip('!?') in _DANGLE: w.pop()
    while w and w[0].strip('!?') in ('UH', 'UM', 'AND', 'BUT', 'SO', 'LIKE'): w.pop(0)
    if len(w) < 2 or len(' '.join(w)) < 7 or sum(1 for x in w if len(x.strip("!?'")) >= 3) < 1: return ''
    k = [x.strip('!?') for x in w]
    if len(set(k)) == 1 and len(k) < 3: return ''          # "NO NO"
    return ' '.join(w)[:38]

def title_from(near, hw):
    """a short hook for the top of the short: the phrase you shouted, cut on a pause"""
    if not near: return ''
    # phrases = words split on pauses
    phrases = []; cur = [near[0]]
    for a, b in zip(near, near[1:]):
        if b[0] - a[1] > 0.35 or re.search(r'[.!?]$', a[2]): phrases.append(cur); cur = []
        cur.append(b)
    phrases.append(cur)
    best = None
    for ph in phrases:
        txt = ' '.join(w[2] for w in ph)
        sc = len(SAY_STRONG.findall(txt)) * 3 + len(SAY_HYPE.findall(txt)) + len(SAY_LAUGH.findall(txt)) - (len(ph) > 6)
        if hw and any(w in ph for w in hw): sc += 1
        if best is None or sc > best[0]: best = (sc, ph)
    words = [w[2] for w in best[1] if w[2] != UNCLEAR][:6]
    t = re.sub(r"[^\w' !?]", '', ' '.join(words)).strip().upper()
    if SAY_LAUGH.fullmatch(t.lower() or 'x') or CLIP_SAY.search(t.lower()): return ''   # "clip that" is the reason, not the title
    return tidy_title(t)

CLAIMS = re.compile(r"\b(ACE|[2-5]K|1 ?V ?[2-5]|CLUTCH|ONE ?TAP|NINJA ?DEFUSE)\b")
def title_fits(t, c):
    """a title must not claim something the game data says did not happen (an "ACE" that was a 3K)"""
    g = c.get('game')
    m = CLAIMS.search((t or '').upper())
    if not m or not g: return True
    claim = m.group(1).replace(' ', '')
    lab = (g.get('label') or '').upper().replace(' ', '')
    if claim in ('ACE', '2K', '3K', '4K', '5K'): return claim == lab or (claim == '5K' and lab == 'ACE') or (claim == 'ACE' and lab == '5K')
    if claim.startswith('1V') or claim == 'CLUTCH': return 'CLUTCH' in lab or lab.startswith('1V')
    return True

def fact_title(c):
    """a title from what happened (situation, action, result), from the match data"""
    g = c.get('game')
    if not g: return ''
    lab = (g.get('label') or '').upper(); wpn = (g.get('weapon') or '').upper(); mp = (g.get('map') or '').upper()
    if lab in ('ACE', '5K'): return f'ACE WITH THE {wpn}' if wpn else (f'ACE ON {mp}' if mp else 'ACE')
    if lab == '4K': return f'4K WITH THE {wpn}' if wpn else '4 KILLS IN ONE ROUND'
    if 'CLUTCH' in lab or lab.startswith('1V'): return f'{lab} TO WIN THE ROUND'
    if lab == '3K': return f'3K ON {mp}' if mp else '3 KILLS, ONE ROUND'
    return ''


# ---------------------------------------------------------------- 7.0: listening along during the stream (plan F2.1)
# every few minutes the newest finished part of the recording is turned into text, at low priority and with few cores.
# after the stream the analysis only has to do the last part: the moments are there within minutes, also after 3 hours.
LIVE_CHUNK = 300.0
def live_cache_file(sid): return os.path.join(sdir(sid), 'live_luisteren.json')
def live_cache(sid, path):
    try:
        c = json.load(open(live_cache_file(sid), encoding='utf-8'))
        if c.get('chunk') != LIVE_CHUNK or c.get('mic') != int(SET.get('mic_track') or 0) or c.get('lang') != (SET.get('language') or 'en'): return None
        if os.path.normcase(os.path.abspath(c.get('path') or '')) != os.path.normcase(os.path.abspath(path)): return None
        return c
    except Exception: return None
LISTEN = {'sid': None, 'done': 0, 'why': '', 'at': 0, 'found': []}
def live_listen_ok():
    if not SET.get('live_listen', True) or not whisper_ok() or SET.get('smart', True) is False: return 'off'
    if not (has_cuda() or CORES >= 8): return 'this pc is not strong enough to do it during the stream'
    if pc_busy() or (len(_CPU['hist']) >= 2 and sum(_CPU['hist']) / len(_CPU['hist']) > 80): return 'your pc is busy'
    return ''
def live_listen_once():
    sid = CUR.get('id')
    if not sid: return
    s = load_sess(sid); path = s.get('live_path')
    LISTEN['sid'] = sid
    if not path or not os.path.exists(path): LISTEN['why'] = 'waiting for the recording file'; return
    why = live_listen_ok()
    if why: LISTEN['why'] = why; return
    if os.path.splitext(path)[1].lower() == '.mp4':
        LISTEN['why'] = 'an MP4 cannot be read while it records (MKV can)'; return
    c = live_cache(sid, path) or {'path': path, 'chunk': LIVE_CHUNK, 'mic': int(SET.get('mic_track') or 0), 'lang': SET.get('language') or 'en', 'chunks': {}}
    elapsed = time.time() - float(s.get('start') or time.time())
    a0 = 0.0
    while str(int(a0)) in c['chunks']: a0 += LIVE_CHUNK
    if a0 + LIVE_CHUNK + 20 > elapsed: LISTEN['why'] = ''; return   # the next part is not finished yet
    work = os.path.join(sdir(sid), 'tmp_live'); os.makedirs(work, exist_ok=True)
    wav = os.path.join(work, 'c.wav')
    try:
        LIVE_TL.on = True
        try:
            if not extract_wav(path, a0, LIVE_CHUNK + 2, wav): LISTEN['why'] = 'the recording cannot be read yet'; return
            words = [(round(a + a0, 2), round(b + a0, 2), w) for a, b, w in transcribe(wav, 'scan')]
        finally: LIVE_TL.on = False
        found = []
        try: found = live_found(words, wav, a0)   # plan F2.1: show likely moments already during the stream
        except Exception: traceback.print_exc()
        c['chunks'][str(int(a0))] = {'words': words, 'unsure': [round(u + a0, 2) for u in getattr(UNSURE_TL, 'v', [])], 'at': time.time(), 'found': found}
        tmp = live_cache_file(sid) + '.tmp'; json.dump(c, open(tmp, 'w', encoding='utf-8')); os.replace(tmp, live_cache_file(sid))
        LISTEN.update(done=len(c['chunks']), why='', at=time.time(), found=sorted([f for ch in c['chunks'].values() for f in ch.get('found') or []], key=lambda f: -f['t'])[:8])
        log(f'Listened along during the stream: {fmt(a0 + LIVE_CHUNK)} done')
    except Exception: traceback.print_exc(); LISTEN['why'] = 'did not work this time'
    finally: shutil.rmtree(work, ignore_errors=True)
def live_found(words, wav, a0):
    """likely moments in a piece that was just heard: what you said and how you sounded"""
    out = []
    for i, w in enumerate(words):
        ph = re.sub(r"[^\w' ]", '', ' '.join(x[2] for x in words[i:i + 3] if x[0] - w[0] < 1.5)).lower()
        m_ = SAY_STRONG.match(ph)
        why = 'you said "clip that"' if CLIP_SAY.match(ph) else (f'you said "{m_.group(0)}"' if m_ else None)
        if why and not any(abs(w[0] - o['t']) < 20 for o in out): out.append({'t': round(w[0], 1), 'why': why})
    try:
        import numpy as np
        r = subprocess.run([FF, '-v', 'error', '-i', wav, '-f', 's16le', '-ac', '1', '-ar', str(SOUND_SR), '-'], capture_output=True, creationflags=NOWIN)
        x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        sc, why = sound_moments(sound_scan(x, None, 0.5, True))
        for k in np.argsort(-sc)[:3]:
            t = round(float(a0 + k * 0.5), 1)
            if sc[k] >= 1.4 and why[k] and not any(abs(t - o['t']) < 20 for o in out): out.append({'t': t, 'why': why[k]})
    except Exception: pass
    return out

LIVE_TL = threading.local()
def live_listen_loop():
    while True:
        time.sleep(45)
        try: live_listen_once()
        except Exception: traceback.print_exc()
