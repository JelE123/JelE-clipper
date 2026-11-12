# JelE Clipper: what happens on screen (plan F2.4)
# reads the text in the picture (OCR, rapidocr: works offline, comes with the Full setup) and looks at the colours.
# only around the moments that were found, one picture every 2 seconds, so it stays light.
# per picture it says: playing, menu, dead, spectating, buy phase, round won or lost, match won or lost.

VISION = {'ocr': None, 'tried': False, 'why': ''}

# words on screen per game, as the game shows them (in capitals, checked without spaces)
SCREEN_WORDS = {
    'valorant': {'menu': ['AGENTSELECT', 'LOCKIN', 'COLLECTION', 'CAREER', 'BATTLEPASS', 'PLAY', 'QUEUE', 'MATCHFOUND', 'ACCEPT'],
                 'dead': ['KILLEDBY', 'YOUWEREKILLED'], 'spectate': ['SPECTATING'], 'buy': ['BUYPHASE', 'SHOP'],
                 'round_win': ['ROUNDWIN', 'CLUTCH', 'FLAWLESS', 'THRIFTY', 'ACE', 'TEAMACE'], 'round_loss': ['ROUNDLOSS', 'ROUNDLOST'],
                 'win': ['VICTORY'], 'loss': ['DEFEAT'],
                 'end': ['PLAYAGAIN', 'RETURNTOLOBBY', 'MATCHHISTORY', 'COMBATSCORE', 'RANKRATING', 'MATCHMVP', 'TEAMMVP', 'SCOREBOARD', 'ACS', 'ECONRATING', 'FIRSTBLOODS', 'PERFORMANCE', 'TIMELINE', 'SUMMARY']},
    'cs2': {'menu': ['PLAY', 'INVENTORY', 'MATCHMAKING', 'ACCEPT', 'YOURMATCHISREADY'],
            'dead': ['KILLEDBY', 'YOUWEREKILLED'], 'spectate': ['SPECTATING'], 'buy': ['BUYMENU', 'BUYTIME'],
            'round_win': ['COUNTERTERRORISTSWIN', 'TERRORISTSWIN', 'MVP'], 'round_loss': [], 'win': ['VICTORY', 'YOUWON'], 'loss': ['DEFEAT', 'YOULOST'],
            'end': ['MATCHSUMMARY', 'PLAYAGAIN', 'MAINMENU', 'SCOREBOARD', 'XPEARNED', 'COMPETITIVERANK']},
    'fortnite': {'menu': ['PLAY', 'LOCKER', 'ITEMSHOP', 'BATTLEPASS', 'READYUP', 'MATCHMAKING'],
                 'dead': ['ELIMINATEDBY', 'YOUWEREELIMINATED', 'YOUPLACED'], 'spectate': ['SPECTATING'], 'buy': [],
                 'round_win': [], 'round_loss': [], 'win': ['VICTORYROYALE', '#1'], 'loss': [],
                 'end': ['RETURNTOLOBBY', 'MATCHSTATS', 'XPEARNED', 'PLAYAGAIN', 'SPECTATEPLAYERS']},
}
SCREEN_WORDS['other'] = {'menu': ['MAINMENU', 'SETTINGS', 'PRESSANYKEY'], 'dead': ['YOUDIED', 'GAMEOVER', 'WASTED'], 'spectate': ['SPECTATING'], 'buy': [],
                         'round_win': [], 'round_loss': [], 'win': ['VICTORY', 'YOUWIN'], 'loss': ['DEFEAT', 'YOULOSE'],
                         'end': ['PLAYAGAIN', 'RETURNTOLOBBY', 'MAINMENU', 'CONTINUE', 'RESULTS', 'SCOREBOARD']}

def vision_ok():
    """the text reader is there (Full setup) and can be used"""
    if VISION['tried']: return VISION['ocr'] is not None
    VISION['tried'] = True
    if SET.get('vision', True) is False: VISION['why'] = 'turned off in Settings'; return False
    try:
        from rapidocr_onnxruntime import RapidOCR
        VISION['ocr'] = RapidOCR(); return True
    except Exception as e:
        VISION['why'] = 'the text reader is not installed (Full setup)'; return False

def vision_frames(path, a, b, every=2.0, w=960):
    """pictures between a and b, one every `every` seconds, small (960 wide): [(t, rgb array)]"""
    import numpy as np
    h = w * 9 // 16
    r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-ss', f'{max(0, a):.2f}', '-t', f'{max(0.5, b - a):.2f}', '-i', path, '-map', '0:v:0',
                        '-vf', f'fps=1/{every},scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, creationflags=NOWIN)
    n = len(r.stdout) // (w * h * 3)
    arr = np.frombuffer(r.stdout[:n * w * h * 3], dtype=np.uint8).reshape(n, h, w, 3) if n else []
    return [(round(a + i * every, 2), arr[i]) for i in range(n)]

def _norm(t): return re.sub(r'[^A-Z0-9#]', '', (t or '').upper())

def screen_state(img, game='other'):
    """one picture -> {'state': playing|menu|dead|spectate|buy, 'events': [...], 'text': [...], 'gray': 0..1}"""
    import numpy as np
    W = SCREEN_WORDS.get(game) or SCREEN_WORDS['other']
    # colour: dead and spectating screens are often grey; menus are often still and flat
    hsv_s = (img.max(2).astype(np.int16) - img.min(2).astype(np.int16)).mean() / 255.0
    gray = float(max(0.0, min(1.0, 1 - hsv_s / 0.25)))
    texts = []
    if vision_ok():
        try:
            res, _ = VISION['ocr'](img)
            texts = [(_norm(x[1]), float(x[2])) for x in (res or []) if x and len(x) > 2 and float(x[2]) > 0.6]
        except Exception: texts = []
    words = [t for t, _ in texts]
    joined = ''.join(words)
    def has(k): return any(x and (x in words or (len(x) > 4 and x in joined)) for x in W.get(k, []))   # short words (ACE, MVP) only as a whole word
    ev = [k for k in ('round_win', 'round_loss', 'win', 'loss') if has(k)]
    st = 'playing'
    endn = sum(1 for x in W.get('end', []) if x in words or (len(x) > 4 and x in joined))
    if endn >= 2 or (endn >= 1 and ev and any(e in ev for e in ('win', 'loss'))): st = 'end'   # the end screen after a match: scoreboard, play again
    elif has('spectate'): st = 'spectate'
    elif has('dead'): st = 'dead'
    elif has('buy'): st = 'buy'
    elif sum(1 for x in W['menu'] if x in words) >= 2 or (has('menu') and gray > 0.6 and len(words) > 8): st = 'menu'
    return {'state': st, 'events': ev, 'gray': round(gray, 2), 'n_text': len(words)}

def vision_scan(path, a, b, game='other', every=2.0):
    """what happens on screen between a and b: a list of (t, state)"""
    out = []
    for t, img in vision_frames(path, a, b, every):
        try: s_ = screen_state(img, game)
        except Exception: continue
        out.append({'t': t, **s_})
    return out

def vision_judge(scan, st, en, peak):
    """from the pictures to advice for one moment: {'menu': share, 'dead_at': t, 'spectate_from': t, 'events': [...], 'reasons': [...]}"""
    if not scan: return {}
    inside = [x for x in scan if st <= x['t'] <= en]
    if not inside: return {}
    n = len(inside)
    menu = sum(1 for x in inside if x['state'] == 'menu') / n
    endsc = sum(1 for x in inside if x['state'] == 'end') / n
    buy = sum(1 for x in inside if x['state'] == 'buy') / n
    dead = next((x['t'] for x in inside if x['state'] == 'dead'), None)
    spec = next((x['t'] for x in inside if x['state'] == 'spectate' and x['t'] > peak), None)
    evs = []
    for x in inside:
        for e in x['events']:
            if e not in evs: evs.append(e)
    reasons = []
    names = {'round_win': 'you won the round', 'round_loss': 'you lost the round', 'win': 'you won the match', 'loss': 'you lost the match'}
    for e in evs: reasons.append(names[e])
    if dead is not None and dead <= peak + 3: reasons.append('you died (a fail can be gold)')
    if endsc > 0.4: reasons.append('end screen after the match')
    return {'menu': round(menu, 2), 'end': round(endsc, 2), 'buy': round(buy, 2), 'dead_at': dead, 'spectate_from': spec, 'events': evs, 'reasons': reasons}

# ---------------------------------------------------------------- plan F4.3: the cam follows your face
def face_track(path, start, dur, rect, every=0.5):
    """where your face is in the cam box over time: [(t, x, y, size)] in picture pixels, or [] when no face / no OpenCV"""
    try:
        import cv2, numpy as np
    except Exception: return []
    cx, cy, cw, ch = rect
    if cw < 40 or ch < 40: return []
    sc = min(1.0, 320.0 / cw); w_, h_ = max(2, int(cw * sc) // 2 * 2), max(2, int(ch * sc) // 2 * 2)
    r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-ss', f'{max(0, start):.2f}', '-t', f'{dur:.2f}', '-i', path, '-map', '0:v:0',
                        '-vf', f'fps=1/{every},crop={cw}:{ch}:{cx}:{cy},scale={w_}:{h_}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True, creationflags=NOWIN)
    n = len(r.stdout) // (w_ * h_)
    if not n: return []
    fr = np.frombuffer(r.stdout[:n * w_ * h_], dtype=np.uint8).reshape(n, h_, w_)
    det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    out = []
    for i in range(n):
        fs = det.detectMultiScale(cv2.equalizeHist(fr[i]), scaleFactor=1.15, minNeighbors=5, minSize=(int(w_ * 0.07), int(w_ * 0.07)))
        if len(fs):
            x, y, w, h = max(fs, key=lambda b: b[2] * b[3])
            out.append((round(i * every, 2), cx + (x + w / 2) / sc, cy + (y + h / 2) / sc, w / sc))
    return out

def face_crop(track, rect, dur, zoom=0.8):
    """a crop that keeps your face in the middle of the cam box, smooth and never outside it.
    -> (w, h, x_expr, y_expr) for ffmpeg, or None when there is no face often enough"""
    cx, cy, cw, ch = rect
    n_need = max(3, int(dur / 0.5 * 0.4))
    if len(track) < n_need: return None
    import numpy as np
    w2, h2 = int(cw * zoom) // 2 * 2, int(ch * zoom) // 2 * 2
    ts = np.array([t for t, *_ in track]); xs = np.array([x for _, x, _, _ in track]); ys = np.array([y for _, _, y, _ in track])
    k = 5   # smooth: no shaking with every small movement
    if len(xs) >= k:
        pad = k // 2
        xs = np.convolve(np.pad(xs, pad, mode='edge'), np.ones(k) / k, mode='valid'); ys = np.convolve(np.pad(ys, pad, mode='edge'), np.ones(k) / k, mode='valid')
    X = np.clip(xs - w2 / 2, cx, cx + cw - w2); Y = np.clip(ys - h2 * 0.45, cy, cy + ch - h2)   # face a bit above the middle
    if X.std() < cw * 0.02 and Y.std() < ch * 0.02:   # you sit still: one fixed crop around your face
        return (w2, h2, str(int(np.median(X))), str(int(np.median(Y))))
    # keyframes every 1.5 s, straight lines in between
    keys = [0]
    for i in range(1, len(ts)):
        if ts[i] - ts[keys[-1]] >= 1.5: keys.append(i)
    if keys[-1] != len(ts) - 1: keys.append(len(ts) - 1)
    keys = keys[:40]
    def expr(V):
        e = f'{int(V[keys[-1]])}'
        for a, b in reversed(list(zip(keys, keys[1:]))):
            ta, tb, va, vb = ts[a], ts[b], V[a], V[b]
            e = f"if(lt(t,{tb:.2f}),{va:.0f}+({vb - va:.0f})*max(0,(t-{ta:.2f}))/{max(0.01, tb - ta):.2f},{e})"
        return e
    return (w2, h2, expr(X), expr(Y))

# ---------------------------------------------------------------- install the picture understanding afterwards (Light setup, or an update)
VIS_INST = {'busy': False, 'error': '', 'step': ''}
def vision_status():
    try: import cv2; cv = True
    except Exception: cv = False
    try: import rapidocr_onnxruntime; oc = True
    except Exception: oc = False
    return {'ocr': oc, 'face': cv, 'busy': VIS_INST['busy'], 'error': VIS_INST['error'], 'step': VIS_INST['step']}
def vision_install():
    if VIS_INST['busy']: return
    VIS_INST.update(busy=True, error='', step='Installing (about 100 MB)')
    try:
        py = sys.executable if not sys.executable.lower().endswith('pythonw.exe') else sys.executable[:-5] + '.exe'
        r = subprocess.run([py, '-m', 'pip', 'install', '--no-warn-script-location', '--disable-pip-version-check', 'rapidocr-onnxruntime', 'opencv-python-headless<5'],
                           capture_output=True, text=True, errors='replace', creationflags=NOWIN)
        if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout or '')[-200:])
        VISION.update(tried=False, ocr=None); VIS_INST['step'] = 'Ready'; log('Picture understanding is installed')
    except Exception as e: VIS_INST['error'] = str(e)[:200]; log('Picture understanding could not be installed:', e)
    finally: VIS_INST['busy'] = False

def vision_auto_loop():
    """after an update: install the picture understanding by itself, once, when the pc is quiet (not with the Light setup,
    never during your stream). you can still turn it off in Settings"""
    time.sleep(90)
    try:
        ed = json.load(open(os.path.join(DATA, 'install.json'), encoding='utf-8')).get('edition', 'full')
    except Exception: ed = 'full'
    if ed == 'light' or SET.get('vision', True) is False or SET.get('vision_auto_done'): return
    for _ in range(240):   # wait (up to 4 hours) for a quiet moment
        st = vision_status()
        if st['ocr'] and st['face']: break
        if not (CUR.get('id') or STATE.get('live') or STATE.jobs()):
            log('Installing picture understanding by itself (about 100 MB)'); vision_install()
            break
        time.sleep(60)
    SET['vision_auto_done'] = True; save_settings(SET)
