# JelE Clipper part: sessions and OBS. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- sessions
LOCK = threading.RLock()
CUR = {'id': None}   # the session that is being recorded right now
SESS_START = {}

def sdir(sid): return os.path.join(SESS, os.path.basename(str(sid)))
def load_sess(sid):
    with LOCK:
        return json.load(open(os.path.join(sdir(sid), 'sessie.json'), encoding='utf-8'))
def save_sess(s):
    with LOCK:
        os.makedirs(sdir(s['id']), exist_ok=True)
        tmp = os.path.join(sdir(s['id']), 'sessie.json.tmp')
        json.dump(s, open(tmp, 'w', encoding='utf-8'))
        os.replace(tmp, os.path.join(sdir(s['id']), 'sessie.json'))
def load_chat(sid):
    out = []
    try:
        for line in open(os.path.join(sdir(sid), 'chat.jsonl'), encoding='utf-8'):
            try: out.append(json.loads(line))
            except Exception: pass
    except FileNotFoundError: pass
    return out
def list_sess():
    out = []
    try: lib = lib_load()
    except Exception: lib = {}
    per = {}
    for fn, e in lib.items():   # real shorts only: no test renders, nothing in the recycle bin, file still there
        if e.get('sid') and not e.get('test') and not e.get('deleted_at') and os.path.exists(os.path.join(OUT, fn)): per[e['sid']] = per.get(e['sid'], 0) + 1
    for f in glob.glob(os.path.join(SESS, '*', 'sessie.json')):
        try:
            s = json.load(open(f, encoding='utf-8'))
            out.append({k: s.get(k) for k in ('id', 'title', 'start', 'stop', 'path', 'status', 'duration', 'kind', 'parent', 'imported', 'mic')} | {'game': game_quick(s)['id'], 'n_markers': len(s.get('markers', [])),  'n_moments': len(s.get('moments', [])), 'n_shorts': per.get(s.get('id'), 0), 'top': (s.get('moments') or [{}])[0].get('id')})
        except Exception: pass
    return sorted(out, key=lambda x: x.get('start') or 0, reverse=True)

def new_session(title=None, path=None, start=None):
    sid = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]
    s = {'id': sid, 'title': title or time.strftime('Stream %d-%m-%Y %H:%M'), 'start': start or time.time(), 'stop': None, 'path': path,
         'markers': [], 'status': 'opnemen' if not path else 'wachten', 'moments': [], 'shorts': []}
    save_sess(s); return s

def add_marker(source='knop', note='', length=None):
    if scene_blocked():   # 6.2: no clips from "Starting soon", "BRB" and such
        log(f'Clip ignored: you are on the scene "{STATE.get("scene")}"')
        obs.broadcast({'jele': 'clip-ok', 'ok': False, 'why': 'scene'}); return False
    threading.Thread(target=live_clip, args=(note, length), daemon=True).start()
    sid = CUR['id']
    if not sid:
        log('Clip requested, but nothing is recording. Start recording in OBS.')
        obs.broadcast({'jele': 'clip-ok', 'ok': False, 'why': 'not recording'})
        return False
    s = load_sess(sid); t = time.time() - s['start']
    s['markers'].append({'t': round(t, 2), 'src': source, 'note': note}); save_sess(s)
    log(f'Clip marked at {fmt(t)} ({source})')
    obs.broadcast({'jele': 'clip-ok', 'ok': True, 't': t})
    return True

def fmt(t):
    t = int(max(0, t)); return f'{t//3600}:{t//60%60:02d}:{t%60:02d}' if t >= 3600 else f'{t//60}:{t%60:02d}'

# ---------------------------------------------------------------- OBS websocket
class OBS:
    def __init__(self):
        self.ws = None; self.rid = 0; self.pending = {}; self.ok = False; self.marker_id = None
    def start(self): threading.Thread(target=self.loop, daemon=True).start()
    def loop(self):
        import websocket
        while True:
            try:
                self.ws = websocket.create_connection(f"ws://127.0.0.1:{CFG['OBS_PORT']}", timeout=10)
                self.ws.settimeout(None)
                self.handshake()
                while True:
                    self.on(json.loads(self.ws.recv()))
            except Exception as e:
                if self.ok: log('Lost the connection to OBS:', e)
                self.ok = False
                time.sleep(4)
    def handshake(self):
        hello = json.loads(self.ws.recv())
        d = {'rpcVersion': 1, 'eventSubscriptions': (1 << 0) | (1 << 2) | (1 << 6) | (1 << 7) | (1 << 19)}   # general, scenes, outputs, scene items, transform changes
        a = hello['d'].get('authentication')
        if a and not CFG.get('OBS_PASSWORD'):
            self.why = 'OBS asks for a password. Fill in the password from OBS > Tools > WebSocket Server Settings > Show Connect Info, or turn off "Enable Authentication" there'
            raise Exception(self.why)
        if a:
            sec = base64.b64encode(hashlib.sha256((CFG['OBS_PASSWORD'] + a['salt']).encode()).digest()).decode()
            d['authentication'] = base64.b64encode(hashlib.sha256((sec + a['challenge']).encode()).digest()).decode()
        self.ws.send(json.dumps({'op': 1, 'd': d}))
        msg = json.loads(self.ws.recv())
        if msg.get('op') != 2:
            self.why = 'OBS refused the password. Copy it again from OBS > Tools > WebSocket Server Settings > Show Connect Info'
            raise Exception(self.why)
        self.ok = True; self.why = ''; log('Connected to OBS' + ('' if a else ' (no password needed)'))
        threading.Thread(target=self.after_connect, daemon=True).start()
    def after_connect(self):
        r = self.req('GetRecordStatus')
        if r and r.get('outputActive') and not CUR['id']:
            dur = (r.get('outputDuration') or 0) / 1000
            s = new_session(start=time.time() - dur); CUR['id'] = s['id']
            log('A recording is already running, logging from now on')
        self.find_marker()
        obs_health_refresh()
        try: STATE['scene'] = (obs.req('GetCurrentProgramScene') or {}).get('currentProgramSceneName')
        except Exception: pass
    # where the cam frame sits, read from the scene in OBS. the frame is drawn at FRAME on the mascot game page
    FRAME = (0, 93, 613, 345)
    def walk(self, scene, tf, out, depth=0, group=False):
        r = self.req('GetGroupSceneItemList' if group else 'GetSceneItemList', {'sceneName': scene})
        for it in (r or {}).get('sceneItems', []):
            if not it.get('sceneItemEnabled', True): continue
            t = it.get('sceneItemTransform') or {}
            sw_ = t.get('sourceWidth') or 0; sx = (t.get('width') / sw_) if sw_ and t.get('width') else (t.get('scaleX') or 1)
            sh_ = t.get('sourceHeight') or 0; sy = (t.get('height') / sh_) if sh_ and t.get('height') else (t.get('scaleY') or 1)
            w, h = t.get('width') or 0, t.get('height') or 0; al = t.get('alignment', 5)
            x0 = (t.get('positionX') or 0) - (0 if al & 1 else w if al & 2 else w / 2)
            y0 = (t.get('positionY') or 0) - (0 if al & 4 else h if al & 8 else h / 2)
            cl, ct = t.get('cropLeft') or 0, t.get('cropTop') or 0
            # child coordinates (u, v) -> parent: x0 + (u - cl) * sx, then through the parent transform
            ntf = (lambda u, v, x0=x0, y0=y0, sx=sx, sy=sy, cl=cl, ct=ct: tf(x0 + (u - cl) * sx, y0 + (v - ct) * sy))
            if it.get('isGroup') and depth < 6: self.walk(it['sourceName'], ntf, out, depth + 1, True); continue
            if it.get('sourceType') == 'OBS_SOURCE_TYPE_SCENE' and depth < 6: self.walk(it['sourceName'], ntf, out, depth + 1); continue
            if it.get('inputKind') == 'browser_source':
                st = (self.req('GetInputSettings', {'inputName': it['sourceName']}) or {}).get('inputSettings', {})
                if 'mascotte_live_game' in (st.get('local_file') or '') or 'mascotte_live_game' in (st.get('url') or ''):
                    fx, fy, fw, fh = self.FRAME
                    a = ntf(fx, fy); b = ntf(fx + fw, fy + fh); out.append((a[0], a[1], b[0] - a[0], b[1] - a[1]))
    def detect_cam(self):
        """returns [x, y, w, h] of the cam frame on a 1920x1080 canvas, or None"""
        if not self.ok: return None
        try:
            vs = self.req('GetVideoSettings') or {}; k = 1920.0 / (vs.get('baseWidth') or 1920)
            prog_ = (self.req('GetCurrentProgramScene') or {}).get('currentProgramSceneName')
            scenes = [x['sceneName'] for x in (self.req('GetSceneList') or {}).get('scenes', [])]
            for sc in ([prog_] if prog_ else []) + [x for x in scenes if x != prog_]:
                out = []; self.walk(sc, lambda u, v: (u, v), out)
                if out:
                    x, y, w, h = out[0]
                    cam = [int(round(x * k)), int(round(y * k)), int(round(w * k)), int(round(h * k))]
                    if cam[2] > 40 and cam[3] > 30: return cam
        except Exception: traceback.print_exc()
        return None
    def find_marker(self):
        r = self.req('GetSceneItemList', {'sceneName': 'JelE Mascotte'})
        self.marker_id = None
        for it in (r or {}).get('sceneItems', []):
            if it['sourceName'] == 'Mascotte · clip': self.marker_id = it['sceneItemId']
    def send(self, type_, data=None):
        self.rid += 1; rid = f'c{self.rid}'
        try: self.ws.send(json.dumps({'op': 6, 'd': {'requestType': type_, 'requestId': rid, 'requestData': data or {}}}))
        except Exception: return None
        return rid
    def req(self, type_, data=None, timeout=5):
        ev = threading.Event(); box = {}
        rid = self.send(type_, data)
        if not rid: return None
        self.pending[rid] = (ev, box)
        ev.wait(timeout); self.pending.pop(rid, None)
        return box.get('d')
    def broadcast(self, data):
        if self.ok: self.send('BroadcastCustomEvent', {'eventData': data})
    def on(self, m):
        if m.get('op') == 7:
            p = self.pending.get(m['d']['requestId'])
            if p: p[1]['d'] = m['d'].get('responseData') or {}; p[0].set()
            return
        if m.get('op') != 5: return
        t = m['d']['eventType']; d = m['d'].get('eventData') or {}
        if t == 'RecordStateChanged':
            st = d.get('outputState')
            if st == 'OBS_WEBSOCKET_OUTPUT_STARTED':
                s = new_session(); CUR['id'] = s['id']; log('Recording started, logging along:', s['title'])
                if d.get('outputPath'): s['live_path'] = d['outputPath']; save_sess(s)   # for listening along during the stream
                threading.Thread(target=remember_cam, args=(s['id'],), daemon=True).start()
                threading.Thread(target=remember_game, args=(s['id'],), daemon=True).start()
            elif st == 'OBS_WEBSOCKET_OUTPUT_STOPPED' and CUR['id']:
                s = load_sess(CUR['id']); s['stop'] = time.time(); s['path'] = d.get('outputPath') or s.get('path'); s['status'] = 'wachten'; save_sess(s)
                log('Recording stopped:', s['path']); CUR['id'] = None
                if SET.get('remux', True) and (s.get('path') or '').lower().endswith('.mkv'): JOBS.put(('remux', s['id']))
                JOBS.put(('analyse', s['id']))
        elif t == 'ReplayBufferSaved':
            threading.Thread(target=live_saved, args=(d.get('savedReplayPath'),), daemon=True).start()
        elif t == 'CurrentProgramSceneChanged':
            STATE['scene'] = d.get('sceneName')
        elif t == 'StreamStateChanged':
            st = d.get('outputState')
            if st in ('OBS_WEBSOCKET_OUTPUT_STARTED', 'OBS_WEBSOCKET_OUTPUT_STOPPED'): on_stream_state(st == 'OBS_WEBSOCKET_OUTPUT_STARTED')
        elif t in ('SceneItemTransformChanged', 'CurrentProgramSceneChanged') and CUR['id'] and SET.get('cam_auto', True):
            cam_moved()
        elif t == 'CustomEvent':
            if d.get('jele') == 'clip': threading.Thread(target=add_marker, args=('paneel',), daemon=True).start()
            if d.get('jele') == 'clipper-ping': self.broadcast({'jele': 'clipper-pong', 'rec': bool(CUR['id'])})
        elif t == 'SceneItemEnableStateChanged' and d.get('sceneName') == 'JelE Mascotte':
            if self.marker_id is None: self.find_marker()
            if d.get('sceneItemId') == self.marker_id and d.get('sceneItemEnabled'):
                threading.Thread(target=add_marker, args=('sneltoets',), daemon=True).start()
                self.send('SetSceneItemEnabled', {'sceneName': 'JelE Mascotte', 'sceneItemId': self.marker_id, 'sceneItemEnabled': False})
obs = OBS()


# ---------------------------------------------------------------- 7.0: set up OBS for you (only after you click the button)
MIC_KINDS = ('wasapi_input_capture', 'coreaudio_input_capture', 'pulse_input_capture', 'alsa_input_capture')
def _pp(cat, name):
    return (obs.req('GetProfileParameter', {'parameterCategory': cat, 'parameterName': name}) or {}).get('parameterValue')
def obs_auto_setup():
    """your mic on audio track 2 (and 1), the rest off track 2, recording with tracks 1 and 2, as MKV.
    then the captions only listen to track 2: your voice, no game, no music, no Discord"""
    if not obs.ok: return {'ok': False, 'why': 'OBS is not connected. Start OBS and fill in your OBS password first.'}
    if (obs.req('GetRecordStatus') or {}).get('outputActive'): return {'ok': False, 'why': 'You are recording now. Stop the recording first, OBS does not allow these changes while it records.'}
    sp = obs.req('GetSpecialInputs') or {}
    inputs = (obs.req('GetInputList') or {}).get('inputs') or []
    mics = [sp[k] for k in ('mic1', 'mic2', 'mic3', 'mic4') if sp.get(k)]
    mics += [i['inputName'] for i in inputs if i.get('inputKind') in MIC_KINDS and i['inputName'] not in mics]
    if not mics: return {'ok': False, 'why': 'I found no mic in OBS. Add your mic in OBS (Settings > Audio > Mic/Auxiliary Audio) and try again.'}
    changes, notes = [], []
    names = list(dict.fromkeys(mics + [sp[k] for k in ('desktop1', 'desktop2') if sp.get(k)] + [i['inputName'] for i in inputs]))
    for n in names:
        tr = (obs.req('GetInputAudioTracks', {'inputName': n}) or {}).get('inputAudioTracks')
        if not tr: continue   # no sound in this source
        want = dict(tr)
        if n in mics: want['1'] = True; want['2'] = True
        else: want['2'] = False
        if want != tr:
            obs.req('SetInputAudioTracks', {'inputName': n, 'inputAudioTracks': want})
            changes.append(f'"{n}": on tracks 1 and 2' if n in mics else f'"{n}": off track 2 (track 2 is only for your mic)')
    mode = _pp('Output', 'Mode') or 'Simple'
    cat = 'AdvOut' if mode == 'Advanced' else 'SimpleOutput'
    if cat == 'SimpleOutput' and (_pp('SimpleOutput', 'RecQuality') or 'Stream') == 'Stream':
        notes.append('In OBS, Settings > Output > Recording: set "Recording Quality" to "High Quality" (not "Same as stream"), then click this button again. Only then can OBS record your mic on its own track.')
    else:
        try: cur = int(_pp(cat, 'RecTracks') or 1)
        except ValueError: cur = 1
        if cur & 3 != 3:
            obs.req('SetProfileParameter', {'parameterCategory': cat, 'parameterName': 'RecTracks', 'parameterValue': str(cur | 3)})
            changes.append('Recording: audio tracks 1 and 2 on')
    fk = 'RecFormat2' if _pp(cat, 'RecFormat2') else 'RecFormat'
    if (_pp(cat, fk) or '').lower() in ('mp4', 'mov', 'flv'):
        obs.req('SetProfileParameter', {'parameterCategory': cat, 'parameterName': fk, 'parameterValue': 'mkv'})
        changes.append('Recording format: MKV (does not break when your pc crashes, I turn it into MP4 myself)')
    if not notes:
        SET['mic_track'] = 2; save_settings(SET)
        changes.append('Clipper: captions only listen to track 2 (your mic)')
        if any(c.startswith('Recording') for c in changes): notes.append('Restart OBS once, so it uses the new recording settings.')
    log('OBS set up: ' + ('; '.join(changes) or 'everything was already right'))
    return {'ok': True, 'changes': changes, 'notes': notes, 'mics': mics}

_CAMT = {'h': None}
def cam_moved():
    """you moved or resized something in OBS: check the cam frame again (once things are still for 2 s)"""
    if _CAMT['h']: _CAMT['h'].cancel()
    def go():
        sid = CUR['id']
        if not sid: return
        cam = obs.detect_cam()
        if not cam: return
        s = load_sess(sid); cams = s.setdefault('cams', []); last = cams[-1][1] if cams else s.get('cam')
        if cam != last:
            cams.append([round(time.time() - s['start'], 1), cam]); s['cam'] = s.get('cam') or cam; save_sess(s); log('Cam frame moved, remembering it:', cam)
    _CAMT['h'] = threading.Timer(2.0, go); _CAMT['h'].daemon = True; _CAMT['h'].start()

def remember_cam(sid):
    """store where the cam frame is in this recording, so the crop is always right, even after you move it"""
    if not SET.get('cam_auto', True): return
    cam = obs.detect_cam()
    if cam:
        s = load_sess(sid); s['cam'] = cam; save_sess(s); log('Cam frame found in OBS:', cam)
