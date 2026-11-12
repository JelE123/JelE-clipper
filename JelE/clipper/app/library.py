# JelE Clipper part: library, taste, search, insights, trash. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- library (every short, with where it came from) and your taste
LIB_F = os.path.join(DATA, 'bibliotheek.json'); TASTE_F = os.path.join(DATA, 'smaak.json')
def lib_load():
    try: return json.load(open(LIB_F, encoding='utf-8'))
    except Exception: return {}
def lib_save(d):
    with LOCK: json.dump(d, open(LIB_F, 'w', encoding='utf-8'), indent=1)

# a short goes: to review (nieuw, made automatically) -> ready to post (goed) -> scheduled (gepland) -> posted (gepost).
# Making a short never means it is posted: only you mark that, per platform.
PLAT_NAMES = {'tiktok': 'TikTok', 'shorts': 'YouTube Shorts', 'reels': 'Instagram Reels'}
def short_settle(e):
    """the status that fits what is known: posted somewhere = posted, a date planned = scheduled, else ready"""
    if e.get('posted_on'):
        e['status'] = 'gepost'; e['posted_at'] = min(e['posted_on'].values()); return e
    e.pop('posted_at', None)
    if e.get('status') in ('nieuw', 'concept'): return e
    e['status'] = 'gepland' if e.get('plan_at') and (e['plan_at'] > time.time() or not e.get('plan_done')) else 'goed'
    return e

def short_mark_posted(e, platform, on):
    pon = dict(e.get('posted_on') or {})
    plats = list(SET.get('platforms') or PLAT_NAMES) if platform == 'all' else [platform]
    for p_ in plats:
        if on: pon.setdefault(p_, time.time())
        else: pon.pop(p_, None)
    e['posted_on'] = pon; return short_settle(e)

def lib_migrate():
    """older libraries: views filled in means it was posted; 'posted' without platforms stays posted"""
    lib = lib_load(); ch = False
    for e in lib.values():
        if e.get('test'): continue
        if e.get('status') == 'gepost' and not e.get('posted_on'):
            e['posted_on'] = {'any': e.get('posted_at') or e.get('at') or time.time()}; e['posted_at'] = e['posted_on']['any']; ch = True
        elif (e.get('views') or 0) > 0 and e.get('status') in ('goed', 'gepland', None):
            e['posted_on'] = {'any': e.get('plan_at') or e.get('at') or time.time()}; short_settle(e); ch = True
    if ch: lib_save(lib)
def reason_keys(reasons):
    ks = set()
    for r in reasons or []:
        r = r.lower()
        if 'clip' in r and any(w in r for w in ('knop', 'sneltoets', '!clip', 'button', 'hotkey', 'stream deck')): ks.add('marker')
        elif 'chat' in r or 'lul' in r: ks.add('chat')
        elif 'luid' in r or 'loud' in r: ks.add('audio')
        elif any(w in r for w in ('je zei', 'reageerde', 'you said', 'you reacted')): ks.add('say')
        elif 'gelachen' in r or 'laugh' in r: ks.add('laugh')
        elif 'scream' in r: ks.add('scream')
        elif 'a fight' in r or 'cheering' in r: ks.add('fight')
        elif 'won the' in r: ks.add('win')
        elif 'you died' in r: ks.add('fail')
        elif 'twitch-clip' in r or 'twitch clip' in r: ks.add('tclip')
        elif re.search(r'\b(ace|[345]k|clutch)\b', r): ks.add('game')
    return ks
def taste_load():
    try: return json.load(open(TASTE_F, encoding='utf-8'))
    except Exception: return {}
def taste_note(reasons, good, length=None, keys=None):
    """remember what kind of moments you keep and which you throw away"""
    try: taste_example(reasons, good, length)
    except Exception: pass
    try: taste2_note(keys or sorted(reason_keys(reasons)), good)   # the personal score model
    except Exception: pass
    t = taste_load()
    for k in reason_keys(reasons):
        v = t.setdefault(k, [0, 0]); v[0 if good else 1] += 1
    with LOCK: json.dump(t, open(TASTE_F, 'w', encoding='utf-8'))
def taste_mult(reasons, length=None):
    t = taste_load(); m = 1.0
    p = taste_prob(reasons, length)
    if p is not None: m = 0.55 + 0.9 * p   # 6.3: after 30 choices the model knows your taste better than fixed rules
    else:
        for k in reason_keys(reasons):
            kept, gone = t.get(k, [0, 0]); m *= max(0.6, min(1.45, 1 + 0.45 * (kept - gone) / (kept + gone + 4)))
    if blocked_kind(reasons): m *= 0.3
    # what really did well on TikTok/YouTube: views you filled in
    viewed = [e for e in lib_load().values() if (e.get('views') or 0) > 0]
    if len(viewed) >= 3:
        lv = lambda e: math.log10(e['views'] + 1); avg = sum(lv(e) for e in viewed) / len(viewed)
        for k in reason_keys(reasons):
            grp = [lv(e) for e in viewed if k in reason_keys(e.get('reasons'))]
            if len(grp) >= 2: m *= max(0.7, min(1.4, 1 + 0.3 * (sum(grp) / len(grp) - avg)))
    return m

# ---------------------------------------------------------------- 6.3: a real taste model, learning from your edits, search, insights
EX_F = os.path.join(DATA, 'voorbeelden.json'); EDITS_F = os.path.join(DATA, 'aanpassingen.json'); QW_F = os.path.join(DATA, 'qgewichten.json')
TKEYS = ['marker', 'chat', 'audio', 'say', 'laugh', 'tclip', 'game', 'story']
def jload(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
def jsave(p, v):
    with LOCK:
        tmp = p + '.tmp'; json.dump(v, open(tmp, 'w', encoding='utf-8')); os.replace(tmp, p)
def taste_vec(reasons, length=None):
    ks = reason_keys(reasons) | ({'story'} if any('opzet' in (r or '').lower() or 'setup and payoff' in (r or '').lower() for r in (reasons or [])) else set())
    return [1.0] + [1.0 if k in ks else 0.0 for k in TKEYS] + [min(2.0, (length or 30) / 30.0)]
def taste_example(reasons, good, length=None):
    ex = jload(EX_F, []); ex.append({'x': taste_vec(reasons, length), 'y': 1 if good else 0, 'at': time.time()}); jsave(EX_F, ex[-600:]); MODEL['at'] = 0
MODEL = {'at': 0, 'w': None, 'n': 0}
def taste_model():
    """logistic regression on your keep/throw-away choices: learns what YOU find a good clip"""
    if time.time() - MODEL['at'] < 120: return MODEL
    import numpy as np
    ex = jload(EX_F, []); MODEL.update(at=time.time(), n=len(ex))
    if len(ex) < 30 or len({e['y'] for e in ex}) < 2: MODEL['w'] = None; return MODEL
    X = np.array([e['x'] for e in ex]); y = np.array([e['y'] for e in ex], float)
    age = np.array([(time.time() - e['at']) / 86400 for e in ex]); sw = np.exp(-age / 60)   # recent choices count more
    w = np.zeros(X.shape[1])
    for _ in range(400):
        p = 1 / (1 + np.exp(-X @ w)); w -= 0.3 * (X.T @ ((p - y) * sw) / sw.sum() + 0.01 * w)
    MODEL['w'] = w.tolist(); return MODEL
def taste_prob(reasons, length=None):
    m = taste_model()
    if not m['w']: return None
    z = sum(a * b for a, b in zip(m['w'], taste_vec(reasons, length))); return 1 / (1 + math.exp(-z))
def blocked_kind(reasons):
    ks = reason_keys(reasons)
    return any(set(b) and set(b) <= ks for b in (SET.get('blocked_kinds') or []))

STORY = re.compile(r"\b(watch this|watch me|let me cook|let him cook|i got this|trust me|clip this|here we go|1v[2-5]|one v (two|three|four|five)|easy|i'?m (him|cracked))\b", re.I)
def story_bonus(ALL, cands, sess):
    """'watch this' followed by a kill within 15 seconds: a setup with a payoff, the best kind of clip"""
    if not ALL: return
    setups = [w[0] for w in ALL if STORY.search(w[2])]
    for c in cands:
        g = c.get('game'); peak = g['t'] if g else c['t']
        if any(0 < peak - s_ <= 15 for s_ in setups):
            c['score'] = round(c['score'] * 1.3 + 2, 1); c['reasons'].append('setup and payoff ("watch this" and then it lands)')

def note_edit(job):
    """you changed an automatic short: remember what, to suggest a better default later"""
    lib = lib_load(); old = lib.get(os.path.basename(job.get('replace') or '')) or {}
    if not old.get('auto'): return
    oj = old.get('job') or {}; d = jload(EDITS_F, {})
    def cnt(k, changed):
        v = d.setdefault(k, [0, 0]); v[0 if changed else 1] += 1
    ofx, nfx = oj.get('fx') or {}, job.get('fx') or {}
    if ofx.get('teaser') is not None: cnt('teaser_off', not nfx.get('teaser'))
    if ofx.get('replay') is not None: cnt('replay_off', not nfx.get('replay'))
    cnt('layout:' + str(job.get('layout')), (job.get('layout') or '') != (oj.get('layout') or SET.get('layout')))
    if job.get('cap_y') is not None and oj.get('cap_y') is None: cnt('caps_moved', True)
    else: cnt('caps_moved', False)
    cnt('music_added', bool(job.get('music')) and not oj.get('music'))
    jsave(EDITS_F, d)
# ---------------------------------------------------------------- 7.0: learning your look per game (plan F3.7)
LOOK_F = os.path.join(DATA, 'look_per_game.json')
LOOK_KEYS = ('layout', 'style', 'cap_scale', 'cap_anim', 'cap_y', 'jumpcut', 'sfx', 'progress', 'endcard', 'zoom', 'loop')
def learn_look(job):
    """every short you make yourself: remember the look per game. the editor starts with your last choices,
    and what you pick 10 times in a row the automatic shorts use too ("learned from you")"""
    if job.get('auto') or job.get('preview') or job.get('test') or job.get('live') or job.get('remake_of') or not job.get('sid'): return
    try: g = game_for(job['sid'], job.get('start'))
    except Exception: g = SET.get('default_game') or 'valorant'
    d = jload(LOOK_F, {}); gd = d.setdefault(g, {})
    for k in LOOK_KEYS:
        if k not in job: continue
        v = job[k]
        if isinstance(v, float): v = round(v, 2)
        h = gd.setdefault(k, []); h.append(v); del h[:-20]
    jsave(LOOK_F, d)
def learned_look(g):
    gd = jload(LOOK_F, {}).get(g) or {}
    last = {k: h[-1] for k, h in gd.items() if h}
    auto = {}
    for k, h in gd.items():
        if k in ('cap_y',): continue          # a height is only for the editor, not for every automatic short
        tail = h[-10:]
        if len(tail) >= 10 and all(x == tail[0] for x in tail): auto[k] = tail[0]
    return {'last': last, 'auto': auto}

EDIT_TIPS = {'teaser_off': ('You often remove the teaser. Shall I turn it off by default?', {'fx_teaser': False}),
             'replay_off': ('You often remove the replay. Shall I turn it off by default?', {'fx_replay': False}),
             'caps_moved': ('You often move the captions. Want to change the default height in the editor (Text > Height) and save it as a style?', None),
             'music_added': ('You often add music to your shorts. Pick a fixed track under Audio and save it as a style.', None)}
def edit_suggestions():
    d = jload(EDITS_F, {}); out = []; done = set(SET.get('tips_done') or [])
    for k, (yes, no) in d.items():
        n = yes + no
        if k in EDIT_TIPS and k not in done and n >= 5 and yes / n >= 0.7: out.append({'k': k, 'msg': EDIT_TIPS[k][0], 'can': EDIT_TIPS[k][1] is not None})
        if k.startswith('layout:') and k not in done and n >= 5 and yes / n >= 0.7 and k[7:] != SET.get('layout'):
            out.append({'k': k, 'msg': f'You often pick a different layout. Shall I make "{ {"split": "Cam + game", "frame": "Whole frame", "gameonly": "Game only", "landscape": "Landscape"}.get(k[7:], k[7:]) }" the default?', 'can': True})
    return out

def qweights(): return jload(QW_F, {})
def note_fix(k, used):
    d = qweights(); v = d.setdefault(k, [0, 0]); v[0 if used else 1] += 1; jsave(QW_F, d)
def qweight(k):
    """problems you never fix count less (you clearly don't mind them)"""
    used, ignored = qweights().get(k, [0, 0]); n = used + ignored
    return 1.0 if n < 8 else max(0.35, min(1.0, 0.35 + 0.65 * used / n + 0.2))

# ---- search in everything you ever said
def search_said(q, limit=60):
    q = q.strip().lower()
    if len(q) < 2: return []
    terms = q.split(); out = []
    for s in list_sess():
        if s.get('kind') == 'live': continue
        ws = load_transcript(s['id'])
        if not ws: continue
        low = [w[2].lower().strip('.,!?') for w in ws]
        for i in range(len(ws) - len(terms) + 1):
            if all(low[i + k].startswith(terms[k]) for k in range(len(terms))):
                t = ws[i][0]; ctx = ' '.join(w[2] for w in ws[max(0, i - 6):i + len(terms) + 8])
                out.append({'sid': s['id'], 'title': s.get('title'), 't': t, 'text': ctx, 'at': s.get('start')})
                if len(out) >= limit: return out
    return out

# ---- insights from the views you fill in
def insights():
    lib = {k: v for k, v in lib_load().items() if not v.get('test') and not v.get('deleted_at')}
    now = time.time(); weeks = []
    for i in range(7, -1, -1):
        a, b = now - (i + 1) * 7 * 86400, now - i * 7 * 86400
        es = [e for e in lib.values() if e.get('status') == 'gepost' and a <= (e.get('posted_at') or e.get('at') or 0) < b]
        made = [e for e in lib.values() if a <= (e.get('at') or 0) < b]
        weeks.append({'n': len(es), 'made': len(made), 'views': sum(e.get('views') or 0 for e in es), 'label': time.strftime('%d-%m', time.localtime(b))})
    viewed = [dict(e, file=k) for k, e in lib.items() if (e.get('views') or 0) > 0]
    def grp(name, fn):
        g = {}
        for e in viewed:
            k = fn(e)
            if k is None: continue
            g.setdefault(k, []).append(e['views'])
        rows = [{'k': k, 'n': len(v), 'avg': round(sum(v) / len(v))} for k, v in g.items()]
        return {'name': name, 'rows': sorted(rows, key=lambda r: -r['avg']), 'enough': sum(1 for r in rows if r['n'] >= 3) >= 2}
    LN = {'split': 'Cam + game', 'frame': 'Whole frame', 'gameonly': 'Game only', 'landscape': 'Landscape'}
    kind = lambda e: next((n for k, n in (('game', 'Multikill or clutch'), ('laugh', 'Funny'), ('chat', 'Chat went off'), ('marker', 'Clip button'), ('say', 'Your reaction')) if k in reason_keys(e.get('reasons'))), 'Other')
    groups = [grp('Layout', lambda e: LN.get(e.get('layout'), e.get('layout'))),
              grp('Kind of moment', kind),
              grp('Teaser at the start', lambda e: 'With teaser' if (e.get('fx') or {}).get('teaser') else 'Without teaser'),
              grp('Length', lambda e: '< 20 sec' if (e.get('dur') or 0) < 20 else '20-35 sec' if (e.get('dur') or 0) <= 35 else '> 35 sec'),
              grp('Post-ready score', lambda e: None if not e.get('q') else ('85 or higher' if e['q']['score'] >= 85 else '70-84' if e['q']['score'] >= 70 else 'under 70'))]
    DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    when = grp('Posting day', lambda e: DAYS[time.localtime(e.get('posted_at') or e.get('plan_at')).tm_wday] if (e.get('posted_at') or e.get('plan_at')) else None)
    hours = grp('Posting hour', lambda e: f"{time.localtime(e.get('posted_at') or e.get('plan_at')).tm_hour:02d}:00" if (e.get('posted_at') or e.get('plan_at')) else None)
    best = sorted(viewed, key=lambda e: -e['views'])[:5]
    todo = [dict(file=k, title=e.get('title'), at=e.get('posted_at') or e.get('at')) for k, e in lib.items() if e.get('status') == 'gepost' and not e.get('views') and now - (e.get('posted_at') or e.get('at') or now) > 2 * 86400]
    this_w = weeks[-1]; prev = weeks[:-1]; avg_n = sum(w['n'] for w in prev) / max(1, len(prev)); avg_v = sum(w['views'] for w in prev) / max(1, len(prev))
    return {'weeks': weeks, 'groups': groups + [when, hours], 'best': [{'file': e['file'], 'title': e.get('title'), 'views': e['views']} for e in best],
            'n_viewed': len(viewed), 'todo': todo[:10], 'vs': {'n': this_w['n'], 'avg_n': round(avg_n, 1), 'views': this_w['views'], 'avg_v': round(avg_v)},
            'goal': {'target': int(SET.get('week_goal') or 0), 'done': this_w['n'], 'made': this_w['made']},
            'pipeline': {k: sum(1 for e in lib.values() if e.get('status', 'goed') == k and not e.get('archived')) for k in ('nieuw', 'goed', 'gepland', 'gepost')}, 'model': {'n': taste_model()['n'], 'on': bool(taste_model()['w'])}}

def best_post_hour():
    g = {}
    for e in lib_load().values():
        if (e.get('views') or 0) > 0 and (e.get('posted_at') or e.get('plan_at')):
            h = time.localtime(e.get('posted_at') or e.get('plan_at')).tm_hour; g.setdefault(h, []).append(e['views'])
    rows = [(sum(v) / len(v), h) for h, v in g.items() if len(v) >= 2]
    return max(rows)[1] if len(rows) >= 2 else None

# ---- trash for shorts: 7 days to change your mind
TRASH = os.path.join(DATA, 'prullenbak'); os.makedirs(TRASH, exist_ok=True)
def trash_short(file):
    src = os.path.join(OUT, file)
    if os.path.exists(src): shutil.move(src, os.path.join(TRASH, file))
    lib = lib_load(); e = lib.get(file)
    if e: e['deleted_at'] = time.time(); lib_save(lib)
def restore_short(file):
    p = os.path.join(TRASH, file)
    if os.path.exists(p): shutil.move(p, os.path.join(OUT, file))
    lib = lib_load(); e = lib.get(file)
    if e: e.pop('deleted_at', None); lib_save(lib)
def trash_list():
    lib = lib_load()
    return [{'file': f, 'title': (lib.get(f) or {}).get('title') or f, 'deleted_at': (lib.get(f) or {}).get('deleted_at') or os.path.getmtime(os.path.join(TRASH, f))} for f in sorted(os.listdir(TRASH)) if f.endswith('.mp4')]
def trash_loop():
    while True:
        try:
            lib = lib_load(); ch = False
            for f in os.listdir(TRASH):
                p = os.path.join(TRASH, f); e = lib.get(f) or {}
                if time.time() - (e.get('deleted_at') or os.path.getmtime(p)) > 7 * 86400:
                    os.remove(p); lib.pop(f, None); ch = True
            if ch: lib_save(lib)
            # views reminder: posted two days ago, no views yet
            due = [k for k, e in lib.items() if e.get('status') == 'gepost' and not e.get('views') and not e.get('views_asked') and time.time() - (e.get('posted_at') or time.time()) > 2 * 86400]
            if due:
                notify('How many views?', f'{len(due)} short{"" if len(due) == 1 else "s"} from a few days ago. Fill in the views, then I learn what works.', 'eyes', 'views')
                for k in due: lib[k]['views_asked'] = True
                lib_save(lib)
            # weekly report on Sunday evening
            lt = time.localtime()
            if lt.tm_wday == 6 and lt.tm_hour == 19 and SET.get('week_report', True) and time.time() - (SET.get('report_sent') or 0) > 5 * 86400:
                ins = insights(); b = (ins['best'] or [None])[0]
                tip = next((f"{g['name']}: {g['rows'][0]['k']} does best" for g in ins['groups'] if g['enough'] and g['rows']), 'fill in views, then I can see what works')
                notify('Your week in shorts', f"{ins['vs']['n']} shorts this week" + (f", best: {b['title']} ({b['views']} views)" if b else '') + f". Tip: {tip}.", 'bar_chart')
                SET['report_sent'] = time.time(); save_settings(SET)
        except Exception: traceback.print_exc()
        time.sleep(1800)

# ---------------------------------------------------------------- what was wrong with a clip: you tell, I learn (and you can send it to be tuned)
FEEDBACK_F = os.path.join(DATA, 'feedback.jsonl')
FB_REASONS = {'boring': 'boring, nothing happens', 'early': 'starts too early', 'late': 'starts too late', 'cut': 'ends too soon, the reaction is cut off',
              'long': 'goes on too long at the end', 'wrong': 'wrong moment', 'title': 'bad title', 'captions': 'captions wrong', 'confusing': 'hard to follow without context', 'good': 'good clip'}
def _lib_items():
    L = lib_load()
    return [dict(v, file=v.get('file') or k) for k, v in L.items()] if isinstance(L, dict) else list(L)
def feedback_add(b):
    """{sid, mid or file, reasons: [keys], note} -> remembered, and the timing learns from it"""
    rs = [r for r in (b.get('reasons') or []) if r in FB_REASONS]
    e = {'at': time.time(), 'sid': b.get('sid'), 'mid': b.get('mid'), 'file': b.get('file'), 'reasons': rs, 'note': (b.get('note') or '')[:300], 'version': VERSION}
    m = None
    try:
        s = load_sess(b['sid']) if b.get('sid') else None
        if s and b.get('mid'): m = next((x for x in s.get('moments', []) if x.get('id') == b['mid']), None)
        if not m and b.get('file'):
            sh = next((x for x in _lib_items() if x.get('file') == b['file']), None)
            if sh: e['sid'] = sh.get('sid'); e['mid'] = sh.get('mid'); s = load_sess(sh['sid']) if sh.get('sid') else None; m = next((x for x in (s or {}).get('moments', []) if x.get('id') == sh.get('mid')), None)
        if m: e['moment'] = {k: m.get(k) for k in ('t', 'start', 'end', 'score', 'reasons', 'title', 'vision', 'game', 'feat', 'brief', 'ai')}
    except Exception: pass
    with open(FEEDBACK_F, 'a', encoding='utf-8') as fh: fh.write(json.dumps(e) + '\n')
    # learn: the start and end of new clips move a little with every "too early" / "too soon"
    lr = dict(SET.get('learn_timing') or {'lead': 0.0, 'tail': 0.0})
    if 'early' in rs: lr['lead'] = round(max(-6.0, lr['lead'] - 1.0), 1)
    if 'late' in rs: lr['lead'] = round(min(6.0, lr['lead'] + 1.0), 1)
    if 'cut' in rs: lr['tail'] = round(min(6.0, lr['tail'] + 1.0), 1)
    if 'long' in rs: lr['tail'] = round(max(-4.0, lr['tail'] - 1.0), 1)
    SET['learn_timing'] = lr; save_settings(SET)
    if m and any(r in rs for r in ('boring', 'wrong')):
        for _ in range(2): taste_note(m.get('reasons') or [], False, keys=m.get('feat'))   # a reason you gave counts double
    if m and 'good' in rs:
        for _ in range(2): taste_note(m.get('reasons') or [], True, keys=m.get('feat'))
    if 'confusing' in rs: SET['ctx_cards'] = min(3, int(SET.get('ctx_cards') or 1) + 1); save_settings(SET)   # more context cards from now on
    return {'ok': True, 'learn': lr}

def analysis_report():
    """a zip with what the clipper found and what you thought of it: no videos, no passwords or keys. for tuning the AI on your streams"""
    import zipfile
    os.makedirs(REPORT_DIR, exist_ok=True); out = os.path.join(REPORT_DIR, f'JelE_analysis_report_{time.strftime("%Y%m%d_%H%M")}.zip')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        if os.path.exists(FEEDBACK_F): z.write(FEEDBACK_F, 'feedback.jsonl')
        safe = {k: v for k, v in SET.items() if not re.search(r'key|secret|token|password|pass|ntfy|phone_key|jwt', k, re.I)}
        z.writestr('settings.json', json.dumps(safe, indent=1, default=str))
        for s_ in sorted(list_sess(), key=lambda x: -(x.get('start') or 0))[:6]:
            s = load_sess(s_['id'])
            keep = {k: s.get(k) for k in ('id', 'title', 'duration', 'game', 'mic', 'sounds', 'game_events', 'talk', 'status', 'rec_tracks')}
            keep['moments'] = [{k: m.get(k) for k in ('id', 't', 'start', 'end', 'score', 'reasons', 'title', 'hooks', 'text', 'vision', 'manual')} for m in s.get('moments', [])]
            keep['markers'] = s.get('markers', [])
            z.writestr(f"sessions/{s['id']}.json", json.dumps(keep, indent=1, default=str))
        shorts = [{k: x.get(k) for k in ('file', 'title', 'sid', 'mid', 'status', 'views', 'auto', 'reasons', 'dur', 'q', 'learned', 'posted_on')} for x in _lib_items()]
        z.writestr('shorts.json', json.dumps(shorts, indent=1, default=str))
        lg = os.path.join(DATA, 'clipper.log')
        if os.path.exists(lg):
            z.writestr('clipper_log_tail.txt', ''.join(open(lg, encoding='utf-8', errors='replace').readlines()[-1500:]))
    return out
