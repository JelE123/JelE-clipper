# JelE Clipper part: which game, Twitch chat. Loaded by clipper.py into one shared namespace, do not run on its own.
# ---------------------------------------------------------------- which game is this?
try: import games as GP          # one profile per game (games.py)
except Exception: GP = None
GAME_TL = threading.local()       # the game of the stream that this thread is working on

def gprof(gid=None):
    """the profile of a game (or of the game this thread works on)"""
    gid = gid or cur_game()
    if GP: return GP.get(gid)
    return {'name': 'Valorant', 'killfeed': True, 'matchdata': True, 'hashtags': SET.get('hashtags', ''), 'word_tags': {}, 'hype': 'ace|clutch', 'strong': 'ace|clutch',
            'hooks': ['WAIT FOR IT...'], 'stickers': ['NO WAY'], 'teaser': 'WAIT FOR IT...', 'fallback': 'Stream moment', 'platform_tags': {}}

def cur_game():
    return getattr(GAME_TL, 'v', None) or SET.get('default_game') or 'valorant'

def use_game(sid, t=None):
    """from now on this thread works on the game of this stream (at t seconds in, if you switched games)"""
    try: GAME_TL.v = game_quick(load_sess(sid), float(t) if t not in (None, '') else None)['id'] if sid else None
    except Exception: GAME_TL.v = None

def _by_name(txt, field):
    t = (txt or '').lower()
    if not t or not GP: return None
    for g in GP.ORDER:
        if any(x and x in t for x in GP.GAMES[g].get(field, [])): return g
    return None

def _foreground():
    """the program and window title in front on this PC (Windows), or ('', '')"""
    if os.name != 'nt': return '', ''
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32; k = ctypes.windll.kernel32
        hw = u.GetForegroundWindow()
        if not hw: return '', ''
        buf = ctypes.create_unicode_buffer(512); u.GetWindowTextW(hw, buf, 512); title = buf.value
        pid = wintypes.DWORD(); u.GetWindowThreadProcessId(hw, ctypes.byref(pid))
        h = k.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
        exe = ''
        if h:
            n = wintypes.DWORD(1024); pb = ctypes.create_unicode_buffer(1024)
            if k.QueryFullProcessImageNameW(h, 0, pb, ctypes.byref(n)): exe = os.path.basename(pb.value)
            k.CloseHandle(h)
        return exe.lower(), title
    except Exception: return '', ''

def _running_games():
    """known games that are running on this PC (Windows)"""
    if os.name != 'nt' or not GP: return []
    try:
        out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, errors='replace', timeout=8, creationflags=NOWIN).stdout.lower()
        return [g for g in GP.ORDER if any(('"' + e + '"') in out for e in GP.GAMES[g].get('exe', []))]
    except Exception: return []

_TW = {'tok': None, 'until': 0, 'uid': None}
def twitch_category():
    """the category your Twitch channel is set to right now (needs TWITCH_CLIENT_ID/SECRET in config.js)"""
    cid, sec = CFG.get('TWITCH_CLIENT_ID'), CFG.get('TWITCH_CLIENT_SECRET')
    if not (cid and sec and CFG.get('CHANNEL')): return ''
    try:
        if not _TW['tok'] or time.time() > _TW['until']:
            r = http_json('https://id.twitch.tv/oauth2/token', data=urllib.parse.urlencode({'client_id': cid, 'client_secret': sec, 'grant_type': 'client_credentials'}).encode())
            _TW['tok'] = r['access_token']; _TW['until'] = time.time() + min(3600, r.get('expires_in', 3600)) - 60
        h = {'Client-Id': cid, 'Authorization': 'Bearer ' + _TW['tok']}
        if not _TW['uid']: _TW['uid'] = http_json('https://api.twitch.tv/helix/users?login=' + urllib.parse.quote(CFG['CHANNEL'].lower().lstrip('#')), h)['data'][0]['id']
        return (http_json('https://api.twitch.tv/helix/channels?broadcaster_id=' + _TW['uid'], h).get('data') or [{}])[0].get('game_name', '')
    except Exception: return ''

def obs_game_window():
    """the window your game capture / window capture in OBS points at"""
    if not obs.ok: return ''
    try:
        out = []
        for it in (obs.req('GetInputList') or {}).get('inputs', []):
            if it.get('inputKind') in ('game_capture', 'window_capture'):
                st = (obs.req('GetInputSettings', {'inputName': it['inputName']}) or {}).get('inputSettings', {})
                out.append((st.get('window') or '') + ' ' + it['inputName'])
        return ' | '.join(out)
    except Exception: return ''

def sense_game():
    """(game, how) right now, or (None, None)"""
    exe, title = _foreground()
    g = _by_name(exe, 'exe') or (('minecraft' if 'minecraft' in title.lower() else None) if exe in ('javaw.exe', 'java.exe') else None) or _by_name(title, 'window')
    if g: return g, 'pc'
    run_ = _running_games()
    if len(run_) == 1: return run_[0], 'pc'
    g = _by_name(twitch_category(), 'twitch')
    if g: return g, 'twitch'
    g = _by_name(obs_game_window(), 'window') or _by_name(obs_game_window(), 'exe')
    if g: return g, 'obs'
    return None, None

def remember_game(sid):
    """while you record: every few minutes, which game is in front. A switch from Valorant to Minecraft is noted too"""
    if not SET.get('game_detect', True): return
    last = None
    while CUR['id'] == sid:
        try:
            g, how = sense_game()
            if g and g != last:
                s = load_sess(sid); s.setdefault('game_log', []).append([round(time.time(), 1), g, how]); save_sess(s)
                log(f'Game: {gprof(g)["name"]} (seen via {how})'); last = g
        except Exception: traceback.print_exc()
        for _ in range(180):
            if CUR['id'] != sid: return
            time.sleep(1)

def speech_game(words):
    """which game the words give away, if it is clear"""
    if not GP or not words: return None
    txt = ' '.join(w[2] for w in words if w[2] != UNCLEAR).lower()
    n = {g: len(re.findall(r'\b(' + rx + r')\b', txt)) for g, rx in GP.SIGNS.items()}
    top = sorted(n.items(), key=lambda x: -x[1])
    if top[0][1] >= 5 and top[0][1] >= 2.5 * max(1, top[1][1]): return top[0][0]
    return None

def game_quick(s, t=None):
    """{'id', 'by'}: which game this stream is (at t seconds in, when the game changed during the stream)"""
    if s.get('game_set'): return {'id': s['game_set'], 'by': 'you'}
    log_ = s.get('game_log') or []
    if log_:
        if t is not None and s.get('start'):
            at = s['start'] + t; cur = log_[0]
            for e in log_:
                if e[0] <= at: cur = e
            return {'id': cur[1], 'by': cur[2]}
        cnt = collections.Counter(e[1] for e in log_)
        return {'id': cnt.most_common(1)[0][0], 'by': log_[0][2]}
    if s.get('game_events'): return {'id': 'valorant', 'by': 'matches'}
    nm = (s.get('title') or '') + ' ' + os.path.basename(s.get('path') or '')
    g = _by_name(nm, 'window')
    if g: return {'id': g, 'by': 'title'}
    if s.get('game_speech'): return {'id': s['game_speech'], 'by': 'speech'}
    return {'id': SET.get('default_game') or 'valorant', 'by': 'default'}

def game_info(s, t=None):
    g = game_quick(s, t); P = gprof(g['id'])
    by = {'you': 'set by you', 'pc': 'seen on your PC', 'twitch': 'your Twitch category', 'obs': 'your OBS capture', 'matches': 'your Valorant matches',
          'title': 'the name of the recording', 'speech': 'what you say', 'default': 'your default game'}.get(g['by'], g['by'])
    switched = len({e[1] for e in s.get('game_log') or []}) > 1
    return {'id': g['id'], 'name': P['name'], 'by': g['by'], 'by_text': by, 'switched': switched}

def game_for(sid, t=None):
    try: return game_quick(load_sess(sid), t)['id']
    except Exception: return SET.get('default_game') or 'valorant'

class GameRe:
    """a regex that also knows the words of the game this thread works on"""
    def __init__(self, base, field): self.base = base; self.field = field; self.cache = {}
    def rx(self):
        g = cur_game()
        if g not in self.cache:
            extra = re.sub(r'\((?!\?)', '(?:', gprof(g).get(self.field) or '')   # no extra groups: findall keeps giving plain words
            pat = self.base if not extra else self.base.replace(r"\b(", r"\b(" + extra + '|', 1)
            self.cache[g] = re.compile(pat, re.I)
        return self.cache[g]
    def search(self, *a): return self.rx().search(*a)
    def match(self, *a): return self.rx().match(*a)
    def findall(self, *a): return self.rx().findall(*a)
    def fullmatch(self, *a): return self.rx().fullmatch(*a)

# ---------------------------------------------------------------- Twitch chat (anonymous, read only)
def chat_loop():
    chan = CFG['CHANNEL'].lower().lstrip('#')
    while True:
        try:
            s = socket.create_connection(('irc.chat.twitch.tv', 6667), timeout=300)
            s.sendall(f'CAP REQ :twitch.tv/tags\r\nPASS SCHMOOPIIE\r\nNICK justinfan{int(time.time())%80000+10000}\r\nJOIN #{chan}\r\n'.encode())
            log('Reading the chat of', chan); buf = b''
            while True:
                data = s.recv(4096)
                if not data: break
                buf += data
                while b'\r\n' in buf:
                    line, buf = buf.split(b'\r\n', 1); line = line.decode('utf-8', 'ignore')
                    if line.startswith('PING'): s.sendall(b'PONG :tmi.twitch.tv\r\n'); continue
                    m = re.match(r'^(?:@(\S+) )?:(\w+)!\S+ PRIVMSG #\S+ :(.*)$', line)
                    if not m: continue
                    tags, login, text = m.group(1) or '', m.group(2), m.group(3)
                    dn = (re.search(r'display-name=([^;]*)', tags) or [None, login])[1] or login
                    boss = login.lower() == chan or re.search(r'badges=[^;]*(broadcaster|moderator)', tags)
                    LIVE['chat'].append(time.time())
                    if boss and re.match(r'^!clip\b', text, re.I):
                        mm = re.match(r'^!clip\s+(\d{1,2})\b\s*(.*)$', text, re.I)
                        if mm: add_marker('chat', mm.group(2).strip(), max(8, min(60, int(mm.group(1)))))
                        else: add_marker('chat', text[5:].strip())
                        continue
                    sid = CUR['id']
                    if sid:
                        st = SESS_START.get(sid) or load_sess(sid)['start']; SESS_START[sid] = st
                        with LOCK, open(os.path.join(sdir(sid), 'chat.jsonl'), 'a', encoding='utf-8') as cf:
                            cf.write(json.dumps([round(time.time() - st, 2), dn, text[:200]]) + '\n')
        except Exception as e:
            time.sleep(5)
