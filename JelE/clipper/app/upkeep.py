# JelE Clipper part: remux, updates, backup, error report, self test, guard, keys, phone. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- 6.0: MKV to MP4, light work copies
LOWPRIO = 0x00004000 if os.name == 'nt' else 0   # BELOW_NORMAL_PRIORITY_CLASS: never slows your game down

def remux(sid):
    """OBS records MKV (survives a crash). Afterwards it becomes an MP4 without re-encoding: seconds, no quality loss"""
    s = load_sess(sid); src = s.get('path') or ''
    if not src.lower().endswith('.mkv') or not os.path.exists(src): return True
    dst = os.path.splitext(src)[0] + '.mp4'
    prog('Converting the recording to MP4', 5)
    if os.path.exists(dst):   # OBS' own remux made it already: wait until it is finished
        last = -1
        for _ in range(60):
            sz = os.path.getsize(dst)
            if sz == last: break
            last = sz; time.sleep(2)
    else:
        tmp = dst + '.tmp.mp4'
        r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-map', '0', '-c', 'copy', '-movflags', '+faststart', tmp], capture_output=True, text=True, errors='replace', creationflags=NOWIN | LOWPRIO)
        if r.returncode != 0 or not os.path.exists(tmp):
            log('Converting to MP4 failed, just working with the MKV:', (r.stderr or '')[-200:])
            try: os.remove(tmp)
            except OSError: pass
            return True
        os.replace(tmp, dst)
    d1, d2 = probe_duration(src), probe_duration(dst)
    if d2 < max(1, d1 - 2):
        log('The MP4 is shorter than the recording, keeping the MKV'); return True
    s = load_sess(sid); s['path'] = dst; s['mkv'] = src; s['duration'] = s.get('duration') or d2; save_sess(s)
    log('Recording converted to MP4:', dst)
    if SET.get('remux_drop_mkv', True):
        if recycle(src): log('The MKV is in the recycle bin (you can still get it back)')
    prog('Done', 100); return True

def proxy_path(sid): return os.path.join(sdir(sid), 'werkkopie.mp4')
def proxy_enc():
    name = encoder_args()[1]
    return {'h264_nvenc': ['-c:v', 'h264_nvenc', '-preset', 'p2', '-cq', '27'],
            'h264_amf': ['-c:v', 'h264_amf', '-usage', 'transcoding', '-quality', 'speed', '-rc', 'cqp', '-qp_i', '25', '-qp_p', '27', '-qp_b', '29'],
            'h264_qsv': ['-c:v', 'h264_qsv', '-preset', 'veryfast', '-global_quality', '27']}.get(name, ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-threads', str(max(2, CORES // 2))])
def make_proxy(sid):
    """a light 720p copy to scrub through in the editor; the real recording is only used for the export"""
    s = load_sess(sid); src = s.get('path')
    out = proxy_path(sid)
    if not src or not os.path.exists(src) or os.path.exists(out): return
    tmp = out + '.tmp.mp4'; t0 = time.time()
    base = ['-y', '-i', src, '-map', '0:v:0', '-map', '0:a:0?', '-vf', 'scale=-2:720,fps=30', '-g', '15', '-pix_fmt', 'yuv420p']
    tail = ['-c:a', 'aac', '-b:a', '128k', '-ac', '2', '-movflags', '+faststart', tmp]
    for enc in (proxy_enc(), ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-threads', str(max(2, CORES // 2))]):
        r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error'] + base + enc + tail, capture_output=True, text=True, errors='replace', creationflags=NOWIN | LOWPRIO)
        if r.returncode == 0 and os.path.exists(tmp): break
    if os.path.exists(tmp) and probe_duration(tmp) > (s.get('duration') or 0) - 3:
        os.replace(tmp, out); s = load_sess(sid); s['proxy'] = True; save_sess(s)
        log(f'Working copy ready in {time.time() - t0:.0f} sec: the editor jumps faster now')
    else:
        try: os.remove(tmp)
        except OSError: pass

PROXYQ = queue.Queue(); PROXY_ASKED = set()
def proxy_loop():
    while True:
        sid = PROXYQ.get()
        while paused(): time.sleep(5)
        try: make_proxy(sid)
        except Exception: traceback.print_exc()

# ---------------------------------------------------------------- 6.0: updates (GitHub), going back, self repair
CHANGELOG_F = os.path.join(HERE, 'CHANGELOG.md')
def changelog():
    """CHANGELOG.md read into [{version, date, groups: [{name, items}]}], newest first"""
    out = []
    try: lines = open(CHANGELOG_F, encoding='utf-8').read().splitlines()
    except Exception: return out
    for ln in lines:
        m = re.match(r'^##\s+([\d.]+)\s*(?:[·-]\s*(.+))?$', ln.strip())
        if m: out.append({'version': m.group(1), 'date': (m.group(2) or '').strip(), 'groups': []}); continue
        if not out: continue
        m = re.match(r'^###\s+(.+)$', ln.strip())
        if m: out[-1]['groups'].append({'name': m.group(1).strip(), 'items': []}); continue
        m = re.match(r'^[-*]\s+(.+)$', ln.strip())
        if m:
            if not out[-1]['groups']: out[-1]['groups'].append({'name': 'New', 'items': []})
            out[-1]['groups'][-1]['items'].append(m.group(1).strip())
    return out
def changes_for(version):
    v = next((x for x in changelog() if x['version'] == version), None)
    return [it for g in v['groups'] for it in g['items']] if v else []
VERS_DIR = os.path.join(DATA, 'versies'); os.makedirs(VERS_DIR, exist_ok=True)
UPD_PENDING = os.path.join(DATA, 'update_pending.json'); HERSTELD = os.path.join(DATA, 'hersteld.json')
UPD = {'checked': 0, 'info': None, 'error': None, 'busy': False}
SAFE = {'on': '--veilig' in sys.argv or bool(SET.get('safe_mode'))}

def vtuple(v): return tuple(int(x) for x in re.findall(r'\d+', str(v or '0'))) or (0,)

def update_source():
    repo = (SET.get('update_repo') or '').strip()
    if repo:
        repo = re.sub(r'^(https?://)?(www\.)?github\.com/', '', repo).strip('/')
        repo = '/'.join(repo.split('/')[:2])
        if not re.match(r'^[\w.-]+/[\w.-]+$', repo): raise ValueError('Enter the repository as name/repo, for example jele/jele-clipper')
        try: r = http_json(f'https://api.github.com/repos/{repo}/releases/latest', headers={'Accept': 'application/vnd.github+json'})
        except urllib.error.HTTPError as e:
            if e.code == 404: raise ValueError(f'No release found on GitHub yet ({repo}). Is the repository public?')
            if e.code == 403: raise ValueError('GitHub is not allowing checks for a while. Try again in an hour.')
            raise
        asset = next((a for a in r.get('assets', []) if a.get('name', '').lower().endswith('.zip')), None)
        if not asset: raise ValueError('The newest release on GitHub has no zip')
        return {'version': (r.get('tag_name') or '').lstrip('vV'), 'notes': r.get('body') or '', 'url': asset['browser_download_url'], 'source': 'github'}
    if CFG.get('UPDATE_URL'):
        mf = http_json(CFG['UPDATE_URL']); return {'version': str(mf.get('version')), 'notes': mf.get('notes', ''), 'url': mf['url'], 'source': 'url'}
    return None

def update_check(force=False):
    if not force and time.time() - UPD['checked'] < 600: return UPD
    UPD['checked'] = time.time()
    try:
        info = update_source(); UPD['info'] = info; UPD['error'] = None
        UPD['newer'] = bool(info and vtuple(info['version']) > vtuple(VERSION))
    except Exception as e:
        UPD['info'] = None; UPD['newer'] = False
        UPD['error'] = str(e)[:160] if isinstance(e, ValueError) else friendly(str(e))
    return UPD

def update_loop():
    time.sleep(30)
    while True:
        if SET.get('update_repo') or CFG.get('UPDATE_URL'):
            u = update_check(True)
            if u.get('newer'): log(f"New version available: {u['info']['version']} (Settings > Updates)")
        time.sleep(6 * 3600)

def busy_reason():
    if CUR['id']: return 'A recording is running. Update after your stream.'
    if STATE.jobs() or any(not x.get('skip') for x in JOBS.pending): return 'Something is still being made. The update happens when the queue is empty.'
    return None

def install_update():
    """download the new version, keep a copy of the files it replaces, put it in place and restart"""
    why = busy_reason()
    if why: return {'ok': False, 'why': why}
    u = update_check(True)
    if not u.get('info'): return {'ok': False, 'why': u.get('error') or 'No update channel set'}
    info = u['info']
    if UPD['busy']: return {'ok': False, 'why': 'The update is already running'}
    UPD['busy'] = True
    try:
        import zipfile, io
        req = urllib.request.Request(info['url'], headers={'User-Agent': 'JelE-Clipper/' + VERSION})
        data = urllib.request.urlopen(req, timeout=180).read()
        z = zipfile.ZipFile(io.BytesIO(data))
        files = []
        for m in z.infolist():
            rel = m.filename.split('/', 1)[1] if m.filename.startswith('JelE/') else m.filename
            if not rel or m.is_dir() or '..' in rel or rel.startswith('/'): continue
            if os.path.basename(rel).lower() == 'config.js' or rel.replace('\\', '/').startswith('clipper/data/'): continue
            files.append((m, rel))
        if not any(rel.replace('\\', '/') == 'clipper/clipper.py' for _, rel in files): raise ValueError('This zip is not a JelE Clipper update')
        # 1: copy of everything this update changes, so you can always go back
        bk = os.path.join(VERS_DIR, f'v{VERSION}_{time.strftime("%Y%m%d_%H%M%S")}.zip'); added = []
        with zipfile.ZipFile(bk, 'w', zipfile.ZIP_DEFLATED) as bz:
            for _, rel in files:
                cur = os.path.join(ROOT, rel.replace('/', os.sep))
                if os.path.exists(cur): bz.write(cur, rel)
                else: added.append(rel)
            bz.writestr('_added.json', json.dumps(added)); bz.writestr('_info.json', json.dumps({'version': VERSION, 'at': time.time()}))
        olds = sorted(glob.glob(os.path.join(VERS_DIR, '*.zip')), key=os.path.getmtime)
        for f_ in olds[:-5]:
            try: os.remove(f_)
            except OSError: pass
        json.dump({'from': VERSION, 'to': info['version'], 'backup': bk, 'at': time.time()}, open(UPD_PENDING, 'w', encoding='utf-8'))
        # 2: the new files
        for m, rel in files:
            dst = os.path.join(ROOT, rel.replace('/', os.sep)); os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as fh: fh.write(z.read(m))
        log(f'Update to {info["version"]} installed ({len(files)} files). Restarting.')
        restart_app(); return {'ok': True, 'version': info['version']}
    except Exception as e:
        note_error('update', traceback.format_exc())
        return {'ok': False, 'why': str(e)[:160] if isinstance(e, ValueError) else friendly(str(e))}
    finally: UPD['busy'] = False

RESTART_CODE = 75   # the launcher (launcher.pyw) starts the Clipper again when it stops with this code
def restart_app(delay=1.5):
    def go():
        time.sleep(delay)
        if os.environ.get('JELE_LAUNCHER'): os._exit(RESTART_CODE)   # no new window: the launcher restarts it
        if os.name == 'nt': subprocess.Popen(['cmd', '/c', 'start', '', '/min', os.path.join(HERE, 'start.bat'), '--no-browser'], cwd=HERE)
        else: subprocess.Popen([sys.executable] + sys.argv, cwd=HERE)
        os._exit(0)
    threading.Thread(target=go, daemon=True).start()

def versions_list():
    out = []
    for f_ in sorted(glob.glob(os.path.join(VERS_DIR, '*.zip')), key=os.path.getmtime, reverse=True):
        m = re.match(r'v(.+?)_(\d{8}_\d{6})\.zip$', os.path.basename(f_))
        out.append({'file': os.path.basename(f_), 'version': m.group(1) if m else '?', 'at': os.path.getmtime(f_)})
    return out

def rollback(name=None):
    why = busy_reason()
    if why: return {'ok': False, 'why': why}
    vs = versions_list()
    if not vs: return {'ok': False, 'why': 'No previous version has been kept yet'}
    pick = next((v for v in vs if v['file'] == name), vs[0])
    try:
        import herstel
        n = herstel.restore(os.path.join(VERS_DIR, pick['file']), ROOT)
        json.dump({'from': VERSION, 'to': pick['version'], 'at': time.time(), 'files': n, 'manual': True}, open(HERSTELD, 'w', encoding='utf-8'))
        log(f'Back to version {pick["version"]} ({n} files). Restarting.')
        restart_app(); return {'ok': True, 'version': pick['version']}
    except Exception as e:
        note_error('restoring', traceback.format_exc()); return {'ok': False, 'why': friendly(str(e))}

def confirm_start():
    """the new version runs fine for 25 seconds: the update is accepted"""
    time.sleep(25)
    if os.path.exists(UPD_PENDING):
        try: os.remove(UPD_PENDING); log('New version runs fine')
        except OSError: pass

# ---------------------------------------------------------------- 6.0: daily back-up of what you built up
BACKUP_DIR = os.path.join(DATA, 'backups'); os.makedirs(BACKUP_DIR, exist_ok=True)
BACKUP_FILES = ('instellingen.json', 'bibliotheek.json', 'smaak.json', 'tempo.json', 'voorbeelden.json', 'aanpassingen.json', 'qgewichten.json')
def backup_now(tag=''):
    import zipfile
    name = os.path.join(BACKUP_DIR, f'backup_{time.strftime("%Y%m%d_%H%M%S")}{tag}.zip')
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as z:
        for f_ in BACKUP_FILES:
            p = os.path.join(DATA, f_)
            if os.path.exists(p): z.write(p, f_)
        if os.path.exists(VOICE_FILE): z.write(VOICE_FILE, 'voicelines.txt')
        for p in glob.glob(os.path.join(SESS, '*', 'sessie.json')):
            z.write(p, 'sessies/' + os.path.basename(os.path.dirname(p)) + '/sessie.json')
    fs = sorted(glob.glob(os.path.join(BACKUP_DIR, 'backup_*.zip')), key=os.path.getmtime)
    daily = [f_ for f_ in fs if not f_.endswith('_voor.zip')]
    for f_ in daily[:-14] + [f_ for f_ in fs if f_.endswith('_voor.zip')][:-3]:
        try: os.remove(f_)
        except OSError: pass
    return name
def backups_list():
    return [{'file': os.path.basename(f_), 'at': os.path.getmtime(f_), 'size': os.path.getsize(f_), 'before_restore': f_.endswith('_voor.zip')}
            for f_ in sorted(glob.glob(os.path.join(BACKUP_DIR, 'backup_*.zip')), key=os.path.getmtime, reverse=True)]
def backup_restore(name):
    import zipfile
    p = os.path.join(BACKUP_DIR, os.path.basename(name))
    if not os.path.exists(p): return {'ok': False, 'why': 'Backup not found'}
    backup_now('_voor')   # first a copy of how it is now, so restoring can be undone too
    with zipfile.ZipFile(p) as z:
        for m in z.infolist():
            if m.is_dir() or '..' in m.filename: continue
            if m.filename == 'voicelines.txt': dst = VOICE_FILE
            elif m.filename.startswith('sessies/'):
                dst = os.path.join(SESS, *m.filename.split('/')[1:])
                if not os.path.isdir(os.path.dirname(dst)): continue   # a stream you removed stays removed
            else: dst = os.path.join(DATA, os.path.basename(m.filename))
            with open(dst, 'wb') as fh: fh.write(z.read(m))
    SET.clear(); SET.update(load_settings())
    log('Backup restored:', name); return {'ok': True}
def backup_loop():
    time.sleep(60)
    while True:
        last = max([b['at'] for b in backups_list() if not b['before_restore']] or [0])
        if time.time() - last > 20 * 3600:
            try: backup_now(); log('Backup made of your settings, library and taste')
            except Exception: traceback.print_exc()
        time.sleep(3600)

# ---------------------------------------------------------------- 6.0: error report (never with secrets)
REPORT_DIR = os.path.join(DATA, 'rapporten'); os.makedirs(REPORT_DIR, exist_ok=True)
SECRET_KEYS = ('OBS_PASSWORD', 'SE_JWT', 'HENRIK_KEY', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET')
def scrub(txt):
    t = str(txt or '')
    vals = [CFG.get(k) for k in SECRET_KEYS] + [SET.get('phone_key'), SET.get('ntfy_topic')]
    for v in vals:
        if v and len(str(v)) >= 4: t = t.replace(str(v), '[secret]')
    t = re.sub(r'eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{4,}', '[secret]', t)                     # tokens
    t = re.sub(r'(?i)((?:password|secret|token|api[_-]?key|jwt|phone_key|ntfy_topic)["\']?\s*[:=]\s*["\']?)([^\s"\',}]{4,})', r'\1[secret]', t)
    t = re.sub(r'([?&]k=)[\w-]+', r'\1[secret]', t)
    return t
def make_report(note=''):
    import zipfile, platform
    name = os.path.join(REPORT_DIR, f'foutrapport_{time.strftime("%Y%m%d_%H%M%S")}.zip')
    sets = {k: v for k, v in SET.items() if k not in ('phone_key', 'ntfy_topic', 'presets')}
    try: checks = system_check()
    except Exception as e: checks = [{'name': 'systeemcheck', 'ok': False, 'info': str(e)}]
    job = STATE.get('job')
    head = [f'JelE Clipper {VERSION}', time.strftime('%Y-%m-%d %H:%M:%S'), f'{platform.platform()} · Python {platform.python_version()} · {CORES} cores',
            f'ffmpeg: {FF}', f'video encoder: {encoder_args()[1]}', f'safe mode: {SAFE["on"]}', f'OBS: {"connected" if obs.ok else "not connected"}',
            f'recording: {bool(CUR["id"])}', f'working on:{(job or {}).get("kind")} / {(job or {}).get("stage")}', '', 'What happened (filled in by you):', note or '-']
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('rapport.txt', scrub('\n'.join(head)))
        z.writestr('logboek.txt', scrub('\n'.join(LOGBUF)))
        z.writestr('fouten.json', scrub(json.dumps(list(ERRORS), indent=1)))
        z.writestr('instellingen.json', scrub(json.dumps(sets, indent=1)))
        z.writestr('systeemcheck.json', scrub(json.dumps(checks, indent=1)))
        z.writestr('zelftest.json', json.dumps(SELFTEST, indent=1))
        z.writestr('klaar.json', scrub(json.dumps(STATE.get('done', [])[-15:], indent=1)))
    log('Error report made:', os.path.basename(name)); return name

# ---------------------------------------------------------------- 6.0: self test at every start
SELFTEST = {'done': False, 'at': 0, 'items': []}
def selftest():
    items = []
    def add(name, ok, info, fix=''): items.append({'name': name, 'ok': ok, 'info': info, 'fix': fix})
    import tempfile
    tmp = tempfile.mkdtemp(prefix='jele_test_')
    try:
        out = os.path.join(tmp, 't.mp4')
        def trial():
            r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=1080x1920:r=60:d=2', '-f', 'lavfi', '-i', 'sine=f=440:d=2',
                                '-vf', 'format=yuv420p'] + encoder_args() + ['-c:a', 'aac', '-shortest', out], capture_output=True, text=True, errors='replace', creationflags=NOWIN)
            return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000
        name = encoder_args()[1]
        if trial(): add('Making the video', True, {'h264_nvenc': 'works with your NVIDIA card', 'h264_amf': 'works with your AMD card', 'h264_qsv': 'works with your Intel chip'}.get(name, 'works with your processor'))
        else:
            if name != 'libx264': _ENC[name] = False
            if name != 'libx264' and trial(): add('Making the video', True, f'your graphics card did not work, now using {encoder_args()[1]}', 'Update your AMD driver if you want to use the graphics card')
            else: add('Making the video', False, 'making a test video fails', 'Run install.bat again')
        # captions model can be loaded
        if whisper_ok(): add('Captions', True, 'speech recognition ready')
        else: add('Captions', False, 'speech recognition missing, shorts come without captions', 'Run install.bat again')
        try:
            free = shutil.disk_usage(OUT).free / 1e9
            add('Disk space', free > 10, f'{free:.0f} GB free', 'Free up space in System > Storage' if free <= 10 else '')
        except Exception: pass
        for _ in range(10):
            if obs.ok: break
            time.sleep(1)
        add('OBS', obs.ok, 'connected' if obs.ok else 'not connected', '' if obs.ok else 'Start OBS, and fill in your OBS password in Settings > Keys')
    except Exception: traceback.print_exc()
    finally: shutil.rmtree(tmp, ignore_errors=True)
    SELFTEST.update(done=True, at=time.time(), items=items)
    bad = [x['name'] for x in items if not x['ok']]
    log('Self-test: everything works' if not bad else 'Self-test: check ' + ', '.join(bad))

# ---------------------------------------------------------------- 6.0: recording guard and health
HEALTH = {'rate': None}
def bytes_per_sec():
    if HEALTH['rate'] and time.time() - HEALTH.get('rate_at', 0) < 3600: return HEALTH['rate']
    rs = []
    for x in list_sess()[:12]:
        p = x.get('path'); d = x.get('duration') or 0
        if p and d > 120 and os.path.exists(p): rs.append(os.path.getsize(p) / d)
    HEALTH['rate'] = sorted(rs)[len(rs) // 2] if rs else 1.2e6; HEALTH['rate_at'] = time.time()
    return HEALTH['rate']
def health():
    h = {'live': bool(STATE.get('live')), 'recording': bool(CUR['id']), 'obs': obs.ok, 'warn': []}
    try:
        rd = HEALTH.get('rec_dir') or OUT
        free = shutil.disk_usage(rd if os.path.isdir(rd) else OUT).free
        h['free_gb'] = round(free / 1e9, 1); h['hours_left'] = round(free / bytes_per_sec() / 3600, 1)
        if h['hours_left'] < 3: h['warn'].append({'k': 'disk', 'msg': f'Only room for about {h["hours_left"]:.1f} hours of recording left'})
    except Exception: pass
    if h['live'] and not h['recording']: h['warn'].append({'k': 'rec', 'msg': 'You are live, but recording is off'})
    try:
        if h['live'] and LIVE['drop'] is not None and LIVE['drop'] >= 2: h['warn'].append({'k': 'frames', 'msg': f'OBS is dropping {LIVE["drop"]:.1f}% of your frames'})
    except NameError: pass
    if HEALTH.get('rec_fmt') and HEALTH['rec_fmt'] not in ('mkv', 'hybrid_mp4', 'hybrid_mov'): h['tip_mkv'] = True
    return h
def obs_health_refresh():
    """reads stream state, record folder and format from OBS"""
    if not obs.ok: return
    try:
        st = obs.req('GetStreamStatus') or {}; STATE['live'] = bool(st.get('outputActive'))
        rd = (obs.req('GetRecordDirectory') or {}).get('recordDirectory'); HEALTH['rec_dir'] = rd
        prof = obs.req('GetProfileParameter', {'parameterCategory': 'SimpleOutput', 'parameterName': 'RecFormat2'}) or {}
        fmt_ = prof.get('parameterValue')
        if not fmt_:
            prof = obs.req('GetProfileParameter', {'parameterCategory': 'SimpleOutput', 'parameterName': 'RecFormat'}) or {}; fmt_ = prof.get('parameterValue')
        HEALTH['rec_fmt'] = (fmt_ or '').lower() or None
    except Exception: pass
def on_stream_state(active):
    STATE['live'] = bool(active)
    if active:
        STATE['run_live'] = False; STATE['stream_at'] = time.time(); STATE['summary'] = None
        if not CUR['id']:
            log('You are live, but recording is off! Click "Start recording" in the dock.')
            obs.broadcast({'jele': 'rec-warn'})
            notify('Recording is off', 'You are live, but OBS is not recording. No recording, no clips.', 'warning')
    else:
        log('Stream stopped'); STATE['summary'] = stream_summary()
        obs.broadcast({'jele': 'stream-summary', **STATE['summary']})

# ---------------------------------------------------------------- 6.0: keys in the app (stored only in config.js on this pc)
KEYS = [('OBS_PASSWORD', 'OBS password', 'OBS > Tools > WebSocket Server Settings > Show Connect Info'),
        ('HENRIK_KEY', 'HenrikDev API-key', 'For your Valorant matches (multikills, aces, clutches)'),
        ('CHANNEL', 'Twitch name', 'Your channel name, as in twitch.tv/name'),
        ('TEAM', 'Team name', 'Shown on your OBS scenes (can be empty)'),
        ('RIOT_NAME', 'Riot name', 'Your name in Valorant, without the #tag'),
        ('RIOT_TAG', 'Riot tag', 'What comes after the #'),
        ('REGION', 'Region', 'eu, na, ap or kr'),
        ('TWITCH_CLIENT_ID', 'Twitch Client ID', 'dev.twitch.tv > Your Console > your app'),
        ('TWITCH_CLIENT_SECRET', 'Twitch Client Secret', 'dev.twitch.tv > your app > New Secret')]
PUBLIC_KEYS = ('CHANNEL', 'TEAM', 'RIOT_NAME', 'RIOT_TAG', 'REGION')
CONFIG_JS = os.path.join(ROOT, 'mascotte', 'config.js')
def keys_info():
    out = []
    for k, label, help_ in KEYS:
        v = CFG.get(k) or ''
        e = {'key': k, 'label': label, 'help': help_, 'set': bool(v), 'secret': k not in PUBLIC_KEYS}
        if k in PUBLIC_KEYS: e['value'] = v
        out.append(e)
    tests = {'OBS_PASSWORD': obs.ok}
    for e in out:
        if e['key'] in tests: e['ok'] = tests[e['key']]
    return out
def keys_save(vals):
    allowed = {k for k, _, _ in KEYS}
    vals = {k: str(v).strip() for k, v in vals.items() if k in allowed and v is not None}
    if not vals: return {'ok': True}
    try: s = open(CONFIG_JS, encoding='utf-8').read()
    except FileNotFoundError:
        os.makedirs(os.path.dirname(CONFIG_JS), exist_ok=True); s = 'window.JELE_CONFIG = {\n};\n'
    for k, v in vals.items():
        v_js = v.replace('\\', '\\\\').replace('"', '\\"')
        pat = re.compile(r'(\b' + k + r'\s*:\s*)("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')')
        if pat.search(s): s = pat.sub(lambda m: m.group(1) + '"' + v_js + '"', s, count=1)
        else: s = re.sub(r'(window\.JELE_CONFIG\s*=\s*\{\s*\n)', lambda m: m.group(1) + f'  {k}: "{v_js}",\n', s, count=1)
    tmp = CONFIG_JS + '.tmp'; open(tmp, 'w', encoding='utf-8').write(s); os.replace(tmp, CONFIG_JS)
    old_pw = CFG.get('OBS_PASSWORD'); CFG.update(read_config_js())
    if 'OBS_PASSWORD' in vals and vals['OBS_PASSWORD'] != old_pw and obs.ws:
        try: obs.ws.close()   # reconnect with the new password
        except Exception: pass
    log('Keys saved in config.js:', ', '.join(sorted(vals)))
    return {'ok': True}
def recover_personal():
    """6.5: your channel, Riot name and team moved out of the overlay files into config.js.
    After an update, take them from the copy of the old files the updater kept, so nothing changes for you."""
    want = [k for k in ('CHANNEL', 'RIOT_NAME', 'RIOT_TAG', 'TEAM') if not CFG.get(k)]
    if not want: return
    import zipfile
    pats = {'CHANNEL': [r"CHANNEL\s*:\s*['\"]([^'\"]+)['\"]"], 'RIOT_NAME': [r"RIOT_NAME\s*:\s*['\"]([^'\"]+)['\"]", r"\bNAME\s*:\s*['\"]([^'\"]+)['\"]"],
            'RIOT_TAG': [r"RIOT_TAG\s*:\s*['\"]([^'\"]+)['\"]", r"\bTAG\s*:\s*['\"]([^'\"]+)['\"]"], 'TEAM': [r"TEAM\s*:\s*['\"]([^'\"]+)['\"]"]}
    found = {}
    for bk in sorted(glob.glob(os.path.join(VERS_DIR, '*.zip')), key=os.path.getmtime, reverse=True):
        try:
            with zipfile.ZipFile(bk) as z:
                for n in z.namelist():
                    if not n.endswith('.html') or not ('mascotte' in n or 'overlays' in n): continue
                    t = z.read(n).decode('utf-8', 'replace')
                    for k in want:
                        if k in found: continue
                        for pat in pats[k]:
                            m = re.search(pat, t)
                            if m and m.group(1).strip() and 'PLAK' not in m.group(1): found[k] = m.group(1).strip(); break
        except Exception: continue
        if len(found) == len(want): break
    if found:
        keys_save(found); log('Your channel and Valorant name are now in config.js:', ', '.join(sorted(found)))
def keys_test(k):
    try:
        if k == 'OBS_PASSWORD':
            for _ in range(8):
                if obs.ok: break
                time.sleep(1)
            return {'ok': obs.ok, 'msg': 'OBS is connected' if obs.ok else 'OBS refuses, or is not running'}
        if k in ('TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET'):
            if not (CFG.get('TWITCH_CLIENT_ID') and CFG.get('TWITCH_CLIENT_SECRET')): return {'ok': False, 'msg': 'Fill in both the Client ID and the Client Secret, then Save'}
            http_json('https://id.twitch.tv/oauth2/token', data=urllib.parse.urlencode({'client_id': CFG.get('TWITCH_CLIENT_ID', ''), 'client_secret': CFG.get('TWITCH_CLIENT_SECRET', ''), 'grant_type': 'client_credentials'}).encode())
            if not CFG.get('CHANNEL'): return {'ok': True, 'msg': 'Twitch accepts your app. Fill in your Twitch name too'}
            cat = twitch_category()
            return {'ok': True, 'msg': 'Twitch works: viewer clips count as moments' + (f', your category now is {cat}' if cat else '')}
        if k == 'HENRIK_KEY':
            name, tag = CFG.get('RIOT_NAME', ''), CFG.get('RIOT_TAG', '')
            if not (name and tag): return {'ok': False, 'msg': 'Fill in your Riot name and tag first'}
            http_json(f'https://api.henrikdev.xyz/valorant/v2/account/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}', headers={'Authorization': CFG.get('HENRIK_KEY', '')})
            return {'ok': True, 'msg': 'HenrikDev works and finds your account'}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'msg': {400: 'Not accepted: is the key right?', 401: 'Not accepted: is the key right?', 403: 'Not accepted: is the key right?', 404: 'Account not found: are your name and tag right?', 429: 'Too many tries, wait a minute'}.get(e.code, f'Error {e.code}')}
    except Exception as e: return {'ok': False, 'msg': friendly(str(e))}
    return {'ok': False, 'msg': 'There is no test for this'}

# ---------------------------------------------------------------- 6.0: phone access stays safe
def phone_guard_loop():
    while True:
        try:
            if SET.get('phone'):
                last = max(SET.get('phone_used') or 0, SET.get('phone_on_at') or 0)
                if last and time.time() - last > 7 * 86400:
                    SET['phone'] = False; save_settings(SET); phone_stop(); log('Phone access turned off: not used for a week')
        except Exception: pass
        time.sleep(3600)

# ---------------------------------------------------------------- 7.0: shortcuts with the JelE icon (no black window)
def make_shortcuts(force=False):
    """a "JelE Clipper" shortcut on your desktop and in the start menu. it opens the Clipper in its own window, without the black window"""
    if os.name != 'nt': return False
    if SET.get('shortcuts_made') and not force: return False
    if os.path.exists(os.path.join(HERE, 'python', 'pythonw.exe')): return False   # installed with the setup: it made the shortcuts
    pyw = os.path.join(HERE, '.venv', 'Scripts', 'pythonw.exe')
    if not os.path.exists(pyw): return False
    q = lambda x: x.replace("'", "''")   # PowerShell quoting
    pyw, tgt, ico, here = q(pyw), q(os.path.join(HERE, 'launcher.pyw')), q(os.path.join(HERE, 'jele.ico')), q(HERE)
    ps = ("$s = New-Object -ComObject WScript.Shell; "
          "foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { "
          "$l = $s.CreateShortcut((Join-Path $d 'JelE Clipper.lnk')); "
          f"$l.TargetPath = '{pyw}'; $l.Arguments = '\"{tgt}\"'; $l.WorkingDirectory = '{here}'; "
          f"$l.IconLocation = '{ico},0'; $l.Description = 'JelE Clipper'; $l.Save() }}")
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, text=True, timeout=30, creationflags=NOWIN)
        ok = r.returncode == 0
    except Exception: ok = False
    if ok:
        SET['shortcuts_made'] = True; save_settings(SET); log('Shortcut "JelE Clipper" put on your desktop and in the start menu')
    return ok
