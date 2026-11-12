# JelE Clipper part: log window, ffmpeg and settings. Loaded by clipper.py into one shared namespace, do not run on its own.

import collections
LOGBUF = collections.deque(maxlen=600)
def log(*a):
    print(time.strftime('[%H:%M:%S]'), *a, flush=True)
class _Tee:
    """keeps the last lines of the black window, so the app can show them (and you can copy them)"""
    def __init__(self, s): self.s = s; self.part = ''
    def write(self, x):
        try: self.s.write(x)
        except Exception: pass
        self.part += x
        while '\n' in self.part:
            ln, self.part = self.part.split('\n', 1)
            if ln.strip(): LOGBUF.append(ln)
    def flush(self):
        try: self.s.flush()
        except Exception: pass
    def __getattr__(self, k): return getattr(self.s, k)
if sys.stdout: sys.stdout = _Tee(sys.stdout)
if sys.stderr: sys.stderr = _Tee(sys.stderr)

# ---------------------------------------------------------------- ffmpeg
def ffmpeg_bin():
    if shutil.which('ffmpeg'): return 'ffmpeg'
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'
FF = ffmpeg_bin()
NOWIN = 0x08000000 if os.name == 'nt' else 0   # no console window pop-ups on Windows

def run(args, **kw):
    return subprocess.run([FF, '-hide_banner', '-loglevel', 'error'] + args, creationflags=NOWIN | (LOWPRIO_ if (CUR['id'] or STATE_LIVE()) else 0), **kw)

LOWPRIO_ = 0x00004000 if os.name == 'nt' else 0
def low_priority():
    """the whole app, and all ffmpeg and speech work it starts, runs below normal priority:
    your game, OBS and the stream always go first. on an idle pc this costs no speed."""
    try:
        if os.name == 'nt':
            import ctypes
            k = ctypes.windll.kernel32; k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)
        else: os.nice(5)
        return True
    except Exception: return False
def STATE_LIVE():
    try: return bool(STATE.get('live'))
    except NameError: return False

def probe_duration(path):
    p = subprocess.run([FF, '-hide_banner', '-i', path], capture_output=True, text=True, creationflags=NOWIN, errors='replace')
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', p.stderr)
    d = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    if d < 1:   # an OBS file without a duration in its header (crash, still being written): count it by decoding
        r = subprocess.run([FF, '-hide_banner', '-i', path, '-map', '0:a:0?', '-map', '0:v:0?', '-c', 'copy', '-f', 'null', '-'], capture_output=True, text=True, creationflags=NOWIN, errors='replace')
        ts = re.findall(r'time=(\d+):(\d+):([\d.]+)', r.stderr)
        if ts: h, mi, se = ts[-1]; d = int(h) * 3600 + int(mi) * 60 + float(se)
    return d
def probe_size(path):
    p = subprocess.run([FF, '-hide_banner', '-i', path], capture_output=True, text=True, creationflags=NOWIN)
    m = re.search(r'Video:.*?(\d{3,5})x(\d{3,5})', p.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (1920, 1080)

# ---------------------------------------------------------------- settings
def read_config_js():
    c = {'OBS_PORT': 4455, 'OBS_PASSWORD': '', 'CHANNEL': ''}
    p = os.path.join(ROOT, 'mascotte', 'config.js')
    try:
        s = open(p, encoding='utf-8').read()
        for k in ('OBS_PASSWORD', 'SE_JWT', 'CHANNEL', 'TEAM', 'HENRIK_KEY', 'RIOT_NAME', 'RIOT_TAG', 'REGION', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET', 'UPDATE_URL'):
            m = re.search(r'\b' + k + r'\s*:\s*"((?:[^"\\]|\\.)*)"', s) or re.search(r'\b' + k + r"\s*:\s*'((?:[^'\\]|\\.)*)'", s)
            if m: c[k] = re.sub(r'\\(.)', r'\1', m.group(1))
        m = re.search(r'OBS_PORT\s*:\s*(\d+)', s)
        if m: c['OBS_PORT'] = int(m.group(1))
    except Exception:
        log('config.js not found, using the default settings')
    return c
CFG = read_config_js()
def default_tag():
    ch = (CFG.get('CHANNEL') or '').strip().lstrip('#')
    return f'twitch.tv/{ch}' if ch else ''

DEFAULTS = {
    'cam': [0, 93, 539, 303],          # where your mascot cam sits in the recording (x, y, w, h) on a 1920x1080 canvas
    'game_x': 0.5,                      # centre of the gameplay crop, 0 = left, 1 = right
    'layout': 'split', 'cap_style': 'jele',                  # split = cam on top + gameplay, frame = whole stream frame on blurred bg, gameonly, landscape
    'clip_len': 30,                     # longest clip in seconds; clips end where a sentence ends, so many are shorter
    'max_clips': 12,
    'captions': True,
    'whisper_model': 'auto',            # auto = large-v3 with an NVIDIA card, otherwise small.en to scan and medium.en for captions
    'language': 'en',                   # you stream in English
    'smart': True,                      # listen to what is said around each moment to rank it and to cut on sentences
    'chat_delay': 6,                    # chat reacts a few seconds after the moment (stream delay + typing)
    'mic_track': 0,                     # 0 = automatic (finds your mic track), -1 = all audio mixed, 1..6 = that audio track
    'friends_track': 0,                 # plan F2.3: OBS track with your friends (Discord). 0 = none. their words get their own colour
    'friends_caps': True,               # show what your friends say in the captions
    'learn_timing': {'lead': 0.0, 'tail': 0.0},   # learned from your feedback: start earlier/later, end later/earlier (seconds)
    'sounds': True, 'vision': True, 'vision_auto_done': False, 'face_follow': True, 'voice_up': True,
    'loud': True,                       # make the short as loud as other TikToks/Shorts
    'auto_shorts': True,                # make shorts of the best moments by itself after a stream (they land in the inbox)
    'auto_shorts_n': 3,
    'cam_auto': True,                   # read where the cam frame sits from OBS at the start of every recording
    'auto_zoom': True,                  # punch in on the gameplay when you shout ("no way", "let's go") or press the clip button
    'progress_bar': False,              # thin orange bar at the top that fills up (people watch till the end)
    'endcard': True,                    # last 2 seconds: "follow for more" with your twitch
    'cap_scale': 1.0,                   # caption size
    'hashtags': '#valorant #valorantclips #valorantmoments #twitch #gaming #fyp',
    'phone': False,                     # open your shorts on your phone over wifi (QR code in the app)
    'phone_key': '',
    'jumpcut': True,                    # cut out dead air (no talking and quiet game) inside a clip
    'sfx': True,                        # a soft boom when it zooms in, a whoosh between montage clips
    'matchdata': True,                  # use your Valorant matches (HenrikDev API) to find multikills, aces and clutches
    'match_offset': 0,                  # seconds; move match events earlier (-) or later (+) if they land off
    'twitch_clips': True,               # clips viewers made on Twitch count as strong moments (needs TWITCH_CLIENT_ID/SECRET in config.js)
    'ntfy': False, 'ntfy_topic': '',    # push messages on your phone through the free ntfy app
    'presets': [],                      # your saved styles
    'fx_teaser': True,                  # start with a 1 s peek at the best part ("wait for it")
    'fx_replay': True,                  # slow motion replay of the best part at the end
    'fx_killfeed': True,                # killfeed big in view after your kills (needs matchdata)
    'fx_stickers': True,                # ACE / CLUTCH stamps from matchdata, CLIP THAT etc
    'voice_clean': False,               # filter noise out of the sound
    'kf_box': [1440, 80, 460, 170],     # where the killfeed is on a 1920x1080 recording
    'highlight_min': 8,                 # length of the YouTube highlights video in minutes
    'auto_preset': '',                  # style used for the automatic shorts
    'v': 3,
    'tag': '',                          # empty = twitch.tv/ + your channel from config.js
    'encoder': 'auto',                  # auto tries NVIDIA, AMD and Intel video encoding, then normal x264
    # 6.0
    'update_repo': 'JelE123/JelE-clipper',   # GitHub repository for updates
    'seen_version': '',                 # last version whose "what is new" you saw
    'safe_mode': False,                 # start without effects (for when something breaks after an update)
    'remux': True, 'remux_drop_mkv': True,   # MKV recordings become MP4 after the stream; the MKV goes to the recycle bin
    'pause_live': True,                 # heavy work waits while you stream or record
    'parallel': 'auto',                 # how many shorts at the same time (auto = 2 on 8+ cores)
    'proxy': True,                      # light 720p work copy for the editor
    'wizard_done': False, 'tour_done': False, 'adv': False,
    'phone_used': 0, 'phone_on_at': 0,
    # 6.1
    'vocab': '',                        # your own words for the captions (names of teammates, emotes)
    'game_words': True,                 # put Valorant and game words in their right spelling (gamewords.py)
    'speech_process': True,             # the speech model runs in its own process: if it crashes, the app keeps running
    'speech_engine': 'auto',            # auto | gpu (graphics card of any brand, after installing support) | cpu
    'learn_look': True,                 # the editor starts with your last look per game; what you pick 10 times in a row, the automatic shorts use too
    'cap_fillers': True,                # uh, um and ehm are left out of the captions
    'live_listen': True,                # listen along during the stream (strong pc only), so the moments are there right after
    'pause_busy': True,                 # new heavy work waits a moment when your pc is already at its limit
    'low_priority': True,               # the app works below normal priority, so your game and stream always go first
    'default_game': 'valorant',         # the game when nothing else tells which game a stream is
    'game_detect': True,                # find out by itself which game you play (PC, OBS, Twitch category, what you say)
    'game_hashtags': {},                # your own hashtags per game: {"minecraft": "#minecraft #fyp"}
    'fixes': [],                        # corrections that are always applied: [["jet", "Jett"], ...]
    'cap_anim': 'pop',                  # pop, bounce, type (word by word appears), word (one big word), none
    'bleep': False,                     # beep out swear words
    'frame_bg': 'blur', 'frame_round': False, 'frame_border': False,   # whole-picture layout
    'divider': True,                    # orange line between cam and game
    'snap_words': True,                 # clip edges snap to the start or end of a word
    # 6.2
    'live_clip': True,                  # Clip button during the stream: OBS replay buffer, short right away
    'live_len': 25,                     # seconds before the press
    'block_scenes': '',                 # scenes where clips are ignored (empty = Starting soon, BRB, Pause, End...)
    'platform': 'tiktok',               # main platform: length and safe zones
    'platforms': ['tiktok', 'shorts', 'reels'],
    'tags_tiktok': '', 'tags_shorts': '', 'tags_reels': '',
    'name_tpl': '{title}',              # file names: {title} {date} {time} {layout} (old Dutch names still work)
    'q_min': 70,                        # below this Postklaar-score a short gets a warning
    'safe_zone': '',                    # editor: show the safe zones of this platform
    # 6.3
    'blocked_kinds': [],                # "not like this again"
    'tips_done': [], 'week_goal': 0, 'week_report': True, 'report_sent': 0,
    # 6.4
    'brands': [], 'brand_default': 'jele',   # brand profiles for the videos (the app itself stays JelE)
    'team_dir': '', 'team_name': '', 'team_auto': False,   # shared team folder (OneDrive, Google Drive)
}
SETTINGS_F = os.path.join(DATA, 'instellingen.json')
def load_settings():
    s = dict(DEFAULTS)
    try: saved = json.load(open(SETTINGS_F, encoding='utf-8'))
    except Exception: saved = {}
    if saved.get('v', 1) < 2:   # 2.0: the automatic parts are on by default
        for k in ('auto_shorts', 'cam_auto', 'auto_zoom', 'v'): saved.pop(k, None)
    if saved.get('v', 1) < 3:   # 6.0.1: updates come from your GitHub repository
        if not saved.get('update_repo'): saved.pop('update_repo', None)
        saved['v'] = 3
    s.update(saved)
    return s
def save_settings(s):
    json.dump(s, open(SETTINGS_F, 'w', encoding='utf-8'), indent=2)
SET = load_settings()
