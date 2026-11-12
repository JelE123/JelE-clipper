# JelE Clipper part: small helpers and Valorant matches. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- small helpers
import urllib.request, urllib.parse
def http_json(url, headers=None, data=None, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': 'JelE-Clipper/' + VERSION, **(headers or {})}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode('utf-8', 'replace'))

def notify(title, msg, tags='movie_camera', open_hash=None):
    """push message on your phone (free ntfy app, subscribe to your topic). Tapping it opens the right short when phone access is on"""
    if not (SET.get('ntfy') and SET.get('ntfy_topic')): return False
    try:
        hd = {'Title': title.encode('utf-8').decode('latin-1', 'ignore'), 'Tags': tags, 'User-Agent': 'JelE-Clipper'}
        if SET.get('phone'):
            try: hd['Click'] = phone_url() + ('#' + open_hash if open_hash else '')
            except Exception: pass
        req = urllib.request.Request('https://ntfy.sh/' + urllib.parse.quote(SET['ntfy_topic']), data=msg.encode('utf-8'), headers=hd)
        urllib.request.urlopen(req, timeout=8).read(); return True
    except Exception as e: log('Could not send the notification:', e); return False

SFX_DIR = None
def sfx_files():
    """two small sounds, made by the clipper itself (no copyright): boom.wav and whoosh.wav"""
    import numpy as np, wave as wv
    d = os.path.join(DATA, 'sfx'); os.makedirs(d, exist_ok=True)
    def save(name, x):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            y = (np.clip(x, -1, 1) * 32000).astype(np.int16)
            with wv.open(p, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(y.tobytes())
        return p
    sr = 48000; t = np.arange(int(sr * 0.9)) / sr
    f = 110 * np.exp(-t * 3.2) + 38                         # falling low tone
    boom = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 4.0) * 0.9
    rng = np.random.default_rng(7); click = rng.normal(0, 1, len(t)) * np.exp(-t * 60) * 0.25
    tw = np.arange(int(sr * 0.45)) / sr; noise = rng.normal(0, 1, len(tw))
    env = np.sin(np.pi * tw / tw[-1]) ** 2
    kern = np.ones(40) / 40; whoosh = np.convolve(noise, kern, mode='same') * env * 0.8
    return {'boom': save('boom.wav', boom + click), 'whoosh': save('whoosh.wav', whoosh)}

MUSIC_DIR = os.path.join(HERE, 'muziek'); os.makedirs(MUSIC_DIR, exist_ok=True)
def music_list():
    return sorted(os.path.basename(f) for f in glob.glob(os.path.join(MUSIC_DIR, '*')) if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac')))

def sticker_png(folder, text, kind='stamp', W=1080, i=0):
    """a stamp like ACE / NO WAY (tilted, orange), a chapter label, or the big WAIT FOR IT / REPLAY text"""
    from PIL import Image, ImageDraw, ImageFilter
    text = re.sub(r'\s+', ' ', str(text).strip().upper())[:28] or 'NO WAY'
    big = {'teaser': 150, 'replay': 110, 'stamp': 120, 'pill': 80, 'chapter': 58}.get(kind, 110) * (W / 1080 if W < 1500 else 0.85)
    f = font(int(big), 'tag' if kind == 'chapter' else 'caption'); tmp = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    w = tmp.textlength(text, font=f); h = big * 1.2; pad = big * 0.35
    img = Image.new('RGBA', (int(w + pad * 2 + 40), int(h + pad * 2 + 40)), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    box = (20, 20, 20 + w + pad * 2, 20 + h + pad * 0.6)
    cxy = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    if kind == 'stamp':
        d.rounded_rectangle(box, radius=int(big * 0.18), fill=BC(), outline=BI(), width=int(big * 0.07))
        d.text(cxy, text, font=f, fill=BI(), anchor='mm')
    elif kind == 'pill':
        d.rounded_rectangle(box, radius=int(h), fill=BI(235)); d.text(cxy, text, font=f, fill=(255, 255, 255, 255), anchor='mm')
    elif kind == 'chapter':
        d.rounded_rectangle(box, radius=int(big * 0.3), fill=BI(225)); d.rectangle((box[0], box[1], box[0] + 10, box[3]), fill=BC())
        d.text(cxy, text, font=f, fill=(255, 255, 255, 255), anchor='mm')
    else:   # teaser / replay: big text with an outline
        d.text(cxy, text, font=f, fill=(255, 255, 255, 255) if kind == 'teaser' else BC(), anchor='mm', stroke_width=int(big * 0.08), stroke_fill=BI())
    if kind == 'stamp': img = img.rotate(-7 if i % 2 == 0 else 6, resample=Image.BICUBIC, expand=True)
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 120), mask=img.split()[3]); sh = sh.filter(ImageFilter.GaussianBlur(8))
    out = Image.new('RGBA', img.size, (0, 0, 0, 0)); out.alpha_composite(sh, (4, 8)); out.alpha_composite(img)
    p = os.path.join(folder, f'sticker_{kind}_{i}.png'); out.save(p); return p

def cam_at(s, t):
    """where the cam frame was at second t of the recording (you can move it during a stream)"""
    cams = s.get('cams') or []
    cur = s.get('cam') or SET['cam']
    for tt, c in sorted(cams, key=lambda x: x[0]):
        if tt <= t + 1: cur = c
    return cur if (s.get('cam') or cams) else SET['cam']

def fx_suggest(sid, start, end, job=None):
    """the effects a pro editor would add, as editable items. times are seconds into the clip"""
    job = job or {}; s = load_sess(sid); dur = end - start
    ws = [tuple(w) for w in (job.get('words') or [])] or [tuple(w) for w in load_transcript(sid) if start <= w[0] <= end]
    if not ws:
        m = next((m for m in s.get('moments', []) if m.get('id') == job.get('mid')), None)
        if m: ws = [tuple(w) for w in m.get('words', [])]
    zooms = zoom_pick(zoom_times(sid, job, ws, start, dur), dur)
    kills = [kt - start for kt in s.get('game_kills', []) if start <= kt <= end]
    evs = [e for e in s.get('game_events', []) if start <= e['t'] <= end]
    peak, why_peak = clip_peak(s, ws, start, end)
    fx = {'zooms': [round(z, 2) for z in zooms], 'killfeed': [], 'stickers': [], 'voice': SET.get('voice_clean', False)}
    P = gprof()
    if SET.get('fx_killfeed', True) and kills and P.get('killfeed'): fx['killfeed'] = [round(k_, 2) for k_ in kills if 0.3 < k_ < dur - 0.5][:6]
    if SET.get('fx_stickers', True):
        for e in evs: fx['stickers'].append({'t': round(e['t'] - start + 0.15, 2), 'dur': 1.6, 'text': e['label'], 'x': 0.5, 'y': 0.3, 'kind': 'stamp'})
        if not evs:   # the big moment of this game in what you said: "victory royale", "diamonds", "ace"
            srx = re.compile(r'\b(' + (P.get('strong') or 'ace') + r')\b', re.I)
            for w in ws:
                m_ = srx.search(w[2])
                if m_ and 0.3 < w[0] - start < dur - 1:
                    lab = next((x for x in P.get('stickers', []) if m_.group(0).lower().replace(' ', '') in x.lower().replace(' ', '')), m_.group(0).upper())
                    fx['stickers'].append({'t': round(w[0] - start, 2), 'dur': 1.6, 'text': lab[:24], 'x': 0.5, 'y': 0.3, 'kind': 'stamp'}); break
    # one story: the opening shows the second before the payoff (not the payoff itself), the replay shows that same payoff again.
    # only when there is a real payoff, and only when the clip does not open with it anyway
    # the story of this moment (worked out after the stream): the payoff, where to zoom, a replay or not, the music
    mm = next((x for x in s.get('moments', []) if x.get('id') == job.get('mid')), None) if job.get('mid') else None
    br = (mm or {}).get('brief') or {}
    if br.get('payoff') is not None and start <= br['payoff'] <= end:
        peak, why_peak = br['payoff'] - start, 'story'
        bz = [round(z - start, 2) for z in (br.get('zoom') or []) if start < z < end]
        if bz: fx['zooms'] = bz
        if br.get('music'): fx['music_mood'] = br['music']; fx['music_file'] = music_for_mood(br['music'])
        if br.get('cause') is not None and start <= br['cause'] <= end: fx['cause'] = round(br['cause'] - start, 2)
        fo = br.get('focus')
        if fo and fo.get('box') and start <= fo['t'] <= end:   # show what you react to big: the chat message, the killfeed
            fx['focus'] = [{'t': round(fo['t'] - start + 0.2, 2), 'dur': float(fo.get('dur') or 3.0), 'box': fo['box'], 'region': fo.get('region'), 'text': fo.get('text', '')}]
        if br.get('about'): fx['about'] = br['about']; fx['type'] = br.get('type')
        if br.get('layout'): fx['layout'] = br['layout']
        ctx_ = (br.get('context') or '').strip()
        if ctx_ and int(SET.get('ctx_cards') or 1) >= 1:   # a context card for strangers: "1v3, last round", "he typed this in team chat"
            fx.setdefault('stickers', []).append({'t': 0.15, 'dur': 2.8, 'text': ctx_[:28], 'x': 0.5, 'y': 0.1, 'kind': 'chapter'})
    fx['peak'] = round(peak, 2) if peak is not None else None; fx['peak_why'] = why_peak
    # the teaser shows what you react to (the cause: the kill, the angle, the message), not you reacting.
    # a replay only for a real play (a kill from the match data, or the story says clutch / skill), never for talking or a chat message
    cz = fx.get('cause')
    if peak is not None and why_peak in ('event', 'shout', 'marker', 'story') and dur > 10:
        tz_at = cz if cz is not None else peak - 0.6
        if SET.get('fx_teaser', True) and tz_at > 2.5: fx['teaser'] = {'t': round(max(0, tz_at - 0.4), 2), 'len': 1.1, 'text': ''}
        play = (why_peak == 'event') or (why_peak == 'story' and br.get('replay') and br.get('type') in ('clutch', 'skill'))
        if SET.get('fx_replay', True) and play and not fx.get('focus'):
            ra = cz if cz is not None else peak
            if ra < dur - 0.4:
                if SET.get('slowmo_not_replay', True): fx['slowmo'] = {'a': round(max(0, ra - 0.5), 2), 'b': round(min(dur, ra + 0.6), 2), 'speed': 0.5}   # slow it down right where it happens
                else: fx['replay'] = {'a': round(max(0, ra - 1.6), 2), 'b': round(min(dur, ra + 0.8), 2), 'speed': 0.5}
        if SET.get('fx_freeze', True) and cz is not None and br.get('type') in ('fail', 'funny', 'reaction', 'rage') and not fx.get('focus') and 1.0 < cz < dur - 2:
            fx['freeze'] = {'t': round(cz, 2), 'len': 0.8, 'text': 'WAIT...'}   # the picture stops for a second on what you react to
    return fx

def clip_peak(s, ws, start, end):
    """(seconds into the clip, why) of the payoff: last kill of a multikill/clutch, else your strongest shout, else the clip button"""
    dur = end - start
    evs = [e for e in s.get('game_events', []) if start <= e['t'] <= end]
    if evs: return max(evs, key=lambda e: e['strength'])['t'] - start, 'event'
    best = None
    for i, w in enumerate(ws):
        if not (start <= w[0] <= end): continue
        ph = ' '.join(x[2] for x in ws[i:i + 3] if x[0] - w[0] < 1.5)
        sc = (3 if SAY_STRONG.match(re.sub(r"[^\w' ]", '', ph)) else 0) + len(SAY_HYPE.findall(ph))
        if sc >= 3 and (best is None or sc > best[0]): best = (sc, w[0] - start - 0.6)
    if best: return best[1], 'shout'
    mk = [m['t'] - start for m in s.get('markers', []) if start <= m['t'] <= end]
    if mk: return max(0.5, mk[0] - 1.0), 'marker'
    return (dur * 0.7 if dur > 4 else None), 'guess'

def make_mezz(parts, work):
    """glue pieces of recordings into one temporary video (for montages and for cutting out dead air)"""
    def one(i, pt):
        p, a, b = pt[:3]; sp = pt[3] if len(pt) > 3 else 1.0
        out = os.path.join(work, f'part{i}.mp4')
        vf = 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1'
        if sp == 0:   # a freeze frame: the picture at a, standing still for b - a seconds (quiet)
            L = max(0.2, b - a)
            r = run(['-y', '-ss', f'{a:.3f}', '-i', p, '-f', 'lavfi', '-t', f'{L:.3f}', '-i', 'anullsrc=r=48000:cl=stereo',
                     '-filter_complex', f'[0:v:0]trim=end_frame=1,{vf},loop=loop=-1:size=1:start=0,setpts=N/60/TB,fps=60,trim=duration={L:.3f}[v]',
                     '-map', '[v]', '-map', '1:a', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '15', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-ac', '2', '-t', f'{L:.3f}', out],
                    capture_output=True, text=True, errors='replace')
            if r.returncode != 0 or not os.path.exists(out): raise RuntimeError('making a freeze frame failed: ' + (r.stderr or '')[-200:])
            return out
        af = 'aformat=sample_rates=48000:channel_layouts=stereo'
        if sp < 0.999:   # slow motion for the replay: smooth frames, lower voice is fine for a replay
            vf += f',setpts={1 / sp:.4f}*PTS,minterpolate=fps=60:mi_mode=blend'
            t_ = sp; chain = []
            while t_ < 0.5: chain.append('atempo=0.5'); t_ /= 0.5
            chain.append(f'atempo={t_:.4f}'); af += ',' + ','.join(chain)
        vf += ',fps=60'
        ln_ = (b - a) / max(sp, 0.01)
        if ln_ > 0.2: af += f',afade=t=in:d=0.015,afade=t=out:st={max(0.0, ln_ - 0.02):.3f}:d=0.02'   # no click on the cut
        thr = str(max(2, CORES // min(len(parts), 3)))
        r = run(['-y', '-ss', f'{a:.3f}', '-t', f'{b - a:.3f}', '-i', p, '-map', '0:v:0', '-map', '0:a:0?', '-vf', vf, '-af', af,
                 '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '15', '-threads', thr, '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-ac', '2', out], capture_output=True, text=True, errors='replace')
        if r.returncode != 0 or not os.path.exists(out): raise RuntimeError('making a piece failed: ' + (r.stderr or '')[-200:])
        return out
    # 6.0: the pieces are made at the same time instead of one by one
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, min(3, len(parts)))) as ex:
        files = list(ex.map(lambda ip: one(*ip), enumerate(parts)))
    lst = os.path.join(work, 'parts.txt')
    with open(lst, 'w', encoding='utf-8') as fh:
        for f_ in files: fh.write(f"file '{f_.replace(os.sep, '/')}'\n")
    out = os.path.join(work, 'mezz.mp4')
    r = run(['-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out], capture_output=True, text=True, errors='replace')
    if r.returncode != 0: raise RuntimeError('joining the pieces failed: ' + (r.stderr or '')[-200:])
    return out

def music_beats(mfile, offset, dur):
    """the beats of a song (seconds from where it starts playing in the short), so zooms and cuts land on the beat"""
    import numpy as np
    sr = 8000
    r = subprocess.run([FF, '-v', 'error', '-ss', f'{max(0, offset):.2f}', '-t', f'{dur + 1:.2f}', '-i', mfile, '-vn', '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'], capture_output=True, creationflags=NOWIN)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    hop = 80   # 10 ms
    n = len(x) // hop
    if n < 300: return []
    e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)); on = np.maximum(0, np.diff(np.log(e + 1e-4), prepend=0))
    on = on - np.convolve(on, np.ones(20) / 20, mode='same'); on[on < 0] = 0
    lags = np.arange(30, 100)   # 60 to 200 beats per minute
    ac = np.array([float((on[:-l] * on[l:]).sum()) for l in lags]); per = int(lags[ac.argmax()])
    ph = int(np.argmax([on[p::per].sum() for p in range(per)]))
    return [round((ph + k * per) * hop / sr, 3) for k in range(int((n - ph) / per) + 1)]

def snap_to_beats(times, beats, win=0.25):
    out = []
    for t in times:
        b = min(beats, key=lambda b: abs(b - t)) if beats else None
        out.append(round(b, 3) if b is not None and abs(b - t) <= win else t)
    return out

def clip_env(path, start, dur, step=0.1):
    """loudness of a clip every 0.1 s (dB)"""
    import numpy as np
    r = subprocess.run([FF, '-v', 'error', '-ss', f'{start:.2f}', '-t', f'{dur:.2f}', '-i', path, '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', '-'], capture_output=True, creationflags=NOWIN)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0; n = int(8000 * step)
    if len(x) < n: return np.zeros(0)
    x = x[:len(x) // n * n].reshape(-1, n); return 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-6)

def clip_motion(path, start, dur, step=0.1):
    """how much the picture changes, every 0.1 s (flicks, fights and movement are high)"""
    import numpy as np
    W_, H_ = 64, 36
    r = subprocess.run([FF, '-v', 'error', '-ss', f'{start:.2f}', '-t', f'{dur:.2f}', '-i', path, '-an', '-vf', f'fps={1 / step:g},scale={W_}:{H_},format=gray', '-f', 'rawvideo', '-'],
                       capture_output=True, creationflags=NOWIN)
    n = len(r.stdout) // (W_ * H_)
    if n < 3: return np.zeros(0)
    fr = np.frombuffer(r.stdout[:n * W_ * H_], dtype=np.uint8).reshape(n, H_, W_).astype(np.float32)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    return np.concatenate([[d[0]], d])

def keep_segments(path, ws, start, dur, protect, peak=None):
    """which parts of a clip to keep when the dead air goes out.
    Only a gap where you say nothing, the game is quiet AND the picture hardly moves counts as boring.
    Never touched: the run-up to the payoff, kills and clip presses, the first second and the end.
    At most a quarter of the clip goes out, the most boring gaps first."""
    import numpy as np
    rel = sorted((a - start, b - start) for a, b, t in ws if b > start and a < start + dur)
    if len(rel) < 2: return None
    env = clip_env(path, start, dur)
    try: mot = clip_motion(path, start, dur)
    except Exception: mot = np.zeros(0)
    quiet = np.percentile(env, 50) if len(env) else 0
    still = np.percentile(mot, 45) if len(mot) else 0
    guard = [(p - 1.5, p + 0.6) for p in protect]
    if peak is not None: guard.append((peak - 4.0, peak + 1.5))      # the build-up to the payoff stays whole
    cand = []
    for (a1, b1), (a2, b2) in zip(rel, rel[1:]):
        g0, g1 = b1 + 0.35, a2 - 0.3                                   # keep a breath after and before you talk
        if g1 - g0 < 1.0 or g0 < 1.2 or g1 > dur - 1.5: continue
        if any(x <= g1 and g0 <= y for x, y in guard): continue
        i0, i1 = int(g0 / 0.1), int(g1 / 0.1)
        seg = env[i0:i1] if len(env) else []
        if len(seg) and (float(np.max(seg)) > quiet + 5 or float(np.mean(seg)) > quiet + 1.5): continue   # game sound: something happens
        mv = mot[i0:i1] if len(mot) else []
        if len(mv) and (float(np.mean(mv)) > still or float(np.max(mv)) > still * 3.5): continue          # the picture moves: aiming, a fight
        boring = (g1 - g0) * (1.0 + (still - float(np.mean(mv))) / (still + 1e-3) if len(mv) else 1.0)
        cand.append((boring, g0, g1))
    budget = dur * 0.25; cuts = []
    for _, g0, g1 in sorted(cand, reverse=True):
        if len(cuts) >= 5 or sum(b - a for a, b in cuts) + (g1 - g0) > budget: continue
        cuts.append((g0, g1))
    cuts.sort()
    if sum(b - a for a, b in cuts) < 1.0: return None
    keep = []; t = 0.0
    for a, b in cuts: keep.append((t, a)); t = b
    keep.append((t, dur)); return [(a, b) for a, b in keep if b - a > 0.2]

def jumpcut_plan(sid, a, b):
    """the boring bits that would go out of this clip, in recording time (for the editor, so you see and can undo them)"""
    s = load_sess(sid); pp = proxy_path(sid); path = pp if s.get('proxy') and os.path.exists(pp) else s['path']
    ws = [tuple(w) for w in load_transcript(sid) if a - 1 <= w[0] <= b + 1]
    fx = fx_suggest(sid, a, b, {'words': [w for w in ws if a <= w[0] <= b]})
    protect = [float(z) for z in fx.get('zooms', [])] + [float(z) for z in fx.get('killfeed', [])] + [float(x.get('t', 0)) for x in fx.get('stickers', [])]
    if fx.get('replay'): protect += [fx['replay']['a'], fx['replay']['b']]
    keep = keep_segments(path, ws, a, b - a, protect, fx.get('peak'))
    if not keep: return []
    out = []
    for (x0, x1), (y0, y1) in zip(keep, keep[1:]): out.append([round(a + x1, 2), round(a + y0, 2)])
    return out

def remap(t, keep):
    """time in the original clip -> time after cutting"""
    acc = 0.0
    for a, b in keep:
        if t < a: return acc
        if t <= b: return acc + t - a
        acc += b - a
    return acc

# ---------------------------------------------------------------- your Valorant matches (HenrikDev API)
def match_events(s):
    """multikills, aces and clutches from your real matches, as times in this recording"""
    key, name, tag = CFG.get('HENRIK_KEY'), CFG.get('RIOT_NAME'), CFG.get('RIOT_TAG')
    if not (SET.get('matchdata', True) and key and name and tag): return None
    reg = (CFG.get('REGION') or 'eu').lower(); t0, t1 = s.get('start') or 0, (s.get('stop') or time.time())
    url = f'https://api.henrikdev.xyz/valorant/v4/matches/{reg}/pc/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}?size=10'
    try: data = http_json(url, {'Authorization': key}).get('data') or []
    except Exception as e: log('Could not fetch match data:', e); return None
    evs = []; kills_me = []; off = float(SET.get('match_offset') or 0)
    for m in data:
        md = m.get('metadata') or {}
        st = md.get('started_at') or md.get('game_start_patched')
        try:
            import datetime as dt
            ms = dt.datetime.fromisoformat(str(st).replace('Z', '+00:00')).timestamp() if isinstance(st, str) else float(md.get('game_start') or 0)
        except Exception: continue
        length = (md.get('game_length_in_ms') or md.get('game_length') or 0) / 1000.0
        if ms + length < t0 - 60 or ms > t1 + 60: continue                     # not during this recording
        players = m.get('players') if isinstance(m.get('players'), list) else (m.get('players') or {}).get('all_players', [])
        me = next((p for p in players if str(p.get('name', '')).lower() == name.lower() and str(p.get('tag', '')).lower() == tag.lower()), None)
        if not me: continue
        mypu = me.get('puuid'); myteam = me.get('team_id') or me.get('team')
        team_of = {p.get('puuid'): (p.get('team_id') or p.get('team')) for p in players}
        mapname = ((md.get('map') or {}).get('name') if isinstance(md.get('map'), dict) else md.get('map')) or ''
        rounds = m.get('rounds') or []
        def won(rn):
            r = rounds[rn] if rn < len(rounds) else {}
            return str(r.get('winning_team', '')).lower() == str(myteam).lower()
        byr = {}
        for k in m.get('kills') or []:
            rn = k.get('round', 0); tm = (k.get('time_in_match_in_ms') or k.get('kill_time_in_match') or 0) / 1000.0
            killer = (k.get('killer') or {}).get('puuid') or k.get('killer_puuid'); victim = (k.get('victim') or {}).get('puuid') or k.get('victim_puuid')
            byr.setdefault(rn, []).append((tm, killer, victim, ((k.get('weapon') or {}).get('name') if isinstance(k.get('weapon'), dict) else k.get('damage_weapon_name')) or ''))
        for rn, ks in byr.items():
            ks.sort(); mine = [x for x in ks if x[1] == mypu]
            for x in mine: kills_me.append(ms + x[0] + off - t0)
            # clutch: all my teammates dead while I live, enemies left, and we win the round
            alive_team = {p for p, tm_ in team_of.items() if tm_ == myteam}; alive_enemy = {p for p, tm_ in team_of.items() if tm_ != myteam}
            clutch = 0; dead_me = False
            for tm, kl, vc, wp in ks:
                if vc in alive_team: alive_team.discard(vc)
                if vc in alive_enemy: alive_enemy.discard(vc)
                if vc == mypu: dead_me = True
                if not dead_me and alive_team == {mypu} and not clutch: clutch = len(alive_enemy)
            label = None; strength = 0
            if len(mine) >= 5: label, strength = 'ACE', 16
            elif len(mine) == 4: label, strength = '4K', 11
            elif clutch >= 2 and won(rn) and not dead_me: label, strength = f'1v{clutch} CLUTCH', 7 + 2 * clutch
            elif len(mine) == 3: label, strength = '3K', 6
            elif clutch == 1 and won(rn) and not dead_me and mine: label, strength = '1v1 CLUTCH', 5
            if label:
                ts = [x[0] for x in (mine or ks[-1:])]
                evs.append({'t0': ms + ts[0] + off - t0, 't': ms + ts[-1] + off - t0, 'label': label, 'strength': strength, 'round': rn + 1,
                            'map': mapname, 'weapon': mine[-1][3] if mine else ''})
    log(f'Matchdata: {len(evs)} big moments found ({len(kills_me)} of them your kills)')
    return {'events': evs, 'kills': kills_me}

def twitch_clip_times(s):
    """clips viewers made on Twitch during this recording"""
    cid, sec = CFG.get('TWITCH_CLIENT_ID'), CFG.get('TWITCH_CLIENT_SECRET')
    if not (SET.get('twitch_clips', True) and cid and sec and s.get('start')): return []
    try:
        tok = http_json('https://id.twitch.tv/oauth2/token', data=urllib.parse.urlencode({'client_id': cid, 'client_secret': sec, 'grant_type': 'client_credentials'}).encode())['access_token']
        h = {'Client-Id': cid, 'Authorization': 'Bearer ' + tok}
        uid = http_json('https://api.twitch.tv/helix/users?login=' + urllib.parse.quote(CFG['CHANNEL'].lower().lstrip('#')), h)['data'][0]['id']
        iso = lambda e: time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e))
        d = http_json(f"https://api.twitch.tv/helix/clips?broadcaster_id={uid}&started_at={iso(s['start'] - 60)}&ended_at={iso((s.get('stop') or time.time()) + 600)}&first=50", h).get('data', [])
        import datetime as dt
        out = []
        for c in d:
            ce = dt.datetime.fromisoformat(c['created_at'].replace('Z', '+00:00')).timestamp()
            out.append({'t': ce - s['start'] - 12, 'by': c.get('creator_name', ''), 'views': c.get('view_count', 0), 'title': c.get('title', '')})
        log(f'Twitch: {len(out)} clips from viewers found'); return out
    except Exception as e: log('Could not fetch Twitch clips:', e); return []

def collapse_loops(words, ti=2):
    """the speech model sometimes gets stuck and says the same words again and again.
    a block of 2+ words that comes 3+ times in a row (or one word 6+ times) is kept only once"""
    import re as _r
    k = [_r.sub(r"[^\w']+", '', str(w[ti]).lower()) for w in words]
    out, i, n = [], 0, len(words)
    while i < n:
        hit = 0
        for L in range(1, 13):
            if i + L * 3 > n: break
            blk = k[i:i + L]
            if not any(blk): continue
            r = 1
            while i + (r + 1) * L <= n and k[i + r * L:i + (r + 1) * L] == blk: r += 1
            if r >= (6 if L == 1 else 3): hit = (L, r); break
        if hit:
            L, r = hit; out.extend(words[i:i + L]); i += L * r
        else:
            out.append(words[i]); i += 1
    return out
