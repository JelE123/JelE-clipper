# the moment brain: a personal score model, proof per moment, variety, comparing the best ones side by side,
# and being honest when nothing was good enough

# ---------------------------------------------------------------- what a moment is made of (for the personal model)
def moment_keys(c):
    """everything we know about a moment as short labels: what happened, the type, the AI's mark, the screen, the length"""
    ks = set(reason_keys(c.get('reasons') or []))
    br = c.get('brief') or {}; vi = c.get('vision') or {}; ai = c.get('ai') or {}
    if br.get('type'): ks.add('type:' + br['type'])
    if br.get('focus'): ks.add('focus:' + ((br['focus'] or {}).get('region') or 'screen') if isinstance(br['focus'], dict) else 'focus')
    if br.get('cause') is not None: ks.add('cause')
    if ai.get('score'): ks.add('ai_hi' if ai['score'] >= 7 else 'ai_lo' if ai['score'] <= 4 else 'ai_mid')
    for e in vi.get('events') or []: ks.add('vis:' + e)
    if vi.get('dead_at') is not None: ks.add('vis:dead')
    if (vi.get('hp') or 999) <= 30: ks.add('low_hp')
    if c.get('no_evidence'): ks.add('noev')
    if c.get('game'): ks.add('game:' + str((c['game'] or {}).get('label') or 'event').lower())
    if c.get('marker'): ks.add('marker')
    L_ = (c.get('end') or 0) - (c.get('start') or 0)
    ks.add('len:short' if L_ < 15 else 'len:long' if L_ > 35 else 'len:mid')
    return sorted(ks)

EX2_F = os.path.join(DATA, 'voorbeelden2.json')
MODEL2 = {'at': 0, 'w': None, 'voc': [], 'n': 0}
def taste2_note(keys, good):
    if not keys: return
    ex = jload(EX2_F, []); ex.append({'k': list(keys), 'y': 1 if good else 0, 'at': time.time()}); jsave(EX2_F, ex[-800:]); MODEL2['at'] = 0
def taste2_model():
    """your personal score model: learns from every moment you keep, edit or throw away (with the reason). after 12 choices it starts to count"""
    if time.time() - MODEL2['at'] < 60: return MODEL2
    import numpy as np
    ex = jload(EX2_F, [])
    try:   # views you filled in: the best third counts as good, the worst third as bad
        vw = [e for e in lib_load().values() if (e.get('views') or 0) > 0 and e.get('sid')][-60:]
        if len(vw) >= 6:
            vs = sorted(e['views'] for e in vw); lo, hi = vs[len(vs) // 3], vs[2 * len(vs) // 3]
            for e in vw:
                if e['views'] >= hi or e['views'] <= lo:
                    k_ = feat_of(e)
                    if k_: ex.append({'k': k_, 'y': 1 if e['views'] >= hi else 0, 'at': e.get('at') or time.time()})
    except Exception: pass
    MODEL2.update(at=time.time(), n=len(ex))
    if len(ex) < 12 or len({e['y'] for e in ex}) < 2: MODEL2['w'] = None; return MODEL2
    voc = sorted({k for e in ex for k in e['k']})
    X = np.array([[1.0] + [1.0 if k in e['k'] else 0.0 for k in voc] for e in ex]); y = np.array([e['y'] for e in ex], float)
    age = np.array([(time.time() - e['at']) / 86400 for e in ex]); sw = np.exp(-age / 90)
    lam = 0.15 if len(ex) < 40 else 0.05   # few examples: careful, many: trust them more
    w = np.zeros(X.shape[1])
    for _ in range(500):
        p = 1 / (1 + np.exp(-X @ w)); w -= 0.4 * (X.T @ ((p - y) * sw) / sw.sum() + lam * w)
    MODEL2.update(w=w.tolist(), voc=voc); return MODEL2
def taste2_prob(keys):
    m = taste2_model()
    if not m['w']: return None
    z = m['w'][0] + sum(wt for k, wt in zip(m['voc'], m['w'][1:]) if k in keys)
    return 1 / (1 + math.exp(-max(-30, min(30, z))))
def feat_of(e):
    """the labels of the moment behind a short in the library"""
    try:
        s = load_sess(e.get('sid')); m = next((x for x in s.get('moments', []) if x.get('id') == e.get('mid')), None)
        return (m.get('feat') or moment_keys(m)) if m else None
    except Exception: return None

# ---------------------------------------------------------------- proof: what the AI saw, heard and read
def evidence_lines(items, a, b):
    """the timeline of a moment, short: [[seconds, what, detail]], game and screen first, a few things you said"""
    out = []; says = 0; last = {}
    nice = {'say': 'you said', 'you': 'you', 'loud': 'loud', 'sound': 'sound', 'game sound': 'game sound', 'screen': 'screen', 'chat': 'chat'}
    for x in sorted(items or [], key=lambda x: x['t']):
        if not (a - 1 <= x['t'] <= b + 1) or x['k'] == 'note': continue
        k = str(x['k'])
        if k == 'say':
            if says >= 3: continue
            says += 1
        elif x['t'] - last.get(k, -99) < 4 and k in ('loud', 'you', 'sound', 'game sound'): continue   # one line per few seconds of the same thing
        last[k] = x['t']
        lab = nice.get(k) or (k.replace('on screen (', '').rstrip(')') + ' on screen' if k.startswith('on screen (') else k)
        out.append([round(float(x['t']), 1), lab[:24], str(x['v'])[:80]])
    return out[:12]

def rule_context(c):
    """a context card without the AI: the score and your health, when the screen showed them"""
    vi = c.get('vision') or {}; parts = []
    if vi.get('score') and any(e in (vi.get('events') or []) for e in ('round_win', 'round_loss')): parts.append(f"ROUND {vi['score'][0]}-{vi['score'][1]}")
    if (vi.get('hp') or 999) <= 30: parts.append(f"{vi['hp']} HP LEFT")
    return ' · '.join(parts)

# ---------------------------------------------------------------- the stream's own normal
def stream_baseline(sid, ALL, dur):
    """how you normally sound in THIS stream: words per minute and chat per minute, so a quiet stream and a loud stream are judged fairly"""
    out = {}
    try:
        if ALL and dur > 60:
            import numpy as np
            per = np.zeros(int(dur // 60) + 1)
            for w in ALL: per[min(len(per) - 1, int(w[0] // 60))] += 1
            out['wpm'] = float(np.median(per[per > 0])) if (per > 0).any() else 0
        chat = load_chat(sid)
        if chat and dur > 60: out['cpm'] = round(len(chat) / (dur / 60), 2)
    except Exception: pass
    return out

# ---------------------------------------------------------------- side by side: the AI picks the better of two (more reliable than loose marks)
def llm_compare(c1, c2, port):
    def card(c): return f"{(c.get('brief') or {}).get('about') or c.get('title')}; {'; '.join((c.get('reasons') or [])[:4])}; said: \"{(c.get('text') or '')[:160]}\""
    msg = [{'role': 'system', 'content': 'You pick which gaming moment makes the better TikTok short for strangers. Answer only "A" or "B".'},
           {'role': 'user', 'content': f'A: {card(c1)}\nB: {card(c2)}\nWhich one is better?'}]
    a = (llm_chat(msg, 4, 0.0, port) or '').strip().upper()[:1]
    return a if a in ('A', 'B') else None
def compare_top(cands, port, n=8):
    """one pass of bubble sort on the top n with the AI: neighbours swap when the AI clearly likes the lower one"""
    top = sorted(cands, key=lambda c: -c['score'])[:n]
    if len(top) < 2 or not port: return 0
    swaps = 0
    for i in range(len(top) - 1):
        a_, b_ = top[i], top[i + 1]
        if llm_compare(a_, b_, port) == 'B' and llm_compare(b_, a_, port) == 'A':   # asked both ways round: no luck of the order
            a_['score'], b_['score'] = b_['score'], a_['score']; top[i], top[i + 1] = b_, a_; swaps += 1
    return swaps

# ---------------------------------------------------------------- Best 5 with variety
def best_with_variety(moments, n=5):
    """the 5 best, but not five times the same kind: a second moment of the same kind has to be clearly better"""
    rest = sorted(moments, key=lambda m: -m['score']); pick = []; seen = {}
    while rest and len(pick) < n:
        def eff(m):
            k = (m.get('brief') or {}).get('type') or ('scream' if any('scream' in r for r in m.get('reasons', [])) else 'other')
            return m['score'] * (0.75 ** seen.get(k, 0)), k
        m = max(rest, key=lambda m: eff(m)[0]); k = eff(m)[1]
        pick.append(m); rest.remove(m); seen[k] = seen.get(k, 0) + 1
    return [m['id'] for m in pick]

QUALITY_FLOOR = 2.5   # below this nothing is worth a short

# ---------------------------------------------------------------- names on screen (revenge stories)
def killer_name(texts):
    """the death screen: 'KILLED BY name' -> name"""
    for g in texts or []:
        tx = (g.get('text') or '').strip()
        m = re.search(r'KILLED\s*BY\s*[:\-]?\s*([A-Za-z0-9][\w#.-]{2,20})', tx, re.I)
        if m and m.group(1).upper() not in ('THE', 'YOU'): return m.group(1).split('#')[0]
    for i, g in enumerate(texts or []):   # the name is often its own line under KILLED BY
        if re.fullmatch(r'\s*KILLED\s*BY\s*', g.get('text') or '', re.I):
            below = [h for h in texts if h is not g and abs(h['t'] - g['t']) < 0.6 and h.get('box') and g.get('box') and h['box'][1] > g['box'][1]]
            if below:
                h = min(below, key=lambda h: h['box'][1] - g['box'][1]); m = re.match(r'\s*([A-Za-z0-9][\w#.-]{2,20})', h.get('text') or '')
                if m: return m.group(1).split('#')[0]
    return None
def same_name(a, b):
    """two names read from the screen are the same player (the text reader can miss a letter)"""
    import difflib
    a, b = re.sub(r'\W', '', (a or '').lower()), re.sub(r'\W', '', (b or '').lower())
    if len(a) < 3 or len(b) < 3: return False
    return a == b or (min(len(a), len(b)) >= 5 and (a in b or b in a)) or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85
def llm_story_ok(A, B, why, port):
    """the AI says yes or no: do these two moments really tell one story?"""
    if not A or not B: return True
    def card(m): return f"{(m.get('brief') or {}).get('about') or m.get('title')} | said: {' '.join((m.get('text') or '').split()[:20])}"
    msg = [{'role': 'system', 'content': 'You check if two moments from one gaming stream tell ONE story when shown after each other (a promise and the result, a toxic player and revenge, a joke that comes back). Answer only "yes" or "no".'},
           {'role': 'user', 'content': f'First: {card(A)}\nLater: {card(B)}\nLink found: {why}\nOne story?'}]
    a = (llm_chat(msg, 3, 0.0, port) or '').strip().lower()
    return not a.startswith('no')

def cover_frame(s, mo, a, b):
    """the best picture for a cover: just after the payoff (your biggest reaction plus the action), else the loudest second"""
    try:
        br = (mo or {}).get('brief') or {}
        if br.get('payoff') is not None and a <= br['payoff'] <= b: return round(min(b - 0.2, br['payoff'] + 0.4), 2)
        env = clip_env(s['path'], a, b - a, 0.25)
        if len(env): return round(a + float(env.argmax()) * 0.25, 2)
    except Exception: pass
    return round((a + b) / 2, 2)

def my_titles(n=6):
    """titles you typed yourself or kept (shorts you made, not the automatic ones you left alone), newest first"""
    out = []
    try:
        items = sorted(lib_load().values(), key=lambda e: -(e.get('at') or 0))
        for e in items:
            t = (e.get('title') or '').strip()
            if not t or e.get('test') or len(t) > 40: continue
            if (not e.get('auto')) or e.get('status') in ('goed', 'posted') or (e.get('views') or 0) > 0:
                if t.upper() not in out: out.append(t.upper())
            if len(out) >= n: break
    except Exception: pass
    return out

# ---------------------------------------------------------------- how good is the AI for you? (your own test set)
def ai_check():
    """your choices are the test: shorts you made or kept = good moments, moments you removed as boring or wrong = bad ones.
    per stream: how many good ones the last search found, and how many bad ones it still picked"""
    good = {}; bad = {}
    for e in lib_load().values():
        if e.get('test') or not e.get('sid'): continue
        if (not e.get('auto')) or e.get('status') in ('goed', 'posted'): good.setdefault(e['sid'], []).append((e.get('start', 0), e.get('end', 0)))
    try:
        for ln in open(FEEDBACK_F, encoding='utf-8'):
            try: x = json.loads(ln)
            except Exception: continue
            m = x.get('moment') or {}
            if x.get('sid') and m and any(r in (x.get('reasons') or []) for r in ('boring', 'wrong')): bad.setdefault(x['sid'], []).append((m.get('start', 0), m.get('end', 0)))
    except OSError: pass
    def hit(r, ms): return any(min(r[1], m.get('end', 0)) - max(r[0], m.get('start', 0)) > 0.4 * max(1, r[1] - r[0]) for m in ms)
    rows = []; G = Gf = Bd = Bp = 0
    for sid in set(good) | set(bad):
        try: s = load_sess(sid)
        except Exception: continue
        ms = [m for m in s.get('moments', []) if not m.get('manual')]
        g_ = good.get(sid, []); b_ = bad.get(sid, [])
        gf = sum(1 for r in g_ if hit(r, ms)); bp = sum(1 for r in b_ if hit(r, ms))
        G += len(g_); Gf += gf; Bd += len(b_); Bp += bp
        rows.append({'sid': sid, 'title': s.get('title'), 'good': len(g_), 'good_found': gf, 'bad': len(b_), 'bad_picked': bp})
    return {'good': G, 'good_found': Gf, 'bad': Bd, 'bad_picked': Bp, 'streams': sorted(rows, key=lambda r: -(r['good'] + r['bad']))[:12]}

def learned_summary():
    """what the personal model learned, in plain words: what you keep and what you skip"""
    m = taste2_model()
    nice = {'scream': 'screaming', 'laugh': 'laughing', 'chat': 'chat going off', 'say': 'things you say', 'fail': 'fails', 'win': 'won rounds', 'game': 'multikills and clutches',
            'tclip': 'viewer clips', 'marker': 'clip button', 'noev': 'talking without action', 'len:long': 'long clips', 'len:short': 'short clips', 'low_hp': 'low health plays',
            'focus:chat': 'reading chat', 'cause': 'clear setup', 'ai_hi': 'what the AI rates high', 'ai_lo': 'what the AI rates low'}
    if not m.get('w'): return {'n': m.get('n', 0), 'like': [], 'skip': []}
    pairs = sorted(zip(m['voc'], m['w'][1:]), key=lambda x: -x[1])
    lab = lambda k: nice.get(k) or (k.split(':', 1)[1] + ' moments' if k.startswith('type:') else k.replace('vis:', 'screen: ').replace('game:', ''))
    return {'n': m.get('n', 0), 'like': [lab(k) for k, w in pairs if w > 0.3][:5], 'skip': [lab(k) for k, w in pairs[::-1] if w < -0.3][:5]}

# ---------------------------------------------------------------- everything kept per stream: searching again is quick
def stream_cache(sid, name, key, fn, keep=400):
    """the result of fn() for this stream and key, saved in the stream's folder (the same work is never done twice)"""
    p = os.path.join(sdir(sid), f'cache_{name}.json'); k = json.dumps(key, sort_keys=True)
    try: d = json.load(open(p, encoding='utf-8'))
    except Exception: d = {}
    if k in d: return d[k]
    v = fn()
    try:
        d[k] = v
        if len(d) > keep: d = dict(list(d.items())[-keep:])
        json.dump(d, open(p, 'w', encoding='utf-8'))
    except Exception: pass
    return v
def src_key(path):
    try: return [os.path.getsize(path), int(os.path.getmtime(path)), VERSION.split('.')[0]]
    except OSError: return [0, 0, VERSION]

SPEED = {'fast': {'screen': 5, 'doubt': 40, 'judge': 12}, 'normal': {'screen': 15, 'doubt': 150, 'judge': 30}, 'thorough': {'screen': 30, 'doubt': 400, 'judge': 50}}
def speed_n(k):
    """how much work per search: Fast, Normal or Thorough (Settings)"""
    return SPEED.get(SET.get('speed_mode') or 'normal', SPEED['normal'])[k]

def best_loop_end(path, start, end):
    """for a loop: the end point (in the last 2.5 s) whose picture looks most like the first picture and where it is quiet, so the jump back is smooth"""
    try:
        import numpy as np
        def frames(a, b, fps=10):
            r = subprocess.run([FF, '-v', 'error', '-ss', f'{a:.2f}', '-t', f'{b - a:.2f}', '-i', path, '-map', '0:v:0', '-vf', f'fps={fps},scale=64:36,format=gray', '-f', 'rawvideo', '-'], capture_output=True, creationflags=NOWIN)
            n = len(r.stdout) // (64 * 36); return np.frombuffer(r.stdout[:n * 64 * 36], dtype=np.uint8).reshape(n, 36, 64).astype(np.float32) if n else None
        f0 = frames(start, start + 0.2); fe = frames(max(start + 3, end - 2.5), end)
        if f0 is None or fe is None or not len(fe): return end
        env = clip_env(path, max(start + 3, end - 2.5), min(2.5, end - start - 3), 0.1)
        best, bi = None, len(fe) - 1
        for i in range(len(fe)):
            d = float(((fe[i] - f0[0]) ** 2).mean()) / 255.0
            q = float(env[min(len(env) - 1, i)]) if len(env) else 0
            sc = d + max(0, q + 30) * 0.4   # loud = a bad place to jump
            if best is None or sc < best: best, bi = sc, i
        return round(max(start + 3, end - 2.5) + bi / 10.0, 2)
    except Exception: return end

# ---------------------------------------------------------------- how many views a moment like this usually gets
def predict_views(keys):
    """from the views you filled in: moments with the same labels -> 'high', 'normal' or 'low' (needs 6 shorts with views)"""
    try:
        vw = [e for e in lib_load().values() if (e.get('views') or 0) > 0 and e.get('sid')][-80:]
        if len(vw) < 6: return None
        lv = lambda e: math.log10(e['views'] + 1); avg = sum(lv(e) for e in vw) / len(vw)
        ks = set(keys or []); num = den = 0.0
        for e in vw:
            f = set(feat_of(e) or [])
            if not f: continue
            sim = len(ks & f) / max(1, len(ks | f))
            if sim > 0.2: num += sim * (lv(e) - avg); den += sim
        if den < 0.5: return None
        d = num / den
        return 'high' if d > 0.25 else 'low' if d < -0.25 else 'normal'
    except Exception: return None

# ---------------------------------------------------------------- the stream in two sentences
def stream_summary(moments, stories, port=None):
    if not moments: return ''
    types = collections.Counter(((m.get('brief') or {}).get('type') or 'moment') for m in moments)
    rule = f"{len(moments)} moments: " + ', '.join(f'{n} {k}' for k, n in types.most_common(4)) + (f", and {len(stories)} stor{'y' if len(stories) == 1 else 'ies'} that link moments" if stories else '') + '.'
    if not port: return rule
    try:
        rows = '\n'.join(f"- {int(m['t'] // 60)}:{int(m['t'] % 60):02d} {((m.get('brief') or {}).get('about') or m.get('title') or '')[:80]}" for m in sorted(moments, key=lambda m: m['t'])[:15])
        a = llm_chat([{'role': 'system', 'content': 'Summarise a gaming stream in at most 2 short sentences for the streamer, plain and friendly, no hashtags, no emojis.'},
                      {'role': 'user', 'content': 'Moments of the stream:\n' + rows}], 90, 0.4, port)
        a = re.sub(r'\s+', ' ', a or '').strip()
        return a[:280] if len(a) > 20 else rule
    except Exception: return rule

# ---------------------------------------------------------------- captions in another language (local AI)
def translate_lines(lines, to='en', port=None):
    """['line', ...] -> the same lines in the other language (one per line), or None"""
    port = port or llm_start()
    if not port or not lines: return None
    name = {'en': 'English', 'nl': 'Dutch'}.get(to, 'English')
    body = '\n'.join(f'{i + 1}. {l}' for i, l in enumerate(lines[:60]))
    a = llm_chat([{'role': 'system', 'content': f'Translate these caption lines of a gaming clip to {name}. Keep it short and natural, like the streamer talks. Keep game names (agents, weapons, maps) as they are. Answer with the same numbered list, one line per number, nothing else.'},
                  {'role': 'user', 'content': body}], 900, 0.2, port)
    out = {}
    for ln in (a or '').splitlines():
        m = re.match(r'\s*(\d+)[.)]\s*(.+)', ln)
        if m: out[int(m.group(1)) - 1] = m.group(2).strip()
    if len(out) < max(1, len(lines[:60]) * 0.7): return None
    return [out.get(i, l) for i, l in enumerate(lines[:60])] + lines[60:]

# ---------------------------------------------------------------- a demo stream to try the app without streaming first
def make_demo():
    """a 70 second practice video (made here, no footage of anyone), with two Clip presses, so you can try every step"""
    d_ = os.path.join(DATA, 'demo'); os.makedirs(d_, exist_ok=True); out = os.path.join(d_, 'demo_stream.mp4')
    if not os.path.exists(out):
        vf = ("drawbox=x=0:y=0:w=iw:h=ih:color=0x0b1020@0.35:t=fill,drawtext=text='DEMO STREAM':x=40:y=40:fontsize=52:fontcolor=white,"
              "drawtext=text='Round %{eif\\:1+t/20\\:d}':x=(w-tw)/2:y=30:fontsize=40:fontcolor=white,"
              "drawtext=text='KILLED BY':x=(w-tw)/2:y=h/3:fontsize=70:fontcolor=white:enable='between(t,52,58)',"
              "drawbox=x=1460:y=80:w=420:h=60:color=black@0.5:t=fill:enable='between(t,18,26)',"
              "drawtext=text='You  [Vandal]  Enemy':x=1480:y=95:fontsize=30:fontcolor=white:enable='between(t,18,26)'")
        af = "aevalsrc='0.25*sin(2*PI*220*t)*between(mod(t,9),0,0.25)+0.6*sin(2*PI*660*t)*between(t,20,20.4)+0.6*sin(2*PI*600*t)*between(t,45,46)':s=48000:d=70"
        r = run(['-y', '-f', 'lavfi', '-i', 'testsrc2=s=1920x1080:r=30:d=70', '-f', 'lavfi', '-i', af, '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                 '-c:a', 'aac', '-shortest', out], capture_output=True, text=True, errors='replace')
        if not os.path.exists(out): raise RuntimeError('making the demo failed: ' + (r.stderr or '')[-200:])
    s = new_session(title='Demo stream (practice)', path=out, start=time.time())
    sid = s['id'] if isinstance(s, dict) else s
    s = load_sess(sid); s['demo'] = True; s['markers'] = [{'t': 21.0, 'src': 'paneel', 'note': 'demo'}, {'t': 46.0, 'src': 'paneel', 'note': 'demo'}]; save_sess(s)
    JOBS.put(('analyse', sid)); return sid

REF_DIR = os.path.join(DATA, 'voorbeeldshorts')   # reference shorts you like (only for yourself)

# ---------------------------------------------------------------- the Test button next to every key (the keys never leave config.js)
def key_test(which):
    try:
        if which == 'henrik':
            key, name, tag = CFG.get('HENRIK_KEY'), CFG.get('RIOT_NAME'), CFG.get('RIOT_TAG')
            if not key: return {'ok': False, 'why': 'No HenrikDev key in config.js'}
            if not (name and tag): return {'ok': False, 'why': 'Your Riot name and tag are missing in config.js'}
            d = http_json(f'https://api.henrikdev.xyz/valorant/v2/account/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}', {'Authorization': key})
            return {'ok': bool((d or {}).get('data')), 'why': 'Works: your account was found' if (d or {}).get('data') else 'The key works, but your account was not found'}
        if which == 'twitch':
            cid, sec = CFG.get('TWITCH_CLIENT_ID'), CFG.get('TWITCH_CLIENT_SECRET')
            if not (cid and sec): return {'ok': False, 'why': 'No Twitch app in config.js'}
            tok = http_json('https://id.twitch.tv/oauth2/token', data=urllib.parse.urlencode({'client_id': cid, 'client_secret': sec, 'grant_type': 'client_credentials'}).encode()).get('access_token')
            return {'ok': bool(tok), 'why': 'Works: Twitch said yes' if tok else 'Twitch said no'}
        if which == 'obs':
            ok = bool(getattr(obs, 'ok', False))
            return {'ok': ok, 'why': 'Connected to OBS' if ok else 'Not connected: is OBS open and the websocket on (Tools > WebSocket Server Settings)?'}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'why': {401: 'The key is wrong (401)', 403: 'The key is not allowed (403)', 404: 'Not found (404): check your name and tag', 429: 'Too many tries, wait a minute'}.get(e.code, f'Error {e.code}')}
    except Exception as e: return {'ok': False, 'why': 'No connection: ' + str(e)[:80]}
    return {'ok': False, 'why': 'Unknown key'}

# ---------------------------------------------------------------- captions in another language (the local AI translates, the timing stays)
def translate_words(words, to='en'):
    """words [(a, b, text, ...)] -> the same lines in another language. each line keeps its time; the new words share it evenly"""
    if not words or not llm_ready(): return words
    lines = []; cur = []
    for w in words:
        if cur and (w[0] - cur[-1][1] > 0.5 or len(cur) >= 10 or re.search(r'[.!?]$', cur[-1][2])): lines.append(cur); cur = []
        cur.append(w)
    if cur: lines.append(cur)
    name = {'en': 'English', 'nl': 'Dutch', 'de': 'German', 'fr': 'French', 'es': 'Spanish'}.get(to, to)
    src = '\n'.join(f'{i + 1}. ' + ' '.join(x[2] for x in ln if x[2] != UNCLEAR) for i, ln in enumerate(lines))
    msg = [{'role': 'system', 'content': f'Translate gaming stream captions into casual spoken {name}. Keep names of agents, weapons and players. Keep it short. Answer only JSON like {{"1": "...", "2": "..."}}.'},
           {'role': 'user', 'content': src}]
    try:
        r = llm_chat(msg, 900, 0.2, llm_start()); m = re.search(r'\{.*\}', r or '', re.S); d = json.loads(m.group(0)) if m else {}
    except Exception: traceback.print_exc(); return words
    out = []
    for i, ln in enumerate(lines):
        tx = str(d.get(str(i + 1)) or '').split()
        if not tx: out += ln; continue
        a, b = ln[0][0], ln[-1][1]; step = (b - a) / len(tx)
        out += [(round(a + k * step, 2), round(a + (k + 1) * step, 2), t_) + tuple(ln[0][3:]) for k, t_ in enumerate(tx)]
    return out

# ---------------------------------------------------------------- a posting plan that fills itself
def plan_fill(lib=None, days=7):
    """every short that is ready to post (and not planned) gets the next free time slot ("every day at 18:00"). best ones first"""
    slots = [x.strip() for x in str(SET.get('post_slots') or '').replace(';', ',').split(',') if re.fullmatch(r'\d{1,2}:\d{2}', x.strip())]
    if not slots: return 0
    own = lib is None; lib = lib if lib is not None else lib_load(); now = time.time()
    taken = {round(e['plan_at'] / 60) for e in lib.values() if e.get('plan_at')}
    free = []
    for d in range(days + 1):
        base = time.localtime(now + d * 86400)
        for sl in slots:
            hh, mm = map(int, sl.split(':'))
            t = time.mktime((base.tm_year, base.tm_mon, base.tm_mday, hh, mm, 0, 0, 0, -1))
            if t > now + 600 and round(t / 60) not in taken: free.append(t)
    free.sort(); n = 0
    ready = sorted([(fn, e) for fn, e in lib.items() if e.get('status') == 'goed' and not e.get('plan_at') and not e.get('posted_on') and not e.get('archived') and not e.get('test')],
                   key=lambda x: -(x[1].get('score') or 0))
    for (fn, e), t in zip(ready, free):
        e['plan_at'] = t; e['plan_done'] = False; e['plan_auto'] = True; short_settle(e); n += 1
    if n and own: lib_save(lib)
    return n

def predict_views(e):
    """a rough guess of the views a short will get: your median views, times how much your score model likes this kind of moment"""
    try:
        vs = sorted(x['views'] for x in lib_load().values() if (x.get('views') or 0) > 0)
        if len(vs) < 5: return None
        med = vs[len(vs) // 2]; p = taste2_prob(feat_of(e) or [])
        if p is None: return None
        return int(round(med * (0.4 + 1.6 * p), -1 if med > 100 else 0))
    except Exception: return None

def action_x(path, start, dur, default=0.5):
    """where the action is, left to right (0..1): the columns with the most movement over the clip, pulled towards the middle
    (in shooters the crosshair, and so the action, is in the middle). stays at default when nothing stands out"""
    import numpy as np
    W, H = 320, 180
    r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-ss', f'{max(0, start):.2f}', '-t', f'{max(1, dur):.2f}', '-i', path, '-map', '0:v:0',
                        '-vf', f'fps=4,scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True, creationflags=NOWIN)
    n = len(r.stdout) // (W * H)
    if n < 4: return default
    f = np.frombuffer(r.stdout[:n * W * H], dtype=np.uint8).reshape(n, H, W).astype(np.int16)
    d = np.abs(np.diff(f, axis=0))[:, int(H * 0.12):int(H * 0.88), :]   # leave out the top and bottom HUD
    col = d.mean(axis=(0, 1)); col = np.convolve(col, np.ones(41) / 41, mode='same')
    x = np.arange(W) / W; score = col * np.exp(-((x - 0.5) ** 2) / (2 * 0.18 ** 2))
    if col.max() < 3 or score.max() < 1.3 * np.median(score): return default
    best = float(np.argmax(score)) / W
    return round(min(0.75, max(0.25, 0.5 + (best - 0.5) * 0.7)), 3)
