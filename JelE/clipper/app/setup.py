# JelE Clipper part: system check and setup. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- system check (everything that can go wrong on your pc)
def system_check():
    out = []
    def add(name, ok, info, fix=''): out.append({'name': name, 'ok': ok, 'info': info, 'fix': fix})
    try:
        v = subprocess.run([FF, '-version'], capture_output=True, text=True, creationflags=NOWIN, errors='replace').stdout.split('\n')[0]
        add('ffmpeg', True, v[:70])
    except Exception as e: add('ffmpeg', False, str(e)[:120], 'Run install.bat again')
    enc = encoder_args()[1]
    add('Making the video', True, {'h264_nvenc': 'with your NVIDIA card', 'h264_amf': 'with your AMD card', 'h264_qsv': 'with your Intel chip'}.get(enc, 'with your processor (x264)'))
    add('Audio filter', _AF_OK['ok'], 'on' if _AF_OK['ok'] else 'does not work with this ffmpeg, working without it (that is fine)')
    if whisper_ok():
        try:
            import faster_whisper; fv = getattr(faster_whisper, '__version__', '?')
        except Exception: fv = '?'
        add('Speech recognition', True, f'faster-whisper {fv}, {CORES} cores' + (', NVIDIA' if has_cuda() else ''))
        for m, what in (('small.en', 'for searching'), ('large-v3-turbo', 'for captions')):
            c = model_cached(m); add(f'Model {m}', c, ('downloaded' if c else 'not downloaded yet, happens automatically on first use') + f' ({what})')
    else: add('Speech recognition', False, 'faster-whisper not found', 'Run install.bat again')
    add('OBS', obs.ok, 'connected' if obs.ok else 'not connected', 'Is OBS running? Is your OBS password right (Settings > Keys)?')
    if obs.ok:
        rd = (obs.req('GetRecordDirectory') or {}).get('recordDirectory')
        add('Recording folder', bool(rd), rd or 'unknown')
        cam = obs.detect_cam(); add('Cam frame in OBS', bool(cam), f'found at {cam}' if cam else 'mascot cam not found in your scenes', 'Is the mascot (game) a browser source in one of your scenes?')
    try:
        du = shutil.disk_usage(OUT); free = du.free / 1e9
        add('Free disk space', free > 5, f'{free:.0f} GB free')
    except Exception: pass
    try:
        import qrcode; add('QR for your phone', True, 'ready')
    except Exception: add('QR for your phone', False, 'package missing', 'Restart the clipper, it installs it by itself')
    return out

PHONE = {'srv': None, 'seen': 0}
def lan_ip():
    try:
        s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s_.connect(('10.255.255.255', 1)); ip = s_.getsockname()[0]; s_.close(); return ip
    except Exception: return '127.0.0.1'
def phone_url():
    if not SET.get('phone_key'): SET['phone_key'] = uuid.uuid4().hex[:10]; save_settings(SET)
    return f'http://{lan_ip()}:{PORT + 1}/m?k={SET["phone_key"]}'
PHONE_HTML = open(os.path.join(HERE, 'telefoon.html'), encoding='utf-8').read() if os.path.exists(os.path.join(HERE, 'telefoon.html')) else '<p>telefoon.html is missing</p>'
# ---------------------------------------------------------------- 6.5: setup checks
MODEL_MB = {'small.en': 484, 'small': 484, 'medium.en': 1530, 'medium': 1530, 'large-v3': 3090, 'large-v3-turbo': 1620}
MODELDL = {'busy': False, 'name': '', 'err': '', 'done': []}
def model_names():
    """which speech models this pc will use (same choice as whisper_model)"""
    name = SET.get('whisper_model', 'auto'); cuda = has_cuda(); out = []
    for purpose in ('scan', 'captions'):
        n = name if name != 'auto' else ('large-v3' if cuda else ('large-v3-turbo' if purpose == 'captions' and CORES >= 8 else 'small.en'))
        if SET.get('language', 'en') != 'en': n = n.replace('.en', '')
        if n not in out: out.append(n)
    return out
def hub_mb(name):
    """how much of this speech model is downloaded (MB). files are counted once, also when the cache uses links"""
    tot = 0; seen = set()
    for r, _, fs in os.walk(hub_dir(name)):
        for f in fs:
            p_ = os.path.realpath(os.path.join(r, f))
            if p_ in seen or p_.endswith('.incomplete'): continue
            seen.add(p_)
            try: tot += os.path.getsize(p_)
            except OSError: pass
    return tot / 1e6
def model_status():
    ms = []
    for n in model_names():
        mb = hub_mb(n); total = MODEL_MB.get(n, 1500)
        ms.append({'name': n, 'mb': round(min(mb, total)), 'total': total, 'ready': model_cached(n) and mb > total * 0.8})
    return {'models': ms, 'busy': MODELDL['busy'], 'now': MODELDL['name'], 'error': MODELDL['err'], 'whisper': whisper_ok()}
def model_get():
    if MODELDL['busy']: return {'ok': True}
    if not whisper_ok(): return {'ok': False, 'why': 'The speech package is not installed yet. Run install.bat again.'}
    def run_():
        MODELDL.update(busy=True, err='')
        try:
            from faster_whisper.utils import download_model
            for n in model_names():
                MODELDL['name'] = n; log(f'Downloading speech model "{n}"...'); download_model(n)
            log('Speech models are ready')
        except Exception as e: MODELDL['err'] = friendly(e) if 'friendly' in globals() else str(e)[:160]; log('Downloading the speech model failed:', e)
        finally: MODELDL.update(busy=False, name='')
    threading.Thread(target=run_, daemon=True).start(); return {'ok': True}

def vod_check():
    """Twitch VOD track: a separate audio track without music, so your VODs are not muted"""
    if not obs.ok: return {'ok': None, 'msg': 'OBS is not connected. Start OBS and try again.'}
    g = lambda cat, name: (obs.req('GetProfileParameter', {'parameterCategory': cat, 'parameterName': name}) or {}).get('parameterValue')
    mode = (g('Output', 'Mode') or '').lower()
    if mode != 'advanced':
        return {'ok': False, 'msg': 'Your output mode is Simple. A VOD track needs Advanced.',
                'steps': ['OBS > Settings > Output: set Output Mode to Advanced', 'Streaming tab: tick "Twitch VOD Track" and pick track 2',
                          'Audio Mixer > gear > Advanced Audio Properties: untick track 2 for your music']}
    on = str(g('AdvOut', 'VodTrackEnabled') or '').lower() in ('true', '1')
    vt = g('AdvOut', 'VodTrackIndex'); st = g('AdvOut', 'TrackIndex')
    if not on:
        return {'ok': False, 'msg': 'The Twitch VOD track is off. Music in your stream can then get your VOD muted.',
                'steps': ['OBS > Settings > Output > Streaming tab: tick "Twitch VOD Track"', 'Pick a different track than your stream, for example track 2',
                          'Audio Mixer > gear > Advanced Audio Properties: untick that track for your music']}
    if vt and st and str(vt) == str(st):
        return {'ok': False, 'msg': f'Your VOD uses the same track as your stream (track {vt}), so the music is still in it.',
                'steps': ['Pick a different track for "Twitch VOD Track", for example track 2', 'Untick that track for your music (Advanced Audio Properties)']}
    return {'ok': True, 'msg': f'All set: your VOD uses track {vt}. Do check that your music is not on that track.'}

def phone_diag():
    ip = lan_ip(); out = {'ip': ip, 'url': phone_url() if SET.get('phone') else '', 'on': bool(SET.get('phone')), 'running': bool(PHONE.get('srv')),
                          'seen': round(time.time() - PHONE['seen']) if PHONE.get('seen') else None, 'tips': []}
    t = out['tips']
    if not out['on']: t.append('Phone access is off. Turn it on first.')
    if ip.startswith('127.'): t.append('Your PC is not on a network. Turn on wifi or plug in your cable.')
    if os.name == 'nt':
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-NetConnectionProfile | Select-Object -First 1).NetworkCategory'], capture_output=True, text=True, timeout=8, creationflags=NOWIN)
            cat = r.stdout.strip(); out['network'] = cat
            if cat.lower() == 'public':
                t.append('Windows sees your wifi as a Public network and then blocks your phone. Set it to Private: Settings > Network & internet > your wifi > Network profile type: Private.')
        except Exception: pass
    t.append('Your phone and PC need to be on the same wifi (not your phone data, and not a guest network).')
    t.append('At school, in a hotel or on guest wifi, devices often cannot see each other. Turn on your phone hotspot and connect your PC to it. Then scan the new QR code.')
    return out
class PhoneH(BaseHTTPRequestHandler):
    """only your shorts, only with the secret key from the QR code"""
    def log_message(self, *a): pass
    j = None; file = None
    def do_GET(self):
        try:
            u = urlparse(self.path); q = parse_qs(u.query)
            try:
                import ipaddress
                if not ipaddress.ip_address(self.client_address[0]).is_private: return H.j(self, {'error': 'only on your own wifi'}, 403)
            except ValueError: return H.j(self, {'error': 'no access'}, 403)
            if q.get('k', [''])[0] != SET.get('phone_key') or not SET.get('phone_key'): return H.j(self, {'error': 'no access'}, 403)
            PHONE['seen'] = time.time()
            if time.time() - (SET.get('phone_used') or 0) > 3600: SET['phone_used'] = time.time(); save_settings(SET)
            if u.path == '/m/manifest.json':
                return H.j(self, {'name': 'JelE Clipper', 'short_name': 'Clipper', 'start_url': '/m?k=' + SET.get('phone_key', ''), 'display': 'standalone', 'background_color': '#080b12', 'theme_color': '#0b0f18',
                                  'icons': [{'src': '/m/icon.png?k=' + SET.get('phone_key', ''), 'sizes': '512x512', 'type': 'image/png'}]})
            if u.path == '/m/icon.png':
                ip = os.path.join(DATA, 'app_icon.png')
                if not os.path.exists(ip):
                    from PIL import Image, ImageDraw
                    im = Image.new('RGB', (512, 512), (255, 146, 0)); d = ImageDraw.Draw(im); d.rounded_rectangle((96, 96, 416, 416), 70, fill=(17, 24, 39))
                    d.text((256, 256), 'J', fill=(255, 146, 0), font=font(260, 'caption'), anchor='mm'); im.save(ip)
                return H.file(self, ip, 'image/png')
            if u.path == '/m':
                b = PHONE_HTML.replace('__K__', SET.get('phone_key', '')).encode(); self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b); return
            if u.path == '/m/list':
                lib = lib_load(); fs = sorted(glob.glob(os.path.join(OUT, '*.mp4')), key=os.path.getmtime, reverse=True); out = []
                for f in fs:
                    e = lib.get(os.path.basename(f), {})
                    if e.get('test'): continue
                    out.append({'file': os.path.basename(f), 'at': os.path.getmtime(f), 'q': (e.get('q') or {}).get('score'), **{k: v for k, v in e.items() if k in ('title', 'status', 'post', 'views')}})
                return H.j(self, out)
            if u.path == '/m/v':
                fn = os.path.basename(q['f'][0]); return H.file(self, os.path.join(OUT, fn), 'video/mp4', fn if q.get('dl') else None)
            return H.j(self, {'error': 'not found'}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
    def do_POST(self):
        """keep, throw away, posted, views, title and hashtags: from your phone"""
        try:
            import ipaddress
            u = urlparse(self.path); q = parse_qs(u.query)
            if not ipaddress.ip_address(self.client_address[0]).is_private or q.get('k', [''])[0] != SET.get('phone_key') or not SET.get('phone_key'): return H.j(self, {'error': 'no access'}, 403)
            n = int(self.headers.get('Content-Length') or 0); b = json.loads(self.rfile.read(n) or b'{}') if n else {}
            fn = os.path.basename(b.get('file', '')); lib = lib_load(); e = lib.get(fn)
            if u.path != '/m/act' or not e: return H.j(self, {'error': 'not found'}, 404)
            a = b.get('action')
            if a == 'keep':
                if e.get('status') == 'nieuw': taste_note(e.get('reasons'), True, e.get('dur'))
                e['status'] = 'goed'; lib_save(lib)
            elif a == 'gone':
                if e.get('status') == 'nieuw': taste_note(e.get('reasons'), False, e.get('dur'))
                trash_short(fn)
            elif a == 'posted': short_mark_posted(e, b.get('platform') or 'all', True); lib_save(lib)
            elif a == 'unposted': short_mark_posted(e, b.get('platform') or 'all', False); lib_save(lib)
            elif a == 'views': e['views'] = int(b.get('views') or 0); lib_save(lib)
            elif a == 'meta':
                p_ = e.setdefault('post', {})
                if 'title' in b: p_['title'] = str(b['title'])[:120]
                if 'hashtags' in b: p_['hashtags'] = str(b['hashtags'])[:300]
                lib_save(lib)
            return H.j(self, {'ok': True})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        except Exception: traceback.print_exc(); return H.j(self, {'error': 'fout'}, 500)
def phone_start():
    if PHONE['srv']: return
    try:
        srv = ThreadingHTTPServer(('0.0.0.0', PORT + 1), PhoneH); PHONE['srv'] = srv
        threading.Thread(target=srv.serve_forever, daemon=True).start(); log('Phone access on:', phone_url())
    except OSError as e: log('Phone access failed:', e)
def phone_stop():
    if PHONE['srv']:
        try: PHONE['srv'].shutdown(); PHONE['srv'].server_close()
        except Exception: pass
        PHONE['srv'] = None; log('Phone access off')

def week_stats():
    since = time.time() - 7 * 86400
    ss = [x for x in list_sess() if (x.get('start') or 0) >= since and x.get('kind') != 'live']
    lib = lib_load(); items = [e for e in lib.values() if (e.get('at') or 0) >= since and not e.get('test') and not e.get('deleted_at')]
    kept = [e for e in items if e.get('status') in ('goed', 'gepland', 'gepost')]
    posted = [e for f_, e in lib.items() if e.get('status') == 'gepost' and (e.get('posted_at') or 0) >= since and not e.get('test')]
    keys = collections.Counter(k for e in kept for k in reason_keys(e.get('reasons')))
    names = {'marker': 'Clip button', 'chat': 'chat going off', 'audio': 'loud moments', 'say': 'what you say', 'laugh': 'laughing', 'game': 'multikills and clutches', 'tclip': 'Twitch clips'}
    best = max((dict(e, file=f) for f, e in lib.items() if (e.get('at') or 0) >= since and e.get('views')), key=lambda e: e['views'], default=None)
    return {'streams': len(ss), 'moments': sum(x['n_moments'] for x in ss), 'shorts': len(items), 'kept': len(kept), 'posted': len(posted),
            'views': sum(e.get('views') or 0 for e in items), 'best_kind': names.get(keys.most_common(1)[0][0]) if keys else None,
            'best': {'file': best['file'], 'title': best.get('title'), 'views': best['views']} if best else None, 'sids': [x['id'] for x in ss]}

def montage_parts(sids, n=5, seg=8.0):
    """the best moments of these streams, each cut short around its peak"""
    ms = []
    for sid in sids:
        try: ss = load_sess(sid)
        except Exception: continue
        if not ss.get('path'): continue
        for m in ss.get('moments', []): ms.append((m.get('score', 0), sid, m))
    ms.sort(key=lambda x: -x[0]); parts = []
    for sc, sid, m in ms[:n]:
        g = m.get('game'); pk = g['t'] if g else m['t']
        a = max(m['start'], pk - seg * 0.65); b = min(m['end'], a + seg)
        if g: a = max(0, min(a, g['t0'] - 1.5)); b = max(b, g['t'] + 1.5)
        parts.append({'sid': sid, 'a': round(a, 2), 'b': round(b, 2), 'mid': m['id']})
    parts.sort(key=lambda p: (p['sid'], p['a']))
    return parts

def highlight_parts(sid, minutes=8):
    """a summary of the stream: the best plays plus the funniest talk moments, in order, about `minutes` long"""
    s = load_sess(sid); target = minutes * 60; items = []
    for m in s.get('moments', []): items.append((m.get('score', 0) + 5, m['start'], m['end'], m.get('title') or ''))
    for t_ in s.get('talk', []): items.append((t_['score'] * 2, t_['a'], t_['b'], 'Praatmoment'))
    items.sort(key=lambda x: -x[0]); chosen = []; total = 0.0
    for sc_, a, b, lab in items:
        if total >= target: break
        if any(min(b, cb) - max(a, ca) > 3 for _, ca, cb, _l in chosen): continue
        chosen.append((sc_, a, b, lab)); total += b - a
    chosen.sort(key=lambda x: x[1])
    return [{'sid': sid, 'a': round(a, 2), 'b': round(b, 2), 'label': (lab or 'Moment')[:30]} for _, a, b, lab in chosen]

def make_thumbnail(file=None, sid=None, t=None, text='', kind='yt'):
    """a cover picture: a frame of the moment, big text, your orange style. kind yt = 1280x720, cover = 1080x1920"""
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
    lib = lib_load(); e = lib.get(os.path.basename(file)) if file else None
    if e: sid = sid or e.get('sid'); t = t if t is not None else (e.get('cover_t') or (e.get('start', 0) + e.get('end', 0)) / 2); text = text or e.get('title') or ''
    ss = load_sess(sid); W, H = (1280, 720) if kind == 'yt' else (1080, 1920)
    d_ = os.path.join(OUT, 'thumbnails'); os.makedirs(d_, exist_ok=True)
    fr = os.path.join(d_, '_frame.jpg'); run(['-y', '-ss', f'{float(t or 0):.2f}', '-i', ss['path'], '-frames:v', '1', '-q:v', '2', fr])
    im = Image.open(fr).convert('RGB')
    sc_ = max(W / im.width, H / im.height); im = im.resize((int(im.width * sc_), int(im.height * sc_)), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.35)).enhance(1.12).convert('RGBA')
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for x in range(W):   # dark on the text side
        a = int(200 * max(0, 1 - x / (W * 0.62))) if kind == 'yt' else 0
        d.line([(x, 0), (x, H)], fill=(10, 14, 22, a))
    if kind != 'yt':
        for y in range(H): d.line([(0, y), (W, y)], fill=(10, 14, 22, int(210 * max(0, (y - H * 0.55) / (H * 0.45)))))
    im.alpha_composite(ov); d = ImageDraw.Draw(im)
    words = (text or 'INSANE').upper().split(); lines = ['']
    size = 150 if kind == 'yt' else 170; f = font(size); maxw = W * (0.58 if kind == 'yt' else 0.86)
    for w in words:
        tt = (lines[-1] + ' ' + w).strip()
        if d.textlength(tt, font=f) <= maxw or not lines[-1]: lines[-1] = tt
        else: lines.append(w)
    while len(lines) > 3 and size > 70:
        size -= 14; f = font(size); lines = ['']
        for w in words:
            tt = (lines[-1] + ' ' + w).strip()
            if d.textlength(tt, font=f) <= maxw or not lines[-1]: lines[-1] = tt
            else: lines.append(w)
    lh = size * 0.98; y0 = (H - lh * len(lines)) / 2 if kind == 'yt' else H * 0.66
    for i_, l in enumerate(lines[:3]):
        col = BC() if i_ == len(lines[:3]) - 1 else (255, 255, 255, 255)
        d.text((60, y0 + i_ * lh), l, font=f, fill=col, stroke_width=8, stroke_fill=BI())
    d.rectangle((0, H - 14, W, H), fill=BC())
    tag = (SET.get('tag') or default_tag()); f2 = font(38, 'tag'); tw = d.textlength(tag, font=f2)
    if tag: d.rounded_rectangle((W - tw - 90, 30, W - 30, 92), radius=31, fill=BI(230)); d.text((W - 60 - tw / 2, 61), tag, font=f2, fill=(255, 255, 255, 255), anchor='mm')
    name = re.sub(r'[^\w-]+', '_', (os.path.splitext(os.path.basename(file))[0] if file else ss['title'] + '_' + fmt(t or 0))).strip('_')[:60] + ('' if kind == 'yt' else '_cover') + '.png'
    out = os.path.join(d_, name); im.convert('RGB').save(out, quality=95)
    try: os.remove(fr)
    except OSError: pass
    return out

def planner():
    """posting plan: on the chosen time you get a push message with the text ready to paste"""
    while True:
        try:
            lib = lib_load(); now = time.time(); ch = False
            if SET.get('auto_plan') and SET.get('post_slots'):   # the plan fills itself with shorts that are ready
                try:
                    n_ = plan_fill(lib)
                    if n_: ch = True; log(f'Posting plan: {n_} short(s) planned in your time slots')
                except Exception: traceback.print_exc()
            for fn, e in lib.items():
                if e.get('plan_at') and not e.get('plan_done') and e['plan_at'] <= now:
                    p_ = e.get('post') or {}
                    sent = notify(f"Time to post: {e.get('title') or fn}", f"{p_.get('title', '')}\n\n{p_.get('hashtags', '')}", 'calendar', 'f=' + urllib.parse.quote(fn))
                    e['plan_done'] = True; ch = True; log('Planning:', fn, 'notification sent' if sent else '(notifications are off)')
            if ch: lib_save(lib)
        except Exception: traceback.print_exc()
        time.sleep(30)

def storage_info():
    out = []; total = 0
    for x in list_sess():
        ss = load_sess(x['id']); p_ = ss.get('path'); size = os.path.getsize(p_) if p_ and os.path.exists(p_) else 0; total += size
        out.append({'id': x['id'], 'title': x['title'], 'start': x.get('start'), 'size': size, 'exists': bool(size), 'path': p_ or '', 'n_shorts': len(ss.get('shorts', [])),
                    'n_moments': len(ss.get('moments', [])), 'imported': bool(p_ and os.path.abspath(p_).startswith(os.path.abspath(IMPORTS)))})
    try: du = shutil.disk_usage(OUT); free = du.free
    except Exception: free = 0
    shorts = sum(os.path.getsize(f) for f in glob.glob(os.path.join(OUT, '*.mp4')))
    return {'items': out, 'total': total, 'free': free, 'shorts': shorts}

def recycle(path):
    """to the Windows recycle bin (you can still get it back), never straight away"""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [('hwnd', wintypes.HWND), ('wFunc', wintypes.UINT), ('pFrom', wintypes.LPCWSTR), ('pTo', wintypes.LPCWSTR),
                        ('fFlags', ctypes.c_uint16), ('fAnyOperationsAborted', wintypes.BOOL), ('hNameMappings', ctypes.c_void_p), ('lpszProgressTitle', wintypes.LPCWSTR)]
        op = SHFILEOPSTRUCTW(None, 3, path + '\0', None, 0x0040 | 0x0010 | 0x0004 | 0x0400, False, None, None)   # delete, allow undo, no confirm, silent
        return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0
    trash = os.path.join(DATA, 'prullenbak'); os.makedirs(trash, exist_ok=True); shutil.move(path, os.path.join(trash, os.path.basename(path))); return True

IMPORTS = os.path.join(DATA, 'imports'); os.makedirs(IMPORTS, exist_ok=True)
VIDEO_EXT = ('.mp4', '.mkv', '.mov', '.flv', '.webm', '.ts', '.m4v')
def import_file(path, title=None):
    s = new_session(title=title or os.path.splitext(os.path.basename(path))[0], path=path, start=os.path.getmtime(path))
    JOBS.put(('analyse', s['id'])); return s['id']

def download_url(arg):
    """a Twitch VOD / clip, a Medal clip or a YouTube video as a source (yt-dlp), optionally only a part of it"""
    url = arg['url']; prog('Fetching the video', 1)
    try: import yt_dlp
    except Exception: log('yt-dlp is missing. Restart the clipper and it installs it.'); return
    out_t = os.path.join(IMPORTS, '%(title).80B [%(id)s].%(ext)s'); info = {}
    def hook(d):
        if STATE.get('cancel'): raise yt_dlp.utils.DownloadError('stopped')
        if d.get('status') == 'downloading':
            tot = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            if tot: prog(f"Downloading ({d.get('_speed_str', '').strip()})", 2 + 90 * d.get('downloaded_bytes', 0) / tot)
    opts = {'outtmpl': out_t, 'format': 'bv*[height<=1080]+ba/b[height<=1080]/b', 'merge_output_format': 'mp4', 'ffmpeg_location': FF if os.path.isabs(FF) else None,
            'progress_hooks': [hook], 'quiet': True, 'no_warnings': True, 'noplaylist': True}
    a, b = arg.get('a'), arg.get('b')
    if a is not None or b is not None:
        from yt_dlp.utils import download_range_func
        opts['download_ranges'] = download_range_func(None, [(float(a or 0), float(b) if b else float('inf'))]); opts['force_keyframes_at_cuts'] = True
    try:
        with yt_dlp.YoutubeDL({k: v for k, v in opts.items() if v is not None}) as y:
            info = y.extract_info(url, download=True); fn = y.prepare_filename(info)
            if not os.path.exists(fn): fn = os.path.splitext(fn)[0] + '.mp4'
    except Exception as e:
        log('Download failed:', str(e)[:200]); STATE['why'] = str(e)[:120]; return
    title = (info.get('title') or 'Video')[:80]
    sid = import_file(fn, title); s = load_sess(sid); s['source_url'] = url; save_sess(s)
    log('Video in:', title); notify('Video in', f'{title} is in the clipper, finding the moments.')
