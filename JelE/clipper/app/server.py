# JelE Clipper part: web UI and main(). Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- web UI
UI = os.path.join(HERE, 'ui.html')
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def j(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        n = int(self.headers.get('Content-Length') or 0); return json.loads(self.rfile.read(n) or b'{}')
    def file(self, p, ctype, dl=None):
        if not os.path.exists(p): return self.j({'error': 'not found'}, 404)
        size = os.path.getsize(p); rng = self.headers.get('Range')
        a, b = 0, size - 1
        if rng:
            m = re.match(r'bytes=(\d*)-(\d*)', rng)
            if m:
                a = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2))); b = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
            self.send_response(206); self.send_header('Content-Range', f'bytes {a}-{b}/{size}')
        else: self.send_response(200)
        if dl: self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(dl)}"')
        self.send_header('Content-Type', ctype); self.send_header('Accept-Ranges', 'bytes'); self.send_header('Content-Length', str(b - a + 1)); self.end_headers()
        with open(p, 'rb') as f:
            f.seek(a); left = b - a + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError): pass   # browser stopped loading (normal when you skip in the video)
    def local_ok(self):
        """only this pc may use the app (blocks websites that try to reach it through your browser)"""
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]').lower()
        if host not in ('localhost', '127.0.0.1', '::1'): self.j({'error': 'no access'}, 403); return False
        return True
    def do_GET(self):
        if not self.local_ok(): return
        try: return self._get()
        except (FileNotFoundError, KeyError): return self.j({'error': 'not found'}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        except Exception: tb = traceback.format_exc(); print(tb, file=sys.stderr); note_error('pagina ' + self.path.split('?')[0], tb); return self.j({'error': 'fout', 'why': friendly(tb)}, 500)
    def do_POST(self):
        if not self.local_ok(): return
        try: return self._post()
        except (FileNotFoundError, KeyError): return self.j({'error': 'not found'}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        except Exception: tb = traceback.format_exc(); print(tb, file=sys.stderr); note_error('actie ' + self.path.split('?')[0], tb); return self.j({'error': 'fout', 'why': friendly(tb)}, 500)
    def _get(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path
        GAME_TL.v = None
        if q.get('sid'): use_game(q['sid'][0], (q.get('a') or q.get('start') or [None])[0])
        elif q.get('f'):
            try: GAME_TL.v = (lib_load().get(os.path.basename(q['f'][0])) or {}).get('game')
            except Exception: pass
        if p == '/': return self.file(UI, 'text/html; charset=utf-8')
        if p in ('/icon.png', '/favicon.ico'): return self.file(os.path.join(HERE, 'icon.png' if p == '/icon.png' else 'jele.ico'), 'image/png' if p == '/icon.png' else 'image/x-icon')
        if p == '/api/status':
            cur = None
            if CUR['id']:
                try:
                    cs = load_sess(CUR['id']); cur = {'id': cs['id'], 'title': cs.get('title'), 'start': cs.get('start'), 'markers': cs.get('markers', [])[-8:], 'n_markers': len(cs.get('markers', []))}
                except Exception: pass
            return self.j({'cur': cur, 'now': time.time(), 'obs': obs.ok, 'recording': bool(CUR['id']), 'job': STATE['job'], 'jobs': STATE.jobs(), 'queue': JOBS.qsize(), 'pending': [x for x in JOBS.pending if not x.get('skip')], 'done': STATE['done'][-10:], 'test': STATE.get('test'), 'ffmpeg': FF, 'settings': SET,
                           'version': VERSION, 'paused': paused() and bool(STATE.jobs() or JOBS.qsize()), 'pause_why': pause_reason() if (STATE.jobs() or JOBS.qsize()) else None, 'live': bool(STATE.get('live')), 'health': health(), 'safe': SAFE['on'], 'update': bool(UPD.get('newer')),
                           'selftest': SELFTEST, 'last_error': STATE.get('last_error'), 'hersteld': json.load(open(HERSTELD, encoding='utf-8')) if os.path.exists(HERSTELD) else None,
                           'scene': STATE.get('scene'), 'scene_blocked': scene_blocked(), 'hype': hype() if STATE.get('live') else None, 'drop': LIVE['drop'],
                           'live_clips': LIVE['clips'][-8:], 'summary': STATE.get('summary'), 'whatsnew': SET.get('seen_version') != VERSION and bool(changes_for(VERSION)), 'n_errors': len(ERRORS)})
        if p == '/api/sessions': return self.j([x for x in list_sess() if q.get('all') or x.get('kind') != 'live'])   # live clips are not streams
        if p.startswith('/api/session/'):
            try: s = load_sess(p.split('/')[-1])
            except Exception: return self.j({'error': 'unknown'}, 404)
            s = dict(s); s['chat_n'] = len(load_chat(s['id'])); s['game_info'] = game_info(s)
            if SET.get('proxy', True) and s.get('path') and s.get('duration') and not s.get('proxy') and s['id'] not in PROXY_ASKED and not CUR['id'] == s['id']:
                PROXY_ASKED.add(s['id']); PROXYQ.put(s['id'])   # older streams get a work copy the first time you open them
            return self.j(s)
        if p == '/api/shorts':
            fs = sorted(glob.glob(os.path.join(OUT, '*.mp4')), key=os.path.getmtime, reverse=True); lib = lib_load()
            return self.j([{'file': os.path.basename(f), 'size': os.path.getsize(f), 'at': os.path.getmtime(f), **lib.get(os.path.basename(f), {'status': 'goed'})} for f in fs])
        if p == '/api/week': return self.j(week_stats())
        if p == '/api/fx-suggest':
            return self.j(fx_suggest(q['sid'][0], float(q['a'][0]), float(q['b'][0]), {'mid': q.get('mid', [None])[0]}))
        if p == '/api/music': return self.j({'files': music_list(), 'dir': MUSIC_DIR})
        if p == '/music':
            return self.file(os.path.join(MUSIC_DIR, os.path.basename(q['f'][0])), 'audio/mpeg')
        if p == '/api/storage': return self.j(storage_info())
        if p == '/thumbfile':
            return self.file(os.path.join(OUT, 'thumbnails', os.path.basename(q['f'][0])), 'image/png')
        if p == '/api/plan':
            lib = lib_load(); return self.j(sorted([{'file': f_, 'title': e.get('title'), 'at': e['plan_at'], 'done': bool(e.get('plan_done'))} for f_, e in lib.items() if e.get('plan_at')], key=lambda x: x['at']))
        if p == '/api/integrations':
            return self.j({'version': VERSION, 'henrik': bool(CFG.get('HENRIK_KEY')), 'riot': f"{CFG.get('RIOT_NAME', '')}#{CFG.get('RIOT_TAG', '')}" if CFG.get('RIOT_NAME') else '',
                           'twitch': bool(CFG.get('TWITCH_CLIENT_ID') and CFG.get('TWITCH_CLIENT_SECRET')), 'update_url': bool(CFG.get('UPDATE_URL')), 'ntfy_topic': SET.get('ntfy_topic')})
        if p == '/api/update-check':
            u = update_check(bool(q.get('force')))
            return self.j({'ok': bool(u.get('info')), 'current': VERSION, 'latest': (u.get('info') or {}).get('version'), 'notes': (u.get('info') or {}).get('notes', ''), 'newer': bool(u.get('newer')),
                           'why': u.get('error'), 'repo': SET.get('update_repo', ''), 'has_source': bool(SET.get('update_repo') or CFG.get('UPDATE_URL')), 'versions': versions_list(), 'busy': busy_reason()})
        if p == '/api/unsure': return self.j(load_unsure(q['sid'][0]))
        if p == '/api/search': return self.j(search_said(q.get('q', [''])[0]))
        if p == '/api/insights': return self.j(dict(insights(), best_hour=best_post_hour()))
        if p == '/api/trash': return self.j(trash_list())
        if p == '/trash': return self.file(os.path.join(TRASH, os.path.basename(q['f'][0])), 'video/mp4')
        if p == '/api/tips': return self.j(edit_suggestions())
        if p == '/api/brands': return self.j({'brands': [dict(brand_get(b['id']), has_logo=bool(brand_file(b['id'], 'logo')), has_font=bool(brand_file(b['id'], 'font'))) for b in brands()], 'default': SET.get('brand_default') or 'jele'})
        if p == '/brand-logo':
            lp = brand_file(q['id'][0], 'logo')
            if not lp: return self.j({'error': 'no logo'}, 404)
            return self.file(lp, 'image/png')
        if p == '/api/brand-export':
            import base64
            b = brand_get(q['id'][0]); out = {'jele_brand': 1, 'brand': b}
            for k in ('logo', 'font'):
                fp = brand_file(b['id'], k)
                if fp: out[k] = {'ext': os.path.splitext(fp)[1], 'data': base64.b64encode(open(fp, 'rb').read()).decode()}
            body = json.dumps(out).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Disposition', f'attachment; filename="merk_{b["id"]}.json"'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        if p == '/api/recap': return self.j({'text': recap_text(q['sid'][0])})
        if p in ('/api/clip', '/clip'):   # for a Stream Deck "Website" button: http://localhost:8765/api/clip
            return self.j({'ok': add_marker('streamdeck', (q.get('note') or [''])[0], int(q['len'][0]) if q.get('len') else None)})
        if p == '/api/quality':
            e_ = lib_load().get(os.path.basename(q['f'][0])) or {}; return self.j(e_.get('q') or {})
        if p == '/api/preview': return self.j(STATE['previews'].get(q['id'][0]) or {'ok': False, 'why': 'unknown'})
        if p == '/preview': return self.file(os.path.join(PREVIEW_DIR, os.path.basename(q['f'][0])), 'video/mp4')
        if p == '/api/draft':
            try: D = json.load(open(os.path.join(sdir(q['sid'][0]), 'drafts.json'), encoding='utf-8'))
            except Exception: D = {}
            return self.j(D.get(q.get('key', [''])[0]) or {})
        if p == '/api/voicelines': return self.j({'text': open(VOICE_FILE, encoding='utf-8').read() if os.path.exists(VOICE_FILE) else ''})
        if p == '/api/whatsnew':
            v = next((x for x in changelog() if x['version'] == VERSION), None)
            return self.j({'version': VERSION, 'items': changes_for(VERSION), 'groups': (v or {}).get('groups', []), 'date': (v or {}).get('date', '')})
        if p == '/api/changelog': return self.j({'current': VERSION, 'versions': changelog()})
        if p == '/api/backups': return self.j(backups_list())
        if p == '/api/keys': return self.j(keys_info())
        if p == '/api/selftest': return self.j(SELFTEST)
        if p == '/rapport':
            return self.file(os.path.join(REPORT_DIR, os.path.basename(q['f'][0])), 'application/zip', os.path.basename(q['f'][0]))
        if p == '/api/log': return self.j({'lines': list(LOGBUF)[-int(q.get('n', ['300'])[0]):]})
        if p == '/api/check': return self.j(system_check())
        if p == '/api/post':
            lib = lib_load(); e = lib.get(os.path.basename(q['f'][0])) or {}
            return self.j(e.get('post') or post_text(e.get('title') or '', []))
        if p == '/api/model-status': return self.j(model_status())
        if p == '/api/jumpcut-plan':   # the boring bits that would be cut from this clip, so the editor can show them
            try: return self.j({'cuts': jumpcut_plan(q['sid'][0], float(q['a'][0]), float(q['b'][0]))})
            except Exception as e_: log('Could not plan the cuts:', e_); return self.j({'cuts': []})
        if p == '/api/games': return self.j({'games': GP.public() if GP else [], 'default': SET.get('default_game') or 'valorant'})
        if p == '/api/vod-check': return self.j(vod_check())
        if p == '/api/phone-diag': return self.j(phone_diag())
        if p == '/api/phone':
            return self.j({'on': bool(SET.get('phone')), 'url': phone_url(), 'running': bool(PHONE.get('srv'))})
        if p == '/api/phone-qr':
            try:
                import qrcode, io
                im = qrcode.make(phone_url(), border=2, box_size=8); bio = io.BytesIO(); im.save(bio, format='PNG'); b = bio.getvalue()
                self.send_response(200); self.send_header('Content-Type', 'image/png'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b); return
            except Exception: return self.j({'error': 'qrcode not installed'}, 404)
        if p == '/api/detect-cam':
            return self.j({'cam': obs.detect_cam(), 'obs': obs.ok})
        if p.startswith('/fonts/'):
            return self.file(os.path.join(FONT_DIR, os.path.basename(p)), 'font/woff2' if p.endswith('.woff2') else 'font/ttf')
        if p == '/sthumb':   # a picture for a stream without moments
            ss = load_sess(q['sid'][0]); out = os.path.join(sdir(ss['id']), 'sthumb.jpg')
            if not os.path.exists(out) and ss.get('path'):
                run(['-y', '-ss', str(min(90, (ss.get('duration') or 20) / 2)), '-i', ss['path'], '-frames:v', '1', '-vf', 'scale=480:-2', out])
            return self.file(out, 'image/jpeg')
        if p == '/thumb':
            return self.file(os.path.join(sdir(q['sid'][0]), f"thumb_{q['mid'][0]}.jpg"), 'image/jpeg')
        if p == '/frame':   # a frame of the recording, for the crop picker
            s = load_sess(q['sid'][0]); out = os.path.join(sdir(s['id']), 'frame.jpg')
            run(['-y', '-ss', q.get('t', ['60'])[0], '-i', s['path'], '-frames:v', '1', '-vf', 'scale=1920:-2', out])
            return self.file(out, 'image/jpeg')
        if p == '/wave':   # loudness envelope of a range, for the editor timeline
            import numpy as np
            s = load_sess(q['sid'][0]); a = float(q.get('a', ['0'])[0]); d = min(600.0, float(q.get('d', ['60'])[0])); n = min(800, int(q.get('n', ['400'])[0]))
            r = subprocess.run([FF, '-v', 'error', '-ss', f'{a:.2f}', '-t', f'{d:.2f}', '-i', s['path'], '-vn', '-ac', '1', '-ar', '4000', '-f', 's16le', '-'], capture_output=True, creationflags=NOWIN)
            x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
            if len(x) < n: return self.j({'peaks': []})
            x = x[:len(x) // n * n].reshape(n, -1); pk = np.sqrt((x ** 2).mean(1)); pk = pk / max(1e-4, float(pk.max()))
            return self.j({'peaks': [round(float(v), 3) for v in pk]})
        if p == '/api/overview':
            return self.j(overview(q['sid'][0]))
        if p == '/api/transcript':
            return self.j(load_transcript(q['sid'][0]))
        if p == '/api/tracks':
            s = load_sess(q['sid'][0]); pick, why, tr = find_mic(s['path'])
            return self.j({'tracks': tr, 'auto': pick, 'why': why})
        if p == '/listen':   # 8 seconds of one audio track, so you can hear which one is your mic
            s = load_sess(q['sid'][0]); n = int(q.get('n', ['1'])[0]); at = float(q.get('t', ['60'])[0])
            out = os.path.join(sdir(s['id']), f'listen{n}.wav')
            run(['-y', '-ss', f'{at:.1f}', '-t', '8', '-i', s['path'], '-map', f'0:a:{n-1}', '-vn', '-ac', '1', '-ar', '22050', out])
            return self.file(out, 'audio/wav')
        if p == '/video':
            s = load_sess(q['sid'][0]); ext = os.path.splitext(s['path'])[1].lower()
            if not q.get('full') and os.path.exists(proxy_path(s['id'])): return self.file(proxy_path(s['id']), 'video/mp4')
            return self.file(s['path'], 'video/mp4' if ext in ('.mp4', '.mov') else 'video/x-matroska' if ext == '.mkv' else 'video/mp4')
        if p == '/short':
            return self.file(os.path.join(OUT, os.path.basename(unquote(q['f'][0]))), 'video/mp4')
        return self.j({'error': 'unknown'}, 404)
    def do_PUT(self):
        """drag a video into the app: it is copied into the clipper's import folder"""
        if not self.local_ok(): return
        try:
            u = urlparse(self.path); q = parse_qs(u.query)
            if u.path == '/api/brand-file':   # logo (png) or font (ttf/otf) for a brand profile
                bid = re.sub(r'\W', '', q.get('id', [''])[0])[:24]; kind = q.get('kind', [''])[0]; nm = q.get('name', ['x'])[0].lower()
                ext = os.path.splitext(nm)[1]
                if not bid or kind not in ('logo', 'font') or (kind == 'logo' and ext != '.png') or (kind == 'font' and ext not in ('.ttf', '.otf')):
                    return self.j({'ok': False, 'why': 'Logo as PNG, font as TTF or OTF'})
                n = int(self.headers.get('Content-Length') or 0)
                if n > 15 * 1024 * 1024: return self.j({'ok': False, 'why': 'File too large'})
                os.makedirs(os.path.join(BRAND_DIR, bid), exist_ok=True)
                for old in glob.glob(os.path.join(BRAND_DIR, bid, kind + '.*')): os.remove(old)
                dst = os.path.join(BRAND_DIR, bid, kind + ext); open(dst, 'wb').write(self.rfile.read(n))
                return self.j({'ok': True, 'colors': logo_colors(dst) if kind == 'logo' else None})
            if u.path != '/api/upload': return self.j({'error': 'unknown'}, 404)
            name = re.sub(r'[^\w .()\[\]-]+', '_', os.path.basename(q.get('name', ['video.mp4'])[0]))[:120]
            if not name.lower().endswith(VIDEO_EXT): return self.j({'ok': False, 'why': 'That is not a video'})
            n = int(self.headers.get('Content-Length') or 0); dst = os.path.join(IMPORTS, name); i = 2
            while os.path.exists(dst): dst = os.path.join(IMPORTS, f'{os.path.splitext(name)[0]}_{i}{os.path.splitext(name)[1]}'); i += 1
            with open(dst, 'wb') as fh:
                left = n
                while left > 0:
                    chunk = self.rfile.read(min(1 << 22, left))
                    if not chunk: break
                    fh.write(chunk); left -= len(chunk)
            if left > 0: os.remove(dst); return self.j({'ok': False, 'why': 'Upload cancelled'})
            return self.j({'ok': True, 'sid': import_file(dst)})
        except Exception as e: traceback.print_exc(); return self.j({'ok': False, 'why': str(e)[:120]})
    def _post(self):
        p = urlparse(self.path).path; b = self.body()
        GAME_TL.v = None
        if isinstance(b, dict) and b.get('sid'): use_game(b['sid'], b.get('start'))
        if p == '/api/session-game':   # you say which game a stream is (or '' to let the clipper find out again)
            s_ = load_sess(b['sid']); g_ = (b.get('game') or '').strip()
            if g_ and GP and g_ not in GP.GAMES: return self.j({'error': 'unknown game'}, 400)
            if g_: s_['game_set'] = g_
            else: s_.pop('game_set', None)
            save_sess(s_); log(f'Game of {s_["title"]}: {gprof(game_quick(s_)["id"])["name"]}')
            return self.j({'ok': True, 'game_info': game_info(s_)})
        if p == '/api/render':
            JOBS.put(('render', {'sid': b['sid'], 'start': b['start'], 'end': b['end'], 'title': b.get('title', ''), 'hook': b.get('hook', ''), 'captions': b.get('captions', SET['captions']), 'mid': b.get('mid'), 'layout': b.get('layout'), 'style': b.get('style'), 'words': b.get('words'), 'zoom': b.get('zoom', SET.get('auto_zoom', True)), 'variant': b.get('variant'), 'replace': b.get('replace'),
                                  'cap_y': b.get('cap_y'), 'cap_scale': b.get('cap_scale'), 'game_x': b.get('game_x'), 'cam_h': b.get('cam_h'), 'progress': b.get('progress'), 'endcard': b.get('endcard'),
                                  'jumpcut': b.get('jumpcut', SET.get('jumpcut', True)), 'sfx': b.get('sfx', SET.get('sfx', True)), 'fx': b.get('fx'), 'voice': b.get('voice'), 'music': b.get('music'),
                                  **{k: b.get(k) for k in RENDER_EXTRA if k in b}})); return self.j({'ok': True, 'queue': JOBS.qsize()})
        if p == '/api/preview':   # quick, small version of the end result
            pid = uuid.uuid4().hex[:8]
            job = {k: b.get(k) for k in ('sid', 'start', 'end', 'hook', 'captions', 'mid', 'layout', 'style', 'words', 'zoom', 'cap_y', 'cap_scale', 'game_x', 'cam_h', 'progress', 'endcard', 'jumpcut', 'sfx', 'fx', 'voice', 'music') + RENDER_EXTRA if k in b}
            job.update(title='voorbeeld', preview=pid)
            if SAFE['on']: job.update(fx={'zooms': [], 'killfeed': [], 'stickers': []}, jumpcut=False, sfx=False, zoom=False, music=None)
            STATE['previews'][pid] = {'ok': None}; STATE['run_live'] = STATE.get('run_live') or False
            JOBS.put_front(('render', job)); return self.j({'ok': True, 'id': pid})
        if p == '/api/draft':   # the editor saves every change, so you can continue later (undo included)
            d_ = os.path.join(sdir(b['sid']), 'drafts.json')
            try: D = json.load(open(d_, encoding='utf-8'))
            except Exception: D = {}
            key = str(b.get('key') or '')[:60]
            if b.get('clear'): D.pop(key, None)
            else: D[key] = {'state': b.get('state'), 'hist': (b.get('hist') or [])[-30:], 'at': time.time()}
            if len(D) > 60: D = dict(sorted(D.items(), key=lambda kv: kv[1].get('at', 0))[-60:])
            json.dump(D, open(d_, 'w', encoding='utf-8')); return self.j({'ok': True})
        if p == '/api/voicelines':
            txt = str(b.get('text', ''))
            if b.get('add'):
                cur = open(VOICE_FILE, encoding='utf-8').read() if os.path.exists(VOICE_FILE) else ''
                txt = cur.rstrip('\n') + '\n' + str(b['add']).strip() + '\n'
            open(VOICE_FILE, 'w', encoding='utf-8').write(txt); _VL['t'] = 0
            return self.j({'ok': True})
        if p == '/api/pack':
            try:
                folder, made = make_pack(os.path.basename(b['file']), b.get('platforms') or SET.get('platforms') or ['tiktok'])
                if os.name == 'nt' and b.get('open', True):
                    try: os.startfile(folder)
                    except Exception: pass
                return self.j({'ok': True, 'folder': folder, 'made': made})
            except Exception as e: return self.j({'ok': False, 'why': friendly(str(e))})
        if p == '/api/fix-all':   # apply all safe fixes and make the short again (replaces the old one)
            lib = lib_load(); e_ = lib.get(os.path.basename(b['file']))
            if not e_ or not e_.get('job'): return self.j({'ok': False, 'why': 'This short was made with an older version; open it in the editor and export again'})
            e_ = dict(e_, file=os.path.basename(b['file'])); job = q_fixed_job(e_)
            JOBS.put(('render', job)); return self.j({'ok': True})
        if p == '/api/brand-save':
            nb = b.get('brand') or {}; bid = re.sub(r'\W', '', (nb.get('id') or nb.get('name') or 'merk').lower())[:24] or 'merk'; nb['id'] = bid
            if bid == 'jele' and nb.get('tag'): SET['tag'] = nb['tag']
            L = [x for x in (SET.get('brands') or []) if x.get('id') != bid] + [{k: nb.get(k) for k in ('id', 'name', 'tag', 'color', 'ink', 'end_text', 'credit', 'wm')}]
            SET['brands'] = L
            if b.get('default'): SET['brand_default'] = bid
            save_settings(SET); return self.j({'ok': True, 'id': bid, 'readable': contrast_ok(nb.get('color'))})
        if p == '/api/brand-del':
            bid = b.get('id')
            if bid == 'jele': return self.j({'ok': False, 'why': 'The JelE profile always stays'})
            SET['brands'] = [x for x in (SET.get('brands') or []) if x.get('id') != bid]
            if SET.get('brand_default') == bid: SET['brand_default'] = 'jele'
            shutil.rmtree(os.path.join(BRAND_DIR, re.sub(r'\W', '', bid or '')), ignore_errors=True); save_settings(SET); return self.j({'ok': True})
        if p == '/api/brand-import':
            import base64
            d_ = b.get('data') or {}
            if not d_.get('jele_brand'): return self.j({'ok': False, 'why': 'This is not a JelE Clipper brand profile'})
            nb = d_['brand']; bid = re.sub(r'\W', '', (nb.get('id') or 'merk').lower())[:24]
            if bid == 'jele': bid = 'jele_import'
            nb['id'] = bid; os.makedirs(os.path.join(BRAND_DIR, bid), exist_ok=True)
            for k in ('logo', 'font'):
                if d_.get(k): open(os.path.join(BRAND_DIR, bid, k + d_[k]['ext']), 'wb').write(base64.b64decode(d_[k]['data']))
            SET['brands'] = [x for x in (SET.get('brands') or []) if x.get('id') != bid] + [{k: nb.get(k) for k in ('id', 'name', 'tag', 'color', 'ink', 'end_text', 'credit', 'wm')}]
            save_settings(SET); return self.j({'ok': True, 'id': bid})
        if p == '/api/extra':
            try:
                out = extra_make(b['file'], b.get('kind'), b.get('text', ''))
                if os.name == 'nt' and b.get('open', True):
                    try: subprocess.Popen(['explorer', '/select,', out])
                    except Exception: pass
                return self.j({'ok': True, 'file': os.path.basename(out)})
            except Exception as e: return self.j({'ok': False, 'why': str(e)[:160] if isinstance(e, ValueError) else friendly(str(e))})
        if p == '/api/dual':
            def go_():
                try: o_ = dual_short(b['sid'], b['start'], b['end'], b['other'], b.get('title', '')); log('Two sides ready:', o_)
                except Exception as e: log('Two sides failed:', e); STATE['done'].append({'file': None, 'ok': False, 'at': time.time(), 'why': str(e)[:160], 'title': 'Two sides'})
                else: STATE['done'].append({'file': os.path.basename(o_), 'ok': True, 'at': time.time(), 'why': None, 'title': 'Two sides'})
            threading.Thread(target=go_, daemon=True).start(); return self.j({'ok': True})
        if p == '/api/team-copy':
            d_ = team_copy(b['file']); return self.j({'ok': bool(d_), 'why': None if d_ else 'Set a team folder first (Settings > Brand)'})
        if p == '/api/summary-ok': STATE['summary'] = None; return self.j({'ok': True})
        if p == '/api/fix-add':
            a_, b_ = str(b.get('from', '')).strip(), str(b.get('to', '')).strip()
            if a_:
                SET['fixes'] = [x for x in (SET.get('fixes') or []) if x[0].lower() != a_.lower()] + [[a_, b_]]; save_settings(SET)
            return self.j({'ok': True, 'fixes': SET['fixes']})
        if p == '/api/analyse':
            JOBS.put(('analyse', b['sid'])); return self.j({'ok': True})
        if p == '/api/import':
            path = b.get('path', '').strip().strip('"')
            if not os.path.exists(path): return self.j({'error': 'File not found'}, 400)
            s = new_session(title=os.path.splitext(os.path.basename(path))[0], path=path, start=os.path.getmtime(path))
            JOBS.put(('analyse', s['id'])); return self.j({'ok': True, 'sid': s['id']})
        if p == '/api/marker':
            return self.j({'ok': add_marker('website')})
        if p == '/api/quit':   # from the icon next to the clock: close (or restart) the Clipper
            log('Restarting the Clipper' if b.get('restart') else 'The Clipper is closed')
            restart_app(0.3) if b.get('restart') else threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0)), daemon=True).start()
            return self.j({'ok': True})
        if p == '/api/shortcuts': return self.j({'ok': make_shortcuts(True)})
        if p == '/api/settings':
            SET.update({k: v for k, v in b.items() if k in DEFAULTS}); save_settings(SET); return self.j({'ok': True, 'settings': SET})
        if p == '/api/open':
            target = OUT if b.get('what') == 'shorts' else MUSIC_DIR if b.get('what') == 'music' else sdir(b.get('sid', ''))
            try:
                if os.name == 'nt': os.startfile(target)
            except Exception: pass
            return self.j({'ok': True})
        if p == '/api/delete-short':
            fn = os.path.basename(b.get('file', '')); e = lib_load().get(fn)
            trash_short(fn)   # 6.3: to the trash for 7 days
            if e and e.get('auto') and e.get('status') == 'nieuw': taste_note(e.get('reasons'), False, e.get('dur'))   # thrown away from the inbox
            return self.j({'ok': True})
        if p == '/api/trash-restore': restore_short(os.path.basename(b.get('file', ''))); return self.j({'ok': True})
        if p == '/api/block-kind':   # "not like this again"
            e = lib_load().get(os.path.basename(b.get('file', ''))) or {}; ks = sorted(reason_keys(e.get('reasons')))
            if ks:
                SET['blocked_kinds'] = [x for x in (SET.get('blocked_kinds') or []) if x != ks] + [ks]; save_settings(SET)
                for _ in range(3): taste_note(e.get('reasons'), False, e.get('dur'))
            return self.j({'ok': True, 'kind': ks})
        if p == '/api/short-meta':   # tags, status (concept, goed, gepland, gepost), link, favourite, archive
            lib = lib_load(); fs = b.get('files') or [b.get('file')]
            for fn in fs:
                e = lib.get(os.path.basename(fn or ''))
                if not e: continue
                for k in ('tags', 'status', 'link', 'fav', 'archived'):
                    if k in b: e[k] = b[k]
                if b.get('add_tag'): e['tags'] = sorted(set((e.get('tags') or []) + [b['add_tag'].strip().lower()]))
                if b.get('status') == 'gepost' and not e.get('posted_on'): short_mark_posted(e, 'all', True)
                elif 'status' in b and b['status'] != 'gepost' and e.get('posted_on'): e['posted_on'] = {}; e.pop('posted_at', None)
            lib_save(lib); return self.j({'ok': True})
        if p == '/api/short-posted':   # you posted it (or not) on one platform: {file, platform: tiktok|shorts|reels|all, on}
            lib = lib_load(); fs = b.get('files') or [b.get('file')]; out = None
            for fn in fs:
                e = lib.get(os.path.basename(fn or ''))
                if e: short_mark_posted(e, b.get('platform') or 'all', bool(b.get('on', True))); out = e
            lib_save(lib); return self.j({'ok': bool(out), 'status': out and out.get('status'), 'posted_on': out and out.get('posted_on')})
        if p == '/api/tip':
            k = b.get('k', ''); SET['tips_done'] = list(set((SET.get('tips_done') or []) + [k]))
            if b.get('yes'):
                if k in EDIT_TIPS and EDIT_TIPS[k][1]: SET.update(EDIT_TIPS[k][1])
                if k.startswith('layout:'): SET['layout'] = k[7:]
            save_settings(SET); return self.j({'ok': True})
        if p == '/api/fix-used': note_fix(b.get('k', ''), bool(b.get('used'))); return self.j({'ok': True})
        if p == '/api/short-ok' and SET.get('team_auto'):
            try: team_copy(b.get('file', ''))
            except Exception: pass
        if p == '/api/short-ok':   # kept from the inbox
            fn = os.path.basename(b.get('file', '')); lib = lib_load(); e = lib.get(fn)
            if e:
                if e.get('status') == 'nieuw': taste_note(e.get('reasons'), True)
                e['status'] = 'goed'; lib_save(lib)
            return self.j({'ok': True})
        if p == '/api/cancel':   # stop the short being made, or take one out of the queue
            if b.get('what') == 'current':
                js = STATE.jobs(); n_ = b.get('n')
                for k_, j_ in enumerate(js):
                    if n_ is None or int(n_) == k_: j_['cancel'] = True
            else:
                vis = [i for i, x in enumerate(JOBS.pending) if not x.get('skip')]
                i = int(b.get('i', -1))
                if 0 <= i < len(vis): JOBS.remove(vis[i])
            return self.j({'ok': True})
        if p == '/api/montage':   # best moments of one stream, or of the week, in one video
            sids = [b['sid']] if b.get('sid') else week_stats()['sids']
            parts = montage_parts(sids, int(b.get('n', 5)))
            if len(parts) < 2: return self.j({'ok': False, 'why': 'Too few moments for a montage'})
            hook = b.get('hook') or ('BEST OF THE WEEK' if not b.get('sid') else 'BEST OF STREAM')
            pre = next((x for x in SET.get('presets', []) if x.get('name') == SET.get('auto_preset')), {})
            JOBS.put(('render', {'sid': parts[0]['sid'], 'start': 0, 'end': sum(p_['b'] - p_['a'] for p_ in parts), 'parts': parts, 'title': hook.lower().replace(' ', '_'),
                                 'hook': hook, 'captions': SET['captions'], 'jumpcut': False, **{k: v for k, v in pre.items() if k in ('layout', 'style', 'cap_scale', 'progress', 'endcard', 'sfx')}}))
            return self.j({'ok': True, 'n': len(parts)})
        if p == '/api/highlights':
            parts = highlight_parts(b['sid'], int(b.get('minutes') or SET.get('highlight_min', 8)))
            if len(parts) < 2: return self.j({'ok': False, 'why': 'Too few moments. Find the moments first (with smart search on).'})
            ss = load_sess(b['sid'])
            JOBS.put(('render', {'sid': b['sid'], 'start': 0, 'end': sum(p_['b'] - p_['a'] for p_ in parts), 'parts': parts, 'chapters': True, 'kind': 'highlights',
                                 'title': re.sub(r'[^\w-]+', '_', ss['title'])[:40] + '_highlights', 'hook': '', 'captions': bool(b.get('captions', True)),
                                 'layout': 'landscape', 'jumpcut': False, 'endcard': False, 'zoom': False}))
            return self.j({'ok': True, 'n': len(parts), 'secs': round(sum(p_['b'] - p_['a'] for p_ in parts))})
        if p == '/api/thumbnail':
            try: out = make_thumbnail(b.get('file'), b.get('sid'), b.get('t'), b.get('text', ''), b.get('kind', 'yt'))
            except Exception as e: traceback.print_exc(); return self.j({'ok': False, 'why': str(e)[:120]})
            return self.j({'ok': True, 'file': os.path.basename(out)})
        if p == '/api/plan':
            lib = lib_load(); e = lib.get(os.path.basename(b.get('file', '')))
            if e:
                e['plan_at'] = float(b['at']) if b.get('at') else None; e['plan_done'] = False
                if e.get('status') != 'gepost': e['status'] = 'gepland' if e['plan_at'] else 'goed'
                lib_save(lib)
            return self.j({'ok': bool(e), 'ntfy': bool(SET.get('ntfy'))})
        if p == '/api/storage-clean':
            ss = load_sess(b['sid']); p_ = ss.get('path')
            if b.get('what') == 'recording' and p_ and os.path.exists(p_):
                if CUR['id'] == ss['id']: return self.j({'ok': False, 'why': 'This recording is still running'})
                ok = recycle(p_); ss['status'] = 'opname weg'; save_sess(ss); log('Recording to the recycle bin:', p_); return self.j({'ok': ok})
            return self.j({'ok': False})
        if p == '/api/import-url':
            url = (b.get('url') or '').strip()
            if not re.match(r'https?://', url): return self.j({'ok': False, 'why': 'That is not a link'})
            JOBS.put(('download', {'url': url, 'a': b.get('a'), 'b': b.get('b')})); return self.j({'ok': True})
        if p == '/api/import-folder':
            d_ = (b.get('path') or '').strip().strip('"')
            if not os.path.isdir(d_): return self.j({'ok': False, 'why': 'Folder not found'})
            known = {os.path.abspath(load_sess(x['id']).get('path') or '') for x in list_sess()}
            fs = [f_ for f_ in sorted(glob.glob(os.path.join(d_, '*'))) if f_.lower().endswith(VIDEO_EXT) and os.path.abspath(f_) not in known]
            for f_ in fs: import_file(f_)
            return self.j({'ok': True, 'n': len(fs)})
        if p == '/api/short-views':
            lib = lib_load(); e = lib.get(os.path.basename(b.get('file', '')))
            if e:
                e['views'] = max(0, int(b.get('views') or 0))
                if e['views'] and not e.get('posted_on'): short_mark_posted(e, 'any', True)   # it has views, so it was posted
                lib_save(lib)
            return self.j({'ok': bool(e), 'status': e and e.get('status')})
        if p == '/api/ntfy':
            if b.get('on') and not SET.get('ntfy_topic'): SET['ntfy_topic'] = 'jele-clipper-' + uuid.uuid4().hex[:10]
            if 'on' in b: SET['ntfy'] = bool(b['on'])
            save_settings(SET)
            ok = notify('JelE Clipper test', 'It works! This is how you get notified when your shorts are ready.') if b.get('test') else None
            return self.j({'on': SET['ntfy'], 'topic': SET.get('ntfy_topic'), 'sent': ok})
        if p in ('/api/update-do', '/api/update-install'):
            return self.j(install_update())
        if p == '/api/update-repo':
            SET['update_repo'] = (b.get('repo') or '').strip(); save_settings(SET); UPD['checked'] = 0
            u = update_check(True); return self.j({'ok': bool(u.get('info')), 'why': u.get('error'), 'newer': bool(u.get('newer')), 'latest': (u.get('info') or {}).get('version')})
        if p == '/api/rollback': return self.j(rollback(b.get('file')))
        if p == '/api/backup-now':
            try: f_ = backup_now(); return self.j({'ok': True, 'file': os.path.basename(f_)})
            except Exception as e: return self.j({'ok': False, 'why': friendly(str(e))})
        if p == '/api/backup-restore': return self.j(backup_restore(b.get('file', '')))
        if p == '/api/keys': return self.j(keys_save(b.get('keys') or {}))
        if p == '/api/keys-test': return self.j(keys_test(b.get('key', '')))
        if p == '/api/report':
            f_ = make_report((b.get('note') or '')[:2000])
            if b.get('open') and os.name == 'nt':
                try: subprocess.Popen(['explorer', '/select,', f_])
                except Exception: pass
            return self.j({'ok': True, 'file': os.path.basename(f_)})
        if p == '/api/obs-record':
            r = obs.req('StartRecord') if obs.ok else None
            return self.j({'ok': r is not None, 'why': None if r is not None else 'OBS is not connected'})
        if p == '/api/run-live':   # do the heavy work now, also while live
            STATE['run_live'] = bool(b.get('on', True)); return self.j({'ok': True})
        if p == '/api/safe':
            SET['safe_mode'] = bool(b.get('on')); save_settings(SET); SAFE['on'] = SET['safe_mode'] or '--veilig' in sys.argv
            return self.j({'ok': True, 'on': SAFE['on']})
        if p == '/api/seen':
            for k in ('seen_version', 'wizard_done', 'tour_done', 'adv'):
                if k in b: SET[k] = b[k]
            save_settings(SET); return self.j({'ok': True})
        if p == '/api/hersteld-ok':
            try: os.remove(HERSTELD)
            except OSError: pass
            return self.j({'ok': True})
        if p == '/api/model-get': return self.j(model_get())
        if p == '/api/phone-newkey':
            SET['phone_key'] = uuid.uuid4().hex[:10]; save_settings(SET); return self.j({'ok': True, 'url': phone_url()})
        if p == '/api/test-short':   # makes a 4 second test short from your newest recording
            ss = [x for x in list_sess() if x.get('path') and x.get('duration')]
            if not ss: return self.j({'ok': False, 'why': 'No recording to test with yet'})
            x = ss[0]; t0 = min(60, max(0, (x['duration'] or 10) / 2))
            JOBS.put(('render', {'sid': x['id'], 'start': t0, 'end': t0 + 4, 'title': 'test_short', 'hook': 'TEST', 'captions': False, 'endcard': False, 'test': True}))
            return self.j({'ok': True})
        if p == '/api/phone':
            SET['phone'] = bool(b.get('on'))
            if SET['phone']: SET['phone_on_at'] = time.time()
            save_settings(SET)
            phone_start() if SET['phone'] else phone_stop()
            return self.j({'on': SET['phone'], 'url': phone_url()})
        if p == '/api/moment-add':   # a clip you picked yourself, saved between the found moments
            s = load_sess(b['sid']); st, en = float(b['start']), float(b['end'])
            m = {'id': uuid.uuid4().hex[:8], 't': round(st + (en - st) * 0.7, 1), 'start': round(st, 1), 'end': round(en, 1), 'score': float(b.get('score', 0)),
                 'reasons': ['chosen by you'], 'marker': False, 'title': b.get('title', ''), 'manual': True}
            tw = load_transcript(s['id'])
            if tw: m['words'] = [w for w in tw if st - 1 <= w[0] <= en + 1]; m['text'] = ' '.join(w[2] for w in m['words'])[:400]
            run(['-y', '-ss', str(m['t']), '-i', s['path'], '-frames:v', '1', '-vf', 'scale=480:-2', os.path.join(sdir(s['id']), f"thumb_{m['id']}.jpg")])
            s.setdefault('moments', []).append(m); save_sess(s); return self.j({'ok': True, 'moment': m})
        if p == '/api/moment-del':
            s = load_sess(b['sid']); s['moments'] = [m for m in s.get('moments', []) if m['id'] != b.get('mid')]; save_sess(s); return self.j({'ok': True})
        if p == '/api/delete-session':
            shutil.rmtree(sdir(os.path.basename(b.get('sid', 'x'))), ignore_errors=True); return self.j({'ok': True})
        return self.j({'error': 'unknown'}, 404)

def main():
    log(f'JelE Clipper {VERSION} start. ffmpeg:', FF)
    if SET.get('low_priority', True): low_priority()
    try:
        srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)   # first: is the clipper already running?
    except OSError:
        log('The clipper is already running (port in use). You can close this window.'); time.sleep(3); return
    try: recover_personal()
    except Exception as e: log('Moving the channel name failed:', e)
    try: lib_migrate()
    except Exception: traceback.print_exc()
    # a recording that was still marked "opnemen" from a crash: close it
    for s in list_sess():
        if s['status'] == 'opnemen':
            ss = load_sess(s['id']); ss['status'] = 'onderbroken'; save_sess(ss)
    for d in glob.glob(os.path.join(SESS, '*', 'tmp_*')): shutil.rmtree(d, ignore_errors=True)   # leftovers from a crash
    shutil.rmtree(PREVIEW_DIR, ignore_errors=True)
    if SAFE['on']: log('SAFE MODE: shorts are made without effects, music and extras')
    obs.start()
    threading.Thread(target=chat_loop, daemon=True).start()
    JOBS.restore()
    for _ in range(n_workers()): threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=make_shortcuts, daemon=True).start()
    for fn in (guard_loop, planner, proxy_loop, update_loop, backup_loop, phone_guard_loop, selftest, confirm_start, live_loop, trash_loop):
        threading.Thread(target=fn, daemon=True).start()
    log(f'Open http://localhost:{PORT} in your browser')
    if SET.get('phone'): phone_start()
    if os.name == 'nt' and '--no-browser' not in sys.argv:
        try: os.startfile(f'http://localhost:{PORT}')
        except Exception: pass
    srv.serve_forever()
