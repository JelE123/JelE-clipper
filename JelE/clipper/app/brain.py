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
    ex = jload(EX2_F, []); MODEL2.update(at=time.time(), n=len(ex))
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
