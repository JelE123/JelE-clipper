# JelE Clipper part: live clips, export, postklaar, brands, extras. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- 6.2: clips during the stream (OBS replay buffer), scenes, hype, stream health
LIVE = {'last': 0, 'pending': [], 'clips': [], 'chat': collections.deque(maxlen=6000), 'warned': False, 'drop': None, 'tot0': None, 'skip0': None}
BLOCK_SCENES = r'start|soon|brb|be right back|pauze|pause|intermission|einde|ending|\bend\b|offline|break'
def scene_blocked():
    sc = STATE.get('scene') or ''
    try: return bool(sc and re.search(SET.get('block_scenes') or BLOCK_SCENES, sc, re.I))
    except re.error: return False

def wait_stable(path, still=1.2, limit=40):
    """OBS needs a moment to finish writing the replay: wait until the file stops growing and can be opened"""
    last, since, t0 = -1, time.time(), time.time()
    while time.time() - t0 < limit:
        try:
            sz = os.path.getsize(path)
            if sz != last: last, since = sz, time.time()
            elif sz > 0 and time.time() - since >= still:
                with open(path, 'ab'): return True   # fails while OBS still holds the file (Windows)
        except OSError: pass
        time.sleep(0.25)
    return False

def live_clip(note='', length=None):
    """the Clip button during your stream: OBS saves the last minute, and a short is made right away"""
    if not SET.get('live_clip', True) or not obs.ok: return
    now = time.time()
    if now - LIVE['last'] < 45 and LIVE['clips']:   # same moment (you, a mod and !clip at once): one clip
        LIVE['clips'][-1]['sources'] = LIVE['clips'][-1].get('sources', 1) + 1
        log('Same moment as just now: merged with that clip'); return
    st = obs.req('GetReplayBufferStatus') or {}
    if not st.get('outputActive'):
        if not LIVE['warned']:
            log('Tip: turn on the replay buffer in OBS (Settings > Output > Replay Buffer), then I make clips during your stream'); LIVE['warned'] = True
        return
    LIVE['last'] = now; LIVE['pending'].append({'at': now, 'note': note, 'len': length})
    obs.req('SaveReplayBuffer')

def live_saved(path):
    info = LIVE['pending'].pop(0) if LIVE['pending'] else {'at': time.time(), 'note': '', 'len': None}
    if not path or not wait_stable(path):
        log('The OBS replay did not come in right:', path); return
    dur = probe_duration(path)
    if dur < 3: log('The OBS replay is too short'); return
    s = new_session(title='Live clip ' + time.strftime('%H:%M'), path=path); s.update(kind='live', status='klaar', duration=dur, parent=CUR['id']); save_sess(s)
    L = float(info.get('len') or SET.get('live_len', 25)); end = max(1.0, dur - 0.5); start = max(0.0, end - L)
    cid = uuid.uuid4().hex[:6]
    LIVE['clips'].append({'id': cid, 'sid': s['id'], 'note': info.get('note') or '', 'at': info['at'], 'sources': 1, 'file': None, 'status': 'maken'})
    LIVE['clips'] = LIVE['clips'][-30:]
    job = {'sid': s['id'], 'start': start, 'end': end, 'title': 'live_' + time.strftime('%H%M%S'), 'hook': (info.get('note') or '').upper()[:40],
           'captions': SET.get('captions', True), 'layout': SET.get('layout', 'split'), 'style': SET.get('cap_style', 'jele'), 'zoom': SET.get('auto_zoom', True), 'live': cid}
    JOBS.put_front(('render', job)); log(f'Live clip: making the short ({L:.0f} sec)')

def live_done(cid, path):
    c = next((x for x in LIVE['clips'] if x['id'] == cid), None)
    if not c: return
    c['status'] = 'klaar' if path else 'mislukt'; c['file'] = os.path.basename(path) if path else None
    if path:
        lib = lib_load(); e = lib.get(c['file'])
        if e: e.update(live=True, status='nieuw', sources=c.get('sources', 1)); lib_save(lib)
        obs.broadcast({'jele': 'live-short', 'file': c['file']})

def hype():
    """how busy chat is now compared to normal (1 = normal)"""
    now = time.time(); L = LIVE['chat']
    recent = sum(1 for t in L if now - t < 20)
    base_ = [t for t in L if 20 <= now - t < 600]
    span = min(580, max(60, now - (base_[0] if base_ else now))) if base_ else 0
    per20 = len(base_) / span * 20 if span else 0
    return {'now': recent * 3, 'ratio': round(recent / max(1.5, per20), 2) if (recent or per20) else 0}

def live_loop():
    """while live: dropped frames, every few seconds"""
    while True:
        time.sleep(5)
        if not (obs.ok and STATE.get('live')): LIVE['tot0'] = None; LIVE['drop'] = None; continue
        try:
            st = obs.req('GetStreamStatus') or {}
            tot, sk = st.get('outputTotalFrames') or 0, st.get('outputSkippedFrames') or 0
            if LIVE['tot0'] is None or tot < LIVE['tot0']: LIVE['tot0'], LIVE['skip0'] = tot, sk; continue
            dt, ds = tot - LIVE['tot0'], sk - LIVE['skip0']
            if dt >= 300:
                LIVE['drop'] = round(100.0 * ds / dt, 1); LIVE['tot0'], LIVE['skip0'] = tot, sk
        except Exception: pass

def stream_summary():
    t0 = STATE.get('stream_at') or 0
    clips = [c for c in LIVE['clips'] if c['at'] >= t0]
    s = load_sess(CUR['id']) if CUR['id'] else None
    return {'at': time.time(), 'clips': len(clips), 'ready': sum(1 for c in clips if c['status'] == 'klaar'),
            'markers': len([m for m in (s or {}).get('markers', []) if (s['start'] + m['t']) >= t0]) if s else None, 'mins': round((time.time() - t0) / 60) if t0 else None}

# ---------------------------------------------------------------- 6.2: export pack, subtitles file, seamless loop
SRT_DIR = os.path.join(DATA, 'srt')
PLATFORMS = {
    'tiktok': {'name': 'TikTok', 'max': 60, 'best': (15, 35), 'tags': '#fyp #valorant #gaming'},
    'shorts': {'name': 'YouTube Shorts', 'max': 60, 'best': (20, 45), 'tags': '#shorts #valorant'},
    'reels': {'name': 'Instagram Reels', 'max': 90, 'best': (15, 40), 'tags': '#reels #valorant #gamingclips'},
}
def srt_write(name, words):
    os.makedirs(SRT_DIR, exist_ok=True)
    def ts(t): t = max(0, t); return f'{int(t // 3600):02d}:{int(t // 60 % 60):02d}:{int(t % 60):02d},{int(t * 1000 % 1000):03d}'
    groups = caption_groups([w for w in words if w[2] != UNCLEAR]); out = []
    for i, g in enumerate(groups, 1): out.append(f"{i}\n{ts(g[0][0])} --> {ts(g[-1][1] + 0.3)}\n{' '.join(w[2] for w in g)}\n")
    open(os.path.join(SRT_DIR, os.path.splitext(name)[0] + '.srt'), 'w', encoding='utf-8').write('\n'.join(out))

def make_pack(file, platforms):
    """per platform: the video, the text to post (with that platform's hashtags), the cover and the subtitles, in one folder"""
    lib = lib_load(); e = lib.get(file) or {}; src = os.path.join(OUT, file)
    if not os.path.exists(src): raise FileNotFoundError(file)
    base = os.path.splitext(file)[0]; folder = os.path.join(OUT, 'pakketten', base); os.makedirs(folder, exist_ok=True)
    post = e.get('post') or {}
    try: cover = make_thumbnail(file=file, kind='short')
    except Exception: cover = None
    made = []
    for p in platforms:
        P = PLATFORMS.get(p)
        if not P: continue
        shutil.copy2(src, os.path.join(folder, f'{base}_{p}.mp4'))
        g_ = e.get('game') or (game_for(e['sid']) if e.get('sid') else cur_game())
        own = ((SET.get('tags_' + p) if g_ == 'valorant' else '') or (gprof(g_).get('platform_tags') or {}).get(p) or P['tags']).split()
        tags = ' '.join(dict.fromkeys((post.get('hashtags') or '').split() + own))
        txt = f"{post.get('title', '')}\n\n{post.get('description', '')}\n\n{tags}\n"
        if (e.get('dur') or 0) > P['max']: txt = f"NOTE: this short is {e.get('dur')} sec, {P['name']} recommends {P['max']} sec at most.\n\n" + txt
        open(os.path.join(folder, f'{base}_{p}_posttekst.txt'), 'w', encoding='utf-8').write(txt); made.append(p)
    if cover and os.path.exists(cover): shutil.copy2(cover, os.path.join(folder, base + '_cover' + os.path.splitext(cover)[1]))
    srt = os.path.join(SRT_DIR, base + '.srt')
    if os.path.exists(srt): shutil.copy2(srt, os.path.join(folder, base + '.srt'))
    return folder, made

def make_loop(path, d=0.4):
    """the end flows into the start, so the short loops without a visible jump"""
    dur = probe_duration(path)
    if dur < 4: return path
    tmp = path + '.loop.mp4'
    f = (f"[1:v]trim=0:{d},setpts=PTS-STARTPTS[hd];[0:v]trim={d}:{dur},setpts=PTS-STARTPTS[md];[md][hd]xfade=transition=fade:duration={d}:offset={dur - 2 * d:.3f}[v];"
         f"[1:a]atrim=0:{d},asetpts=PTS-STARTPTS[hda];[0:a]atrim={d},asetpts=PTS-STARTPTS[mda];[mda][hda]acrossfade=d={d}[a]")
    r = run(['-y', '-i', path, '-i', path, '-filter_complex', f, '-map', '[v]', '-map', '[a]'] + encoder_args() + ['-r', '60', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', tmp], capture_output=True, text=True, errors='replace')
    if r.returncode == 0 and os.path.exists(tmp): os.replace(tmp, path); log('Seamless loop made')
    else:
        log('Making the loop failed, the short stays as it was'); 
        try: os.remove(tmp)
        except OSError: pass
    return path

# ---------------------------------------------------------------- 6.2: Postklaar-score: the Clipper watches every short like a strict editor
def q_measure(path):
    r = subprocess.run([FF, '-hide_banner', '-nostats', '-i', path, '-vf', 'scale=270:-2,blackdetect=d=0.25:pix_th=0.10,freezedetect=n=0.002:d=1.3',
                        '-af', 'ebur128=peak=true,silencedetect=n=-45dB:d=0.5', '-f', 'null', '-'], capture_output=True, text=True, errors='replace', creationflags=NOWIN | (LOWPRIO if is_live() else 0))
    e = r.stderr; m = {'black': [], 'freeze': [], 'silence': [], 'I': None, 'TP': None}
    for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', e): m['black'].append((float(a), float(b)))
    fs = re.findall(r'freeze_start: ([\d.]+)', e); fe = re.findall(r'freeze_end: ([\d.]+)', e)
    for i, a in enumerate(fs): m['freeze'].append((float(a), float(fe[i]) if i < len(fe) else None))
    ss = re.findall(r'silence_start: ([\d.-]+)', e); se = re.findall(r'silence_end: ([\d.]+)', e)
    for i, a in enumerate(ss): m['silence'].append((max(0.0, float(a)), float(se[i]) if i < len(se) else None))
    mi = re.findall(r'I:\s+(-?[\d.]+) LUFS', e); mp = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', e)
    if mi: m['I'] = float(mi[-1])
    if mp: m['TP'] = max(float(x) for x in mp)
    return m

def cam_empty(sid, start, dur, job):
    """does the cam box really show your cam or mascot, and not a flat empty area?"""
    try:
        import numpy as np
        s = load_sess(sid); cam = s.get('cam') if (s.get('cam') and SET.get('cam_auto', True)) else SET.get('cam')
        x, y, w, h = [int(v) for v in cam]
        sds = []
        for k in (0.25, 0.5, 0.8):
            r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-ss', f'{start + dur * k:.2f}', '-i', s['path'], '-frames:v', '1', '-vf', f'scale=1920:1080,crop={w}:{h}:{x}:{y},scale=48:27,format=gray', '-f', 'rawvideo', '-'],
                               capture_output=True, creationflags=NOWIN)
            if len(r.stdout) >= 48 * 27: sds.append(float(np.frombuffer(r.stdout[:48 * 27], dtype=np.uint8).std()))
        return bool(sds) and max(sds) < 7
    except Exception: return False

def quality_check(path, job, ws=None, extra=None):
    """score 0-100 in three parts (beeld, geluid, montage), with what is off and how to fix it"""
    extra = extra or {}; issues = []
    dur = probe_duration(path); m = q_measure(path); layout = job.get('layout') or SET.get('layout', 'split')
    def add(area, pen, msg, fix=None, k=None):
        k = k or fix or msg[:20]; pen = max(1, round(pen * qweight(k)))
        issues.append({'area': area, 'pen': pen, 'msg': msg, 'fix': fix, 'k': k})
    # beeld
    for a, b in m['black'][:2]:
        if b - a >= 0.25 and a < dur - 0.6: add('beeld', 15, f'Black picture from {a:.1f} to {b:.1f} sec', 'cut_black', 'black')
    tz = (job.get('fx') or {}).get('replay') or {}
    for a, b in m['freeze'][:2]:
        if (b or dur) - a >= 1.3 and not (layout == 'landscape'): add('beeld', 10, f'Frozen picture around {a:.1f} sec', None, 'freeze')
    if layout == 'split' and not job.get('parts') and cam_empty(job['sid'], float(job['start']), float(job['end']) - float(job['start']), job):
        add('beeld', 20, 'The cam box looks empty: is it in the right place?', 'cam', 'cam')
    zs = len((job.get('fx') or {}).get('zooms') or [])
    if zs > max(4, dur / 6): add('beeld', 5, f'{zs} zooms is restless for {dur:.0f} sec', 'fewer_zooms', 'zooms')
    st_ = (job.get('fx') or {}).get('stickers') or []
    cy = job.get('cap_y')
    if cy is not None and any(abs(float(s_.get('y', .3)) - float(cy)) < 0.07 for s_ in st_): add('beeld', 6, 'A sticker covers the captions', 'caps_move', 'overlap')
    # geluid
    if m['I'] is not None:
        if m['I'] < -20: add('geluid', 12, f'Too quiet ({m["I"]:.0f} LUFS, normal is -14)', 'loud', 'quiet')
        elif m['I'] > -9: add('geluid', 8, f'Too loud ({m["I"]:.0f} LUFS)', 'loud', 'loud')
    if m['TP'] is not None and m['TP'] > -0.3: add('geluid', 6, 'The audio clips in some places (distortion)', 'loud', 'clip')
    if m['silence'] and m['silence'][0][0] < 0.05 and (m['silence'][0][1] or 0) > 0.6: add('geluid', 8, f'Silence at the start ({m["silence"][0][1]:.1f} sec)', 'trim_start', 'silence_start')
    if job.get('music') and float((job.get('music') or {}).get('vol', 0.25)) > 0.45: add('geluid', 8, 'The music is so loud your voice gets lost', 'music_down', 'music')
    # montage
    ws = ws or []
    first = [w for w in ws if w[0] < 2.0 and w[2] != UNCLEAR]
    if not (job.get('hook') or '').strip() and not first: add('montage', 12, 'Nothing happens in the first 2 seconds to hook viewers', 'hook', 'hook')
    if not job.get('jumpcut') and ws:
        gaps = [(ws[i][1], ws[i + 1][0]) for i in range(len(ws) - 1) if ws[i + 1][0] - ws[i][1] > 1.8]
        if gaps: add('montage', min(12, 4 * len(gaps)), f'{len(gaps)} boring part{"" if len(gaps) == 1 else "s"} without talking (longer than 1.8 sec)', 'silence', 'dead')
    fast = 0
    for g in caption_groups(ws):
        d_ = max(0.25, g[-1][1] - g[0][0] + 0.3)
        if sum(len(w[2]) for w in g) / d_ > 22: fast += 1
    if fast >= 3: add('montage', 5, f'{fast} captions go too fast to read', None, 'read')
    if extra.get('unsure_left'): add('montage', min(9, 3 * extra['unsure_left']), f'{extra["unsure_left"]} unsure word(s) not checked', 'unsure', 'unsure')
    P = PLATFORMS.get(SET.get('platform') or 'tiktok', PLATFORMS['tiktok'])
    if layout != 'landscape' and not job.get('parts'):
        if dur > P['max']: add('montage', 10, f'{dur:.0f} sec is long for {P["name"]} (max {P["max"]})', 'shorter', 'long')
        elif dur < 7: add('montage', 6, f'{dur:.0f} sec is very short', None, 'short')
    if ws:
        st0, en0 = float(job['start']), float(job['end'])
        if any(w[0] < -0.02 < w[1] for w in ws): add('montage', 6, 'The clip starts in the middle of a word', 'snap_start', 'cut_start')
        if any(w[0] < dur - 0.05 < w[1] for w in ws) and not job.get('endcard'): add('montage', 6, 'The clip stops in the middle of a word', 'snap_end', 'cut_end')
    parts = {'beeld': 100, 'geluid': 100, 'montage': 100}
    for i in issues: parts[i['area']] = max(0, parts[i['area']] - i['pen'] * 2)
    score = max(0, 100 - sum(i['pen'] for i in issues))
    return {'score': score, 'parts': parts, 'issues': issues, 'at': time.time(), 'I': m['I']}

def q_fixed_job(e):
    """the safe fixes applied to the saved job of a short"""
    job = dict(e.get('job') or {}); q = e.get('q') or {}; fx_ = dict(job.get('fx') or {})
    words = [tuple(w) for w in (job.get('words') or [])]
    for i in q.get('issues', []):
        f_ = i.get('fix')
        if f_ == 'music_down' and job.get('music'): job['music'] = dict(job['music'], vol=round(float(job['music'].get('vol', .25)) * 0.55, 2))
        if f_ == 'silence': job['jumpcut'] = True
        if f_ == 'hook' and not job.get('hook'): job['hook'] = (e.get('title') or fallback_title([]) or 'WAIT FOR IT').upper()[:40]
        if f_ == 'fewer_zooms': fx_['zooms'] = (fx_.get('zooms') or [])[::2]
        if f_ == 'caps_move' and job.get('cap_y') is not None: job['cap_y'] = min(0.88, float(job['cap_y']) + 0.1)
        if f_ in ('snap_start', 'trim_start') and words:
            st = float(job['start']); nxt = [w for w in words if w[0] >= st - 0.6]
            if nxt: job['start'] = max(0.0, nxt[0][0] - 0.12) if f_ == 'snap_start' or nxt[0][0] - st > 0.6 else st
        if f_ == 'snap_end' and words:
            en = float(job['end']); prv = [w for w in words if w[1] <= en + 0.6]
            if prv: job['end'] = prv[-1][1] + 0.15
        if f_ == 'shorter': job['end'] = float(job['start']) + PLATFORMS.get(SET.get('platform') or 'tiktok', PLATFORMS['tiktok'])['max'] - 1
    job['fx'] = fx_; job['replace'] = e.get('file'); job.pop('test', None); job.pop('preview', None)
    return job


# ---------------------------------------------------------------- 6.4: brand profiles (the app stays JelE, the videos get your own brand)
BRAND_DIR = os.path.join(DATA, 'merken'); os.makedirs(BRAND_DIR, exist_ok=True)
BRAND_TL = threading.local()
def brand_default():
    return {'id': 'jele', 'name': 'JelE', 'tag': SET.get('tag') or default_tag(), 'color': '#ff9200', 'ink': 'auto', 'end_text': 'FOLLOW FOR MORE', 'credit': False,
            'wm': {'on': False, 'pos': 'tr', 'size': 0.18, 'opacity': 0.85, 'when': 'all'}}
def brands():
    L = SET.get('brands') or []
    if not any(b.get('id') == 'jele' for b in L): L = [brand_default()] + L
    return L
def brand_get(bid=None):
    bid = bid or SET.get('brand_default') or 'jele'
    b = next((x for x in brands() if x.get('id') == bid), None) or brand_default()
    d = brand_default(); d.update({k: v for k, v in b.items() if v not in (None, '')}); d['wm'] = dict(brand_default()['wm'], **(b.get('wm') or {}))
    if d['id'] == 'jele': d['tag'] = SET.get('tag') or d['tag']
    return d
def hex_rgb(h, a=255):
    h = (h or '#ff9200').lstrip('#')
    try: return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
    except Exception: return (255, 146, 0, a)
def B(): return getattr(BRAND_TL, 'b', None) or brand_get()
def BC(a=255): return hex_rgb(B().get('color'), a)
def BI(a=255):
    ink = B().get('ink') or 'auto'
    if ink == 'auto': ink = '#111827' if contrast_ok(B().get('color') or '#ff9200') else '#ffffff'
    return hex_rgb(ink, a)
def BHEX(): return '0x' + (B().get('color') or '#ff9200').lstrip('#').upper()
def brand_file(bid, kind):
    for ext in (('.png',) if kind == 'logo' else ('.ttf', '.otf')):
        p = os.path.join(BRAND_DIR, re.sub(r'\W', '', bid), kind + ext)
        if os.path.exists(p): return p
    return None
def logo_colors(path):
    """the two strongest colours in a logo, for the colour suggestion"""
    from PIL import Image
    im = Image.open(path).convert('RGBA').resize((96, 96)); px = [p[:3] for p in im.getdata() if p[3] > 128]
    px = [p for p in px if max(p) - min(p) > 40 and 40 < sum(p) / 3 < 235] or px
    if not px: return ['#ff9200', '#111827']
    q = Image.new('RGB', (len(px), 1)); q.putdata(px); q = q.quantize(colors=4)
    pal = q.getpalette(); counts = sorted(q.getcolors(), reverse=True)
    cols = ['#%02x%02x%02x' % tuple(pal[c * 3:c * 3 + 3]) for _, c in counts]
    return (cols + ['#111827'])[:2]
def contrast_ok(hexcol):
    r, g, b, _ = hex_rgb(hexcol); lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return lum > 110   # dark text on this colour stays readable
def watermark_filter(f, last, inputs, n, dur, OW, OH):
    b = B(); wm = b.get('wm') or {}
    logo = brand_file(b['id'], 'logo') if wm.get('on') else None
    if not logo: return f, last, n
    w = int(OW * max(0.06, min(0.4, float(wm.get('size') or 0.18)))); m = int(OW * 0.04)
    pos = {'tl': (m, m + 90), 'tr': (f'W-w-{m}', m + 90), 'bl': (m, f'H-h-{m + 140}'), 'br': (f'W-w-{m}', f'H-h-{m + 140}'), 'c': ('(W-w)/2', '(H-h)/2')}.get(wm.get('pos'), (f'W-w-{m}', m + 90))
    en = f":enable='gte(t,{max(0, dur - 3):.2f})'" if wm.get('when') == 'end' else ''
    inputs += ['-loop', '1', '-t', f'{dur:.2f}', '-i', logo]
    f += f";[{n}:v]scale={w}:-1,format=rgba,colorchannelmixer=aa={max(0.1, min(1, float(wm.get('opacity') or 0.85))):.2f}[wm];[{last}][wm]overlay=x={pos[0]}:y={pos[1]}{en}[wmo]"
    return f, 'wmo', n + 1

# ---------------------------------------------------------------- 6.4: more out of every clip (Discord, GIF, stills, meme, two views, team folder, recap)
EXTRA_DIR = os.path.join(OUT, 'extra')
def extra_make(file, kind, text=''):
    src = os.path.join(OUT, os.path.basename(file)); base = os.path.splitext(os.path.basename(file))[0]
    if not os.path.exists(src): raise FileNotFoundError(file)
    os.makedirs(EXTRA_DIR, exist_ok=True); dur = probe_duration(src)
    if kind == 'discord':   # under 10 MB, so it fits in a free Discord server
        out = os.path.join(EXTRA_DIR, base + '_discord.mp4'); kbps = max(300, int(9.2 * 8192 / max(1, dur)) - 128)
        r = run(['-y', '-i', src, '-vf', 'scale=-2:min(ih\\,1280)', '-c:v', 'libx264', '-preset', 'medium', '-b:v', f'{kbps}k', '-maxrate', f'{kbps}k', '-bufsize', f'{kbps * 2}k', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', out], capture_output=True)
    elif kind == 'gif':     # the strongest 3.5 seconds as a GIF
        lib = lib_load().get(os.path.basename(file)) or {}; t0 = max(0, min(dur - 3.5, dur * 0.45))
        z = (lib.get('fx') or {}).get('zooms') or []
        if z: t0 = max(0, min(dur - 3.5, float(z[0]) - 1.2))
        out = os.path.join(EXTRA_DIR, base + '.gif')
        r = run(['-y', '-ss', f'{t0:.2f}', '-t', '3.5', '-i', src, '-vf', 'fps=15,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4', out], capture_output=True)
    elif kind == 'stills':  # four strong frames for an Instagram carousel (4:5)
        outs = []
        for i, k in enumerate((0.2, 0.42, 0.62, 0.82)):
            o = os.path.join(EXTRA_DIR, f'{base}_still{i + 1}.jpg'); outs.append(o)
            run(['-y', '-ss', f'{dur * k:.2f}', '-i', src, '-frames:v', '1', '-vf', 'scale=1080:-2,crop=1080:min(ih\\,1350)', '-q:v', '2', o], capture_output=True)
        return outs[0]
    elif kind == 'feed':    # 4:5 for the Instagram and Facebook feed: the middle of the short on a blurred copy of itself
        out = os.path.join(EXTRA_DIR, base + '_4x5.mp4')
        fc = ('[0:v]split[a][b];[a]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,boxblur=28:2,eq=brightness=-0.08[bg];'
              '[b]scale=-2:1350,crop=min(iw\\,1080):1350[fg];[bg][fg]overlay=(W-w)/2:0,format=yuv420p[v]')
        r = run(['-y', '-i', src, '-filter_complex', fc, '-map', '[v]', '-map', '0:a?'] + encoder_args() + ['-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out], capture_output=True)
    elif kind == 'meme':    # white bar on top with text, like gaming meme accounts
        from PIL import Image, ImageDraw
        txt = (text or (lib_load().get(os.path.basename(file)) or {}).get('title') or 'when the round goes like this').strip()
        bar = os.path.join(EXTRA_DIR, base + '_memebar.png'); W, Hb = 1080, 360
        im = Image.new('RGB', (W, Hb), 'white'); d = ImageDraw.Draw(im); f_ = font(66, 'tag'); words = txt.split(); lines = ['']
        for w_ in words:
            t_ = (lines[-1] + ' ' + w_).strip()
            if d.textlength(t_, font=f_) > W - 100 and lines[-1]: lines.append(w_)
            else: lines[-1] = t_
        lines = lines[:3]; lh = 78; y0 = (Hb - lh * len(lines)) / 2
        for i, l in enumerate(lines): d.text((W / 2, y0 + lh * i + lh / 2), l, font=f_, fill='black', anchor='mm')
        im.save(bar); out = os.path.join(EXTRA_DIR, base + '_meme.mp4')
        r = run(['-y', '-i', src, '-i', bar, '-filter_complex', f'[0:v]scale=1080:-2,crop=1080:min(ih\\,{1920 - Hb})[v0];[1:v][v0]vstack=2,scale=1080:-2,format=yuv420p[v]', '-map', '[v]', '-map', '0:a?'] + encoder_args() + ['-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out], capture_output=True)
    else: raise ValueError('unknown format')
    if not os.path.exists(out): raise RuntimeError('failed')
    return out

def audio_offset(path_a, path_b, ta, span=40.0, search=90.0):
    """where does the moment at ta in recording A happen in recording B? found by matching the sound"""
    import numpy as np
    def env(p, t0, d):
        r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-ss', f'{max(0, t0):.2f}', '-t', f'{d:.2f}', '-i', p, '-vn', '-ac', '1', '-ar', '2000', '-f', 's16le', '-'], capture_output=True, creationflags=NOWIN)
        x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)
        if not len(x): return np.zeros(1)
        x = np.abs(x[:len(x) // 20 * 20]).reshape(-1, 20).mean(axis=1) if len(x) >= 20 else np.abs(x)   # 100 values per second
        return (x - x.mean()) / (x.std() + 1e-6)
    a = env(path_a, ta, span); db = probe_duration(path_b); b0 = max(0.0, ta - search)
    b = env(path_b, b0, min(db - b0, span + 2 * search))
    if len(b) < len(a) or len(a) < 200: return None
    c = np.correlate(b, a, mode='valid'); i = int(np.argmax(c)); score = float(c[i] / len(a))
    return (b0 + i / 100.0, score)

def dual_short(sid, start, end, other_sid, title=''):
    s = load_sess(sid); o = load_sess(other_sid); dur = float(end) - float(start)
    m = audio_offset(s['path'], o['path'], float(start))
    if not m or m[1] < 0.15: raise ValueError('I cannot find the moment in the other recording. Are you in the same game, with sound on?')
    ob = m[0]; name = re.sub(r'[^\w-]+', '_', title or ('twee_kanten_' + time.strftime('%H%M%S'))).strip('_'); out = os.path.join(OUT, name + '.mp4')
    f = (f"[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,setsar=1[a];[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,setsar=1[b];"
         f"[b][a]vstack=2[st];[st]drawbox=x=0:y=956:w=1080:h=8:color={BHEX()}:t=fill,format=yuv420p[v]")
    r = run(['-y', '-ss', f'{float(start):.2f}', '-t', f'{dur:.2f}', '-i', s['path'], '-ss', f'{ob:.2f}', '-t', f'{dur:.2f}', '-i', o['path'], '-filter_complex', f, '-map', '[v]', '-map', '0:a:0?']
            + encoder_args() + ['-r', '60', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out], capture_output=True, text=True, errors='replace')
    if r.returncode != 0: raise RuntimeError((r.stderr or '')[-200:])
    lib = lib_load(); lib[os.path.basename(out)] = {'sid': sid, 'start': float(start), 'end': float(end), 'layout': 'dual', 'title': title or 'Twee kanten', 'status': 'goed', 'at': time.time(), 'dur': round(dur, 1), 'post': post_text(title, [])}; lib_save(lib)
    return out

def team_copy(file):
    d = (SET.get('team_dir') or '').strip()
    if not d or not os.path.isdir(d): return None
    who = re.sub(r'\W+', '', SET.get('team_name') or brand_get().get('name') or 'jele')[:20]
    dst = os.path.join(d, f'{who}_{os.path.basename(file)}'); shutil.copy2(os.path.join(OUT, os.path.basename(file)), dst); return dst

def recap_text(sid):
    s = load_sess(sid); lib = lib_load()
    shorts = [(k, e) for k, e in lib.items() if e.get('sid') == sid and not e.get('test') and not e.get('deleted_at')]
    mo = sorted(sorted(s.get('moments', []), key=lambda m: -m.get('score', 0))[:5], key=lambda m: m.get('start', 0))
    lines = [f"Stream recap: {s.get('title', '')}", '']
    if mo:
        lines.append('Best moments:')
        for m in mo: lines.append(f"- {fmt(m.get('start', 0))} {(m.get('title') or (m.get('reasons') or ['moment'])[0]).capitalize()}")
        lines.append('')
    links = [e.get('link') for _, e in shorts if e.get('link')]
    if links: lines += ['Shorts:'] + [f'- {l}' for l in links] + ['']
    if brand_get().get('tag'): lines.append(f"Next stream on {brand_get().get('tag')}")
    return '\n'.join(lines)


def worker():
    while True:
        kind, arg = JOBS.get()
        r_ = pause_reason(kind, arg); said = None
        while r_:
            STATE['paused'] = r_
            if r_ != said: log({'live': 'Heavy work waits until your stream or recording stops', 'disk': 'Less than 2 GB free on the disk: the work waits until there is room', 'busy': 'The pc is very busy, the work waits a moment'}[r_]); said = r_
            time.sleep(2); r_ = pause_reason(kind, arg)
        STATE['paused'] = False
        STATE['cancel'] = False; STATE['why'] = None
        job = {'kind': kind, 'arg': arg if kind in ('analyse', 'remux', 'proxy') else {k: arg.get(k) for k in ('sid', 'start', 'end', 'title', 'layout', 'hook')}, 'since': time.time(), 'stage': 'Starting', 'pct': 0, 'est': tempo_est(kind, arg)}
        STATE['job'] = job; t0 = time.time(); ok = False
        if kind in ('analyse', 'remux', 'proxy'): use_game(arg)
        elif isinstance(arg, dict): use_game(arg.get('sid'), arg.get('start'))
        try:
            if kind == 'analyse':
                with ANALYSE_LOCK:
                    job['since'] = time.time(); analyse(arg); ok = True
            elif kind == 'download': download_url(arg)
            elif kind == 'remux': ok = remux(arg)
            elif kind == 'render':
                if SAFE['on']: arg = dict(arg, fx={'zooms': [], 'killfeed': [], 'stickers': []}, jumpcut=False, sfx=False, zoom=False, music=None, voice=False)
                if arg.get('replace') and not arg.get('preview'):
                    try: note_edit(arg)
                    except Exception: pass
                p = render(arg); ok = bool(p)
                if p and not arg.get('preview') and not arg.get('test'):
                    try:
                        job['stage'] = 'Checking'; job['pct'] = 99
                        if arg.get('loop'): make_loop(p)
                        q_ = quality_check(p, arg, Q_WORDS.get(os.path.basename(p)), {'unsure_left': arg.get('unsure_left') or 0})
                        lib = lib_load(); e_ = lib.get(os.path.basename(p))
                        if e_: e_['q'] = q_; lib_save(lib)
                        log(f'Postklaar-score: {q_["score"]}' + (' · ' + '; '.join(i['msg'] for i in q_['issues'][:3]) if q_['issues'] else ''))
                    except Exception: traceback.print_exc()
                if arg.get('live'): live_done(arg['live'], p)
                if arg.get('preview'):
                    STATE['previews'][arg['preview']] = {'ok': bool(p), 'file': os.path.basename(p) if p else None, 'why': None if p else friendly(STATE.get('why') or '', job.get('stage', '')), 'at': time.time()}
                elif arg.get('test'):   # system check: report, then throw the test away
                    STATE['test'] = {'ok': bool(p), 'secs': round(time.time() - t0, 1), 'at': time.time()}
                    if p:
                        try: os.remove(p)
                        except OSError: pass
                        lib = lib_load(); lib.pop(os.path.basename(p), None); lib_save(lib)
                    log('Test-short', 'ok' if p else 'FAILED', f'in {STATE["test"]["secs"]} sec')
                else:
                    if arg.get('auto'):
                        STATE['auto_left'] = max(0, STATE.get('auto_left', 1) - 1)
                        if STATE['auto_left'] == 0: notify('Your shorts are ready', 'Open the Clipper: your new shorts are in your inbox.', 'tada')
                    why = None
                    if not p:
                        raw = STATE.get('why') or ''
                        why = 'Stopped.' if raw in ('gestopt', 'stopped') else friendly(raw, job.get('stage', ''))
                        if raw not in ('gestopt', 'stopped'): note_error('making short (' + str(job.get('stage')) + ')', raw)
                    STATE['done'].append({'file': os.path.basename(p) if p else None, 'ok': bool(p), 'at': time.time(), 'why': why, 'title': arg.get('hook') or arg.get('title') or ''})
            if ok and kind != 'download' and not (isinstance(arg, dict) and arg.get('test')): tempo_note(kind, arg, time.time() - job['since'])
        except Exception:
            tb = traceback.format_exc(); print(tb, file=sys.stderr); note_error(kind + ' (' + str(job.get('stage')) + ')', tb)
            STATE['last_error'] = {'at': time.time(), 'kind': kind, 'msg': friendly(tb, job.get('stage', ''))}
            if kind == 'analyse':
                try: s = load_sess(arg); s['status'] = 'error while analysing'; s['why'] = friendly(tb, 'zoeken'); save_sess(s)
                except Exception: pass
            if kind == 'render' and arg.get('preview'):
                STATE['previews'][arg['preview']] = {'ok': False, 'file': None, 'why': friendly(tb, job.get('stage', '')), 'at': time.time()}
            elif kind == 'render':
                STATE['done'].append({'file': None, 'ok': False, 'at': time.time(), 'why': friendly(tb, job.get('stage', '')), 'title': arg.get('hook') or arg.get('title') or ''})
        STATE['job'] = None; JOBS.done()
        if kind == 'analyse' and SET.get('proxy', True):
            try: PROXYQ.put(arg)
            except Exception: pass

def n_workers():
    w = SET.get('parallel', 'auto')
    if w == 'auto': return 2 if CORES >= 8 else 1
    try: return max(1, min(3, int(w)))
    except Exception: return 1
