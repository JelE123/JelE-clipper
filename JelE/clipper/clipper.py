# JelE Clipper
# Logs your stream (clip markers + chat) while you record, finds the best moments afterwards
# and turns them into vertical shorts (9:16) with your mascot cam on top, gameplay below and captions.
# Start it with start.bat, then open http://localhost:8765
import os, re, sys, json, time, glob, math, uuid, base64, hashlib, socket, shutil, threading, subprocess, traceback
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1'); os.environ.setdefault('HF_HUB_VERBOSITY', 'error')
import warnings, logging; warnings.filterwarnings('ignore', module='huggingface_hub'); logging.getLogger('huggingface_hub').setLevel(logging.ERROR)
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, 'data')
SESS = os.path.join(DATA, 'sessies')
OUT = os.path.join(HERE, 'shorts')
for d in (DATA, SESS, OUT): os.makedirs(d, exist_ok=True)
PORT = 8765
VERSION = '6.17'

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
    fx['peak'] = round(peak, 2) if peak is not None else None
    if peak is not None and why_peak in ('event', 'shout', 'marker') and dur > 10:
        if SET.get('fx_teaser', True) and peak > 5: fx['teaser'] = {'t': round(max(0, peak - 1.1), 2), 'len': 0.9, 'text': ''}
        if SET.get('fx_replay', True) and peak < dur - 0.4: fx['replay'] = {'a': round(max(0, peak - 1.8), 2), 'b': round(min(dur, peak + 0.7), 2), 'speed': 0.5}
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
            out.append({k: s.get(k) for k in ('id', 'title', 'start', 'stop', 'path', 'status', 'duration', 'kind', 'parent', 'imported')} | {'game': game_quick(s)['id'], 'n_markers': len(s.get('markers', [])),  'n_moments': len(s.get('moments', [])), 'n_shorts': per.get(s.get('id'), 0), 'top': (s.get('moments') or [{}])[0].get('id')})
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
        if a:
            sec = base64.b64encode(hashlib.sha256((CFG['OBS_PASSWORD'] + a['salt']).encode()).digest()).decode()
            d['authentication'] = base64.b64encode(hashlib.sha256((sec + a['challenge']).encode()).digest()).decode()
        self.ws.send(json.dumps({'op': 1, 'd': d}))
        msg = json.loads(self.ws.recv())
        if msg.get('op') != 2: raise Exception('OBS refused the connection (is OBS_PASSWORD in config.js right?)')
        self.ok = True; log('Connected to OBS')
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

# ---------------------------------------------------------------- finding the moments
HYPE = re.compile(r'\b(lul|kekw|omegalul|lmao+|lmfao|lol+|w+|clip|clipit|clip it|no way|wtf|what|omg|pog+|poggers|holy|ace|clutch|insane|crazy|nice+|gg|sheesh|bro|nah+|yoo+|goated|cracked)\b|\?{3,}|!{3,}', re.I)
# things you say when something clip-worthy happens
SAY_HYPE = GameRe(r"\b(no+ way|oh my god|oh my gosh|omg|let'?s go+|lets go+|what the|wha+t|bro+|yo+|holy|insane|crazy|ace|clutch|one tap|onetap|no+|yes+|wow|sheesh|are you kidding|are you serious|how did|did you see|i can'?t believe|nah+|wait|oh no|get out|sick|beautiful|perfect|unreal|disgusting|nasty|cracked)\b", 'hype')
SAY_STRONG = GameRe(r"\b(no+ way|oh my god|oh my gosh|let'?s go+|lets go+|what the|holy|insane|crazy|ace|clutch|one tap|are you kidding|are you serious|i can'?t believe|unreal|disgusting|cracked|sheesh)\b", 'strong')
SAY_LAUGH = re.compile(r'\b(ha(ha)+|he(he)+|lmao|lol)\b', re.I)
try: import gamewords             # agents, abilities, maps, weapons, callouts and stream talk (gamewords.py)
except Exception: gamewords = None

def vocab_prompt(model=None):
    """the built-in Valorant words plus your own word list (names of teammates, emotes).
    The speech model only reads the last ~220 word pieces of this text, so your own words go last
    and the built-in list is shortened from the front (least important words first) until it fits."""
    own = [w.strip() for w in re.split(r'[,\n]+', SET.get('vocab') or '') if w.strip()]
    mine = ', '.join(['JelE'] + own)[-450:]
    base = gamewords.prompt_words(cur_game()) if gamewords else ['Valorant', 'Jett', 'Reyna', 'Raze', 'Sova', 'Omen', 'Killjoy', 'Vandal', 'Phantom', 'spike', 'defuse', 'ult']
    tok = getattr(model, 'hf_tokenizer', None)
    def fits(txt):
        if tok is not None:
            try: return len(tok.encode(' ' + txt, add_special_tokens=False).ids) <= 215
            except Exception: pass
        return len(txt) <= 580
    while base and not fits(', '.join(base) + ', ' + mine): base = base[1:]
    return ', '.join(base + [mine])

def apply_fixes(words, game=None):
    """the right spelling of game words, then your own corrections ("jet" is always "Jett"), on every transcript"""
    if gamewords and words and SET.get('game_words', True):
        try: words = gamewords.fix(words, UNCLEAR, game or cur_game())
        except Exception: traceback.print_exc()
    rules = [(str(a).strip(), str(b).strip()) for a, b in (SET.get('fixes') or []) if str(a).strip()]
    if not rules or not words: return words
    out = []
    for w in words:
        t = w[2]
        for a, b in rules:
            if re.fullmatch(re.escape(a) + r"([.,!?']*)", t, re.I): t = b + re.sub(r'^' + re.escape(a), '', t, flags=re.I)
        out.append((w[0], w[1], t) if len(w) == 3 else tuple([w[0], w[1], t] + list(w[3:])))
    return out

SWEAR = re.compile(r"^(fuck\w*|f\*+\w*|motherfuck\w*|shit\w*|bullshit|bitch\w*|asshole\w*|cunt\w*|dick(head)?s?|pussy|whore|slut|nigg\w*|fag\w*|retard\w*|kanker\w*|kut|tering|tyfus|hoer)\W*$", re.I)
def censor(t):
    m = re.match(r"^(\W*)(\w)(\w*)(\W*)$", t)
    return (m.group(1) + m.group(2) + '*' * max(2, len(m.group(3))) + m.group(4)) if m else t

def audio_env(path, step=0.5):
    """loudness per half second (dB) in the voice band, read straight from ffmpeg"""
    import numpy as np
    sr = 8000; n = int(sr * step)
    amap = mic_map(path)
    p = subprocess.Popen([FF, '-hide_banner', '-loglevel', 'error', '-i', path] + amap + ['-vn', '-ac', '1', '-ar', str(sr), '-af', 'highpass=f=250,lowpass=f=3400', '-f', 's16le', '-'],
                         stdout=subprocess.PIPE, creationflags=NOWIN)
    out = []; rest = b''
    while True:
        b = p.stdout.read(n * 2 * 240)
        if not b: break
        b = rest + b; k = len(b) // (n * 2) * (n * 2); rest = b[k:]
        a = np.frombuffer(b[:k], dtype=np.int16).astype(np.float32).reshape(-1, n) / 32768.0
        out.extend((20 * np.log10(np.sqrt((a ** 2).mean(axis=1)) + 1e-6)).tolist())
    p.wait()
    return out

def zscore_rolling(x, win, floor=1e-3, prop=0.0):
    import numpy as np
    x = np.asarray(x, dtype=np.float32)
    if len(x) == 0: return x
    from numpy.lib.stride_tricks import sliding_window_view
    win = max(3, min(win, len(x)))
    w = sliding_window_view(x, win)                       # only real windows, no copied edge values
    idx = np.clip(np.arange(len(x)) - win // 2, 0, len(w) - 1)   # at the start/end use the first/last full window
    med_w = np.median(w, axis=1); mad_w = np.median(np.abs(w - med_w[:, None]), axis=1)
    med = med_w[idx]; mad = mad_w[idx]
    return (x - med) / np.maximum(1.4826 * mad, np.maximum(floor, prop * np.abs(med)))

def audio_tracks(path):
    """the audio tracks in a recording: [{'n': 1, 'title': 'Mic'}, ...]. OBS writes the track names you gave them into the file"""
    p = subprocess.run([FF, '-hide_banner', '-i', path], capture_output=True, text=True, creationflags=NOWIN, errors='replace')
    out = []; lines = p.stderr.splitlines()
    for i, ln in enumerate(lines):
        if re.search(r'Stream #0:\d+.*: Audio:', ln):
            title = ''
            for nx in lines[i + 1:i + 6]:
                if 'Stream #' in nx: break
                m = re.match(r'\s+(title|handler_name)\s*:\s*(.+)', nx)
                if m and not title and m.group(2).strip().lower() not in ('soundhandler', 'sound handler'): title = m.group(2).strip()
            out.append({'n': len(out) + 1, 'title': title})
    return out

def silence_ratio(path, track, at):
    """how much of 20 seconds on this track is (almost) silent. a mic with noise suppression is quiet a lot, game audio almost never"""
    import numpy as np
    r = subprocess.run([FF, '-v', 'error', '-ss', f'{at:.1f}', '-t', '20', '-i', path, '-map', f'0:a:{track-1}', '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', '-'],
                       capture_output=True, creationflags=NOWIN)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < 8000: return None
    x = x[:len(x) // 800 * 800].reshape(-1, 800)
    db = 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-6)
    return float((db < -48).mean())

_MIC = {}
def find_mic(path):
    """which audio track is only your voice. 0 = none found, use everything"""
    if path in _MIC: return _MIC[path]
    tr = audio_tracks(path); pick = 0; why = 'only 1 audio track, using all audio'
    named = [t for t in tr if re.search(r'\b(mic|microfoon|microphone|voice|stem|me)\b', t['title'], re.I)]
    if named: pick = named[0]['n']; why = f'track {pick} is called "{named[0]["title"]}"'
    elif len(tr) >= 2:
        dur = probe_duration(path) or 60
        spots = [dur * f for f in (0.25, 0.5, 0.75)]
        sil = {}
        for t in tr[1:]:   # track 1 is (almost) always the full mix
            v = [silence_ratio(path, t['n'], a) for a in spots]; v = [x for x in v if x is not None]
            if v: sil[t['n']] = sum(v) / len(v)
        full = [silence_ratio(path, 1, a) for a in spots]; full = sum(x for x in full if x is not None) / max(1, len([x for x in full if x is not None]))
        if sil:
            best = max(sil, key=sil.get)
            if 0.25 <= sil[best] <= 0.97 and sil[best] > full + 0.2: pick = best; why = f'track {best} is often quiet, that looks like your mic'
            else: why = 'no separate mic track found, using all audio and filtering out voicelines'
    _MIC[path] = (pick, why, tr)
    log('Audio:', why)
    return _MIC[path]

def mic_map(path):
    mt = int(SET.get('mic_track') or 0)
    if mt == 0: mt = find_mic(path)[0]
    return ['-map', f'0:a:{mt-1}'] if mt > 0 else []

_WAVMIC = {}
_AF_OK = {'ok': True}
def extract_wav(path, start, dur, out):
    amap = mic_map(path); _WAVMIC[out] = bool(amap)
    base = ['-y', '-ss', f'{max(0, start):.2f}', '-t', f'{dur:.2f}', '-i', path] + amap + ['-vn']
    tail = ['-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', out]
    if _AF_OK['ok']:
        # clean the voice a bit: rumble out, quiet words up. helps the speech model
        r = run(base + ['-af', 'highpass=f=70,lowpass=f=7800,dynaudnorm=f=200:g=11'] + tail, capture_output=True, text=True, errors='replace')
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000: return True
        _AF_OK['ok'] = False; log('Audio filter does not work with this ffmpeg, continuing without it:', (r.stderr or '').strip()[-200:])
    r = run(base + tail, capture_output=True, text=True, errors='replace')
    if r.returncode != 0 or not os.path.exists(out):
        if amap:   # the chosen track does not work: use all audio
            _MIC[path] = (0, 'mic track does not work', _MIC.get(path, (0, '', []))[2])
            r = run(['-y', '-ss', f'{max(0, start):.2f}', '-t', f'{dur:.2f}', '-i', path, '-vn'] + tail, capture_output=True, text=True, errors='replace')
        if r.returncode != 0 or not os.path.exists(out):
            log('Getting the audio out of the recording failed:', (r.stderr or '').strip()[-300:]); return False
    return True

def sentence_cut(words, peak, L, dur):
    """clip start and end on natural pauses: start before the moment, end once the reaction is over"""
    gaps = []   # (time, size) pauses between words
    for a, b in zip(words, words[1:]):
        if b[0] - a[1] >= 0.45: gaps.append((a[1], b[0] - a[1]))
    # end: first real pause 2-12 s after the peak
    end = None
    for g, size in gaps:
        if peak + 2 <= g <= peak + 12 and size >= 0.6: end = g + 0.8; break
    if end is None: end = peak + 6
    # start: the earliest pause that still fits in L, but at least 12 s before the end
    start = None
    for g, size in gaps:
        s0 = g + min(size, 0.6) - 0.25
        if end - L <= s0 <= end - 12 and s0 <= peak - 3: start = s0; break
    if start is None: start = end - min(L, max(16, (end - peak) + 14))
    return max(0, start), min(dur, end)

def analyse(sid):
    import numpy as np
    s = load_sess(sid)
    path = s.get('path')
    if not path or not os.path.exists(path):
        s['status'] = 'recording not found'; save_sess(s); log('Recording not found:', path); return
    s['status'] = 'analyseren'; save_sess(s); log('Analysing:', os.path.basename(path)); prog('Checking audio and chat', 2)
    GAME_TL.v = game_quick(s)['id']
    dur = probe_duration(path); step = 0.5
    try: env = audio_env(path, step)
    except Exception: log('Audio analysis failed'); traceback.print_exc(); env = []
    if env and max(env) < -70:   # the chosen track is silent: fall back to all audio
        log('The chosen audio track is silent, using all audio'); _MIC[path] = (0, 'mic track silent', _MIC.get(path, (0, '', []))[2]); env = audio_env(path, step)
    dur = max(dur, len(env) * step)
    if dur < 5:
        s['status'] = 'recording too short or unreadable'; save_sess(s); log('Could not read the length of the recording:', path); return
    s['duration'] = dur; log(f'Recording is {fmt(dur)} long')
    T = int(dur / step) + 1
    score = np.zeros(T, dtype=np.float32); why = [dict() for _ in range(T)]
    # 1. getting loud (voice band). the first and last seconds are skipped: starting the recording is not a moment
    try:
        if env:
            z = zscore_rolling(env, int(90 / step), floor=3.0)
            z = np.convolve(np.clip(z, 0, 8), np.ones(4) / 4, mode='same')
            skip_a, skip_b = int(10 / step), len(z) - int(4 / step)
            for i in range(min(T, len(z))):
                if i < skip_a or i > skip_b: continue
                if z[i] > 2.0: score[i] += 0.7 * (z[i] - 2.0); why[i]['audio'] = 1
    except Exception: log('Audio analysis failed'); traceback.print_exc()
    # 1b. what you say, over the whole recording (always with an NVIDIA card or a strong processor, else up to 30 min)
    ALL = []
    if SET.get('smart', True) and whisper_ok() and (dur <= 1800 or has_cuda() or (CORES >= 8 and dur <= 5 * 3600)):
        work0 = os.path.join(sdir(sid), 'tmp_full'); os.makedirs(work0, exist_ok=True)
        chunk = 300.0; a0 = 0.0; nchunks = int(math.ceil(dur / chunk)); UNSURE = []
        while a0 < dur:
            s = load_sess(sid); s['status'] = f'luisteren ({int(a0 // chunk) + 1}/{nchunks})'; save_sess(s); prog('Listening to the whole stream', 5 + 70 * a0 / dur)
            wav = os.path.join(work0, 'c.wav'); extract_wav(path, a0, min(chunk + 2, dur - a0), wav)
            try:
                ALL += [(round(a + a0, 2), round(b + a0, 2), w) for a, b, w in transcribe(wav, 'scan', lambda f, a0=a0: prog(None, 5 + 70 * min(dur, a0 + f * chunk) / dur)) if a + a0 >= (ALL[-1][0] + 0.01 if ALL else 0)]
                UNSURE += [round(u + a0, 2) for u in getattr(UNSURE_TL, 'v', [])]
            except Exception: traceback.print_exc()
            a0 += chunk
        shutil.rmtree(work0, ignore_errors=True)
        try:
            json.dump(ALL, open(os.path.join(sdir(sid), 'transcript.json'), 'w', encoding='utf-8'))
            sg_ = speech_game(ALL)
            if sg_:
                s_ = load_sess(sid); s_['game_speech'] = sg_; save_sess(s_); GAME_TL.v = game_quick(s_)['id']
            json.dump(sorted(set(UNSURE)), open(os.path.join(sdir(sid), 'twijfel.json'), 'w', encoding='utf-8'))
        except Exception: pass
        for k, (a, b, w) in enumerate(ALL):
            i = int(a / step)
            if not (0 <= i < T): continue
            phrase = ' '.join(x[2] for x in ALL[k:k + 3] if x[0] - a < 1.5)   # catches "no way", "oh my god"
            m1 = SAY_STRONG.match(re.sub(r'[^\w\' ]', '', phrase)) or (SAY_STRONG.search(w) and SAY_STRONG.search(w))
            v = 2.0 if m1 else 1.5 if SAY_LAUGH.search(w) else 0.8 if SAY_HYPE.search(w) else 0
            if m1: w = m1.group(0)
            if v:
                for j in range(max(0, i - 2), min(T, i + 3)):
                    score[j] += v * (1 - abs(j - i) * 0.25)
                    if v > why[j].get('sv', 0): why[j]['say'] = w; why[j]['sv'] = v
        # talking fast and a lot at once is a reaction too
        cnt = np.zeros(T, dtype=np.float32)
        for a, b, w in ALL:
            i = int(a / step)
            if 0 <= i < T: cnt[i] += 1
        rate = np.convolve(cnt, np.ones(int(6 / step)), mode='same') / 6.0
        for i in range(T):
            if rate[i] > 3.2: score[i] += (rate[i] - 3.2) * 0.8
    # 2. chat going off (shifted back: chat reacts a few seconds after the moment)
    chat = load_chat(sid); delay = float(SET.get('chat_delay', 6))
    if chat:
        cnt = np.zeros(T, dtype=np.float32); hype = np.zeros(T, dtype=np.float32); users = [set() for _ in range(T)]
        for t, u, msg in chat:
            i = int((t - delay) / step)
            if 0 <= i < T:
                cnt[i] += 1; users[i].add(u)
                if HYPE.search(msg): hype[i] += 1
        k = int(10 / step)
        uniq = np.array([len(x) for x in users], dtype=np.float32)
        c10 = np.convolve(cnt, np.ones(k), mode='same'); h10 = np.convolve(hype, np.ones(k), mode='same'); u10 = np.convolve(uniq, np.ones(k), mode='same')
        zc = zscore_rolling(c10, int(240 / step), floor=2.0, prop=0.35)
        for i in range(T):
            v = max(0, zc[i] - 1.5) + 0.6 * h10[i] + 0.15 * max(0, u10[i] - 3)
            if v > 0.5: score[i] += v; why[i]['chat'] = int(c10[i]); why[i]['hype'] = int(h10[i])
    # 2b. your real matches: multikills, aces, clutches
    md = match_events(s) if gprof().get('matchdata') else None
    if md:
        s = load_sess(sid); s['game_events'] = md['events']; s['game_kills'] = md['kills']; save_sess(s)
        for e in md['events']:
            i0, i1 = int(max(0, e['t0'] - 2) / step), int(e['t'] / step)
            for j in range(max(0, i0), min(T, i1 + int(2 / step))):
                score[j] += e['strength']; why[j]['game'] = e
    # 2c. Twitch clips your viewers made
    tcl = twitch_clip_times(s)
    if tcl:
        s = load_sess(sid); s['twitch_clips'] = tcl; save_sess(s)
        for c_ in tcl:
            i = int(c_['t'] / step)
            for j in range(max(0, i - int(6 / step)), min(T, i + int(3 / step))):
                score[j] += 9; why[j]['tclip'] = c_
    # 2d. you said "clip that" / "clip it": counts like the clip button
    said_clip = []
    for i_, w in enumerate(ALL):
        ph = ' '.join(x[2] for x in ALL[i_:i_ + 2]).lower()
        if re.match(r"clip (that|it|this)\b", re.sub(r"[^\w ]", '', ph)) and (not said_clip or w[0] - said_clip[-1] > 10): said_clip.append(w[0])
    if said_clip:
        s = load_sess(sid); have = [m['t'] for m in s.get('markers', [])]
        for t_ in said_clip:
            if not any(abs(t_ - 2 - h) < 8 for h in have): s.setdefault('markers', []).append({'t': round(t_ - 2, 2), 'src': 'stem', 'note': ''})
        save_sess(s); log(f'You said "clip that" {len(said_clip)}x, those count as the Clip button')
    # talk moments: stretches where you talk a lot and people laugh (for the highlights video)
    if ALL:
        talk = []; tw_ = 30.0; t_ = 0.0
        while t_ < dur - tw_:
            seg = [w for w in ALL if t_ <= w[0] < t_ + tw_]; txt = ' '.join(w[2] for w in seg)
            sc_ = len(seg) / tw_ + 1.5 * len(SAY_LAUGH.findall(txt)) + 0.5 * len(SAY_HYPE.findall(txt))
            talk.append((round(sc_, 2), round(t_, 1))); t_ += 10.0
        talk.sort(reverse=True); picked = []
        for sc_, t_ in talk:
            if sc_ < 2.0 or len(picked) >= 12: break
            if all(abs(t_ - p_) > 35 for _, p_ in picked): picked.append((sc_, t_))
        s = load_sess(sid); s['talk'] = [{'a': t_, 'b': t_ + tw_, 'score': sc_} for sc_, t_ in picked]; save_sess(s)
    # 3. your own clip markers count the most
    for m in s.get('markers', []):
        i = int(m['t'] / step)
        for j in range(max(0, i - int(8 / step)), min(T, i + 1)):
            score[j] += 12; why[j]['marker'] = m.get('src', 'knop')
    # rough candidates
    L = float(SET['clip_len'])
    want = int(SET['max_clips'])
    smart = SET.get('smart', True) and whisper_ok()
    order = np.argsort(-score); taken = []; cands = []
    for i in order:
        if len(cands) >= (want * 2 + 4 if smart else want): break
        if score[i] < 1.0 and (len(cands) >= min(3, int(dur // 90)) or score[i] < 0.35): break   # a calm stream still gets a few to choose from
        t = i * step
        if any(abs(t - u) < L * 0.8 for u in taken): continue
        taken.append(t)
        w = why[i]; mk = 'marker' in w
        if mk: t = min((m['t'] for m in s.get('markers', [])), key=lambda x: abs(x - t)) - 2
        reasons = []
        g = w.get('game')
        if g: reasons.append(f"{g['label']} in round {g['round']}" + (f" on {g['map']}" if g.get('map') else '')); t = g['t'] - 1
        if w.get('tclip'): reasons.append(f"Twitch clip by {w['tclip']['by'] or 'a viewer'}")
        if mk: reasons.append({'paneel': 'Clip button', 'sneltoets': 'Clip hotkey', 'chat': '!clip in chat', 'website': 'Clip button', 'streamdeck': 'Stream Deck', 'stem': 'you said "clip that"'}.get(w['marker'], 'Clip button'))
        if w.get('chat'): reasons.append(f"chat went off ({w['chat']} messages in 10 sec)")
        if w.get('hype'): reasons.append(f"{w['hype']}x LUL, W, clip and the like")
        if w.get('audio'): reasons.append('it suddenly got loud')
        if w.get('say'): reasons.append(f'you said "{w["say"].strip(".,!?")}"')
        cands.append({'id': uuid.uuid4().hex[:8], 't': round(t, 1), 'score': round(float(score[i]), 1), 'reasons': reasons or ['standout moment'], 'marker': mk, 'game': g})
    # fine pass: listen to what you say around each moment
    if smart and cands:
        s['status'] = f'luisteren (0/{len(cands)})'; save_sess(s)
        work = os.path.join(sdir(sid), 'tmp_an'); os.makedirs(work, exist_ok=True)
        for n, c in enumerate(cands):
            a0 = max(0, c['t'] - L - 4); a1 = min(dur, c['t'] + 16)
            if ALL: words = [w for w in ALL if a0 <= w[0] <= a1]
            else:
                wav = os.path.join(work, 'w.wav'); extract_wav(path, a0, a1 - a0, wav)
                try: words = [(round(a + a0, 2), round(b + a0, 2), w) for a, b, w in transcribe(wav, 'scan')]
                except Exception: traceback.print_exc(); words = []
            near = [w for w in words if c['t'] - 8 <= w[0] <= c['t'] + 8]
            txt = ' '.join(w[2] for w in near)
            hy = len(SAY_HYPE.findall(txt)); la = len(SAY_LAUGH.findall(txt))
            rate = len(near) / 16.0
            st_ = len(SAY_STRONG.findall(txt))
            boost = 0 if ALL else 0.5 * hy + 1.0 * st_ + 1.2 * la + max(0, rate - 2.2) * 0.8   # with the full transcript this is already in the score
            c['score'] = round(c['score'] + boost, 1)
            if hy and not any(r.startswith('you said') for r in c['reasons']): c['reasons'].append(f'you reacted ("{SAY_HYPE.search(txt).group(0)}")')
            if la: c['reasons'].append('there was laughing')
            # peak = your last hype word near the moment, else the moment itself
            hw = [w for w in near if SAY_HYPE.search(w[2]) or SAY_LAUGH.search(w[2])]
            peak = hw[-1][0] if hw else c['t']
            if c['marker']: peak = min(peak, c['t'] + 1)
            if c.get('game'): peak = max(peak, c['game']['t'] + 1)
            st, en = sentence_cut(words, peak, L, dur) if words else (max(0, c['t'] - L * 0.7), min(dur, c['t'] + L * 0.3))
            if c.get('game'):   # the whole play must be in it: from the first kill to just after the last
                st = max(0, min(st, c['game']['t0'] - 4)); en = min(dur, max(en, c['game']['t'] + 2.5))
                if en - st > L + 15: st = max(0, en - L - 15)
            c['start'], c['end'] = round(st, 1), round(en, 1)
            c['words'] = [w for w in words if st - 1 <= w[0] <= en + 1]
            c['text'] = ' '.join(w[2] for w in c['words'])[:400]
            c['title'] = title_from(near, hw) or fallback_title(c, s)
            c['hooks'] = hook_options(near, hw, c, s)
            s = load_sess(sid); s['status'] = f'luisteren ({n+1}/{len(cands)})'; save_sess(s); prog('Picking the moments', 75 + 23 * (n + 1) / len(cands))
        shutil.rmtree(work, ignore_errors=True)
    else:
        for c in cands:
            if c['marker']: st = c['t'] + 7 - L
            else: st = c['t'] - L * 0.72
            c['start'] = round(max(0, st), 1); c['end'] = round(min(dur, max(0, st) + L), 1)
    try: story_bonus(ALL, cands, s)
    except Exception: traceback.print_exc()
    for c in cands:
        tm_ = taste_mult(c['reasons'], (c.get('end') or 0) - (c.get('start') or 0) or None)
        c['score'] = round(c['score'] * tm_, 1)
        if tm_ >= 1.2: c['reasons'].append('you often keep clips like this')
        if not c.get('title'): c['title'] = fallback_title(c, load_sess(sid))
        if not c.get('hooks'): c['hooks'] = hook_options([], [], c, load_sess(sid))   # learn from what you kept before
    # no near-copies: when two clips mostly overlap, keep the best one (and its reasons)
    best = []
    for c in sorted(cands, key=lambda c: -c['score']):
        a1, b1 = c.get('start', c['t'] - L * 0.7), c.get('end', c['t'] + L * 0.3)
        dup = next((d for d in best if min(b1, d.get('end', d['t'] + L * 0.3)) - max(a1, d.get('start', d['t'] - L * 0.7)) > 0.4 * min(b1 - a1, d.get('end', 0) - d.get('start', 0) or L)), None)
        if dup: dup['reasons'] = list(dict.fromkeys(dup['reasons'] + c['reasons']))[:5]; continue
        best.append(c)
    moments = sorted(best[:want], key=lambda m: m['t'])
    for m in moments:
        th = os.path.join(sdir(sid), f"thumb_{m['id']}.jpg")
        run(['-y', '-ss', str(m['t']), '-i', path, '-frames:v', '1', '-vf', 'scale=480:-2', th])
    s = load_sess(sid); s['moments'] = moments + [m for m in s.get('moments', []) if m.get('manual')]; s['duration'] = dur; s['status'] = 'klaar'; save_sess(s)   # keep clips you picked yourself
    log(f'Done: {len(moments)} moments found in {s["title"]}')
    made = [(float(x.get('start') or 0), float(x.get('end') or 0)) for x in s.get('shorts', [])]
    def has_short(m):   # searching again must not make the same shorts twice
        return any(min(m['end'], e) - max(m['start'], a_) > 0.5 * max(1.0, m['end'] - m['start']) for a_, e in made)
    auto_pick = [m for m in sorted(moments, key=lambda m: -m['score']) if not has_short(m)][:int(SET.get('auto_shorts_n', 3))]
    if SET.get('auto_shorts'):
        for m in auto_pick:
            pre = next((p for p in SET.get('presets', []) if p.get('name') == SET.get('auto_preset')), {})
            JOBS.put(('render', {'sid': sid, 'start': m['start'], 'end': m['end'], 'title': m.get('title', ''), 'hook': m.get('title', ''), 'captions': SET['captions'], 'mid': m['id'], 'auto': True,
                                 **{k: v for k, v in pre.items() if k in ('layout', 'style', 'cap_scale', 'cap_y', 'progress', 'endcard', 'zoom', 'jumpcut', 'sfx', 'cam_h', 'game_x')}}))
        n_auto = len(auto_pick)
        if n_auto: log(f'Making the best {n_auto} shorts automatically, they will show up in your inbox'); STATE['auto_left'] = STATE.get('auto_left', 0) + n_auto
    notify('Stream checked', f'{len(moments)} moments found in {s["title"]}.' + (' Making your shorts now.' if SET.get('auto_shorts') and auto_pick else ''))

def fallback_title(c, s=None):
    """a hook when nothing clear was said: your !clip note, or what made the moment stand out"""
    if c.get('game'):
        g = c['game']; return f"{g['label']}{' WITH THE ' + g['weapon'].upper() if g.get('weapon') and g['label'] in ('ACE', '4K') else ''}"[:40]
    if c.get('marker') and s:
        near = [m for m in s.get('markers', []) if abs(m['t'] - c['t']) < 12 and (m.get('note') or '').strip()]
        if near: return near[0]['note'].strip()[:36]
    ks = reason_keys(c.get('reasons'))
    if 'laugh' in ks: return "I CAN'T STOP LAUGHING"
    if 'chat' in ks: return 'CHAT WENT CRAZY'
    if 'marker' in ks: return 'WAIT FOR IT...'
    return 'WATCH THIS'

def hook_options(near, hw, c, s):
    """up to 3 different hooks to choose from"""
    out = []
    def add(x):
        x = re.sub(r'\s+', ' ', (x or '').strip().upper())
        if x and x not in out: out.append(x)
    add(title_from(near, hw))
    if near:   # the second best phrase
        phrases = []; cur = [near[0]]
        for a, b in zip(near, near[1:]):
            if b[0] - a[1] > 0.35 or re.search(r'[.!?]$', a[2]): phrases.append(cur); cur = []
            cur.append(b)
        phrases.append(cur)
        ranked = sorted(phrases, key=lambda ph: -(len(SAY_STRONG.findall(' '.join(w[2] for w in ph))) * 3 + len(SAY_HYPE.findall(' '.join(w[2] for w in ph)))))
        for ph in ranked[:3]:
            t = re.sub(r"[^\w' !?]", '', ' '.join(w[2] for w in ph[:6] if w[2] != UNCLEAR)).strip()
            if 2 <= len(t) <= 40 and not SAY_LAUGH.fullmatch(t.lower()): add(t)
    add(fallback_title(c, s))
    g = c.get('game')
    if g: add({'ACE': 'THEY NEVER STOOD A CHANCE', '4K': 'ONE MORE AND IT WAS AN ACE'}.get(g['label'], 'HOW DID I WIN THIS'))
    else:
        hk = gprof().get('hooks') or []
        if hk: add(hk[(int(c.get('t', 0)) // 7) % len(hk)])
    add('WAIT FOR IT...')
    return out[:3]

def title_from(near, hw):
    """a short hook for the top of the short: the phrase you shouted, cut on a pause"""
    if not near: return ''
    # phrases = words split on pauses
    phrases = []; cur = [near[0]]
    for a, b in zip(near, near[1:]):
        if b[0] - a[1] > 0.35 or re.search(r'[.!?]$', a[2]): phrases.append(cur); cur = []
        cur.append(b)
    phrases.append(cur)
    best = None
    for ph in phrases:
        txt = ' '.join(w[2] for w in ph)
        sc = len(SAY_STRONG.findall(txt)) * 3 + len(SAY_HYPE.findall(txt)) + len(SAY_LAUGH.findall(txt)) - (len(ph) > 6)
        if hw and any(w in ph for w in hw): sc += 1
        if best is None or sc > best[0]: best = (sc, ph)
    words = [w[2] for w in best[1]][:6]
    t = re.sub(r"[^\w' !?]", '', ' '.join(words)).strip().upper()
    if SAY_LAUGH.fullmatch(t.lower() or 'x'): return ''
    return t[:38]

# ---------------------------------------------------------------- speech to text
_WHISPER = {}
def model_cached(name):
    hub = os.path.join(os.path.expanduser('~'), '.cache', 'huggingface', 'hub')
    key = name.replace('.', '-').replace('large-v3-turbo', 'large-v3-turbo')
    try: return any(key in d for d in os.listdir(hub))
    except OSError: return False

def whisper_ok():
    try:
        import faster_whisper  # noqa
        return True
    except Exception:
        return False

def has_cuda():
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False

CORES = os.cpu_count() or 4
_BAD_MODEL = set()
def whisper_model(purpose='captions'):
    """auto: NVIDIA = large-v3. otherwise the processor: small.en to scan a whole stream (fast),
    medium.en for the captions of a short when the processor is strong enough (8+ cores)"""
    from faster_whisper import WhisperModel
    name = SET.get('whisper_model', 'auto')
    cuda = has_cuda()
    if name == 'auto': name = 'large-v3' if cuda else ('large-v3-turbo' if purpose == 'captions' and CORES >= 8 else 'small.en')
    if name in _BAD_MODEL: name = 'medium.en' if purpose == 'captions' else 'small.en'
    if SET.get('language', 'en') != 'en': name = name.replace('.en', '')
    key = (name, cuda)
    thr = max(4, min(16, CORES))
    if key not in _WHISPER:
        log(f'Speech model "{name}" loading ({"graphics card" if cuda else "processor"}). The first time it gets downloaded, hang on.')
        prog('Loading the speech model' + ('' if model_cached(name) else ' (one-time download, ~1-2 GB)'))
        try: _WHISPER[key] = WhisperModel(name, device='cuda' if cuda else 'cpu', compute_type='float16' if cuda else 'int8', cpu_threads=thr)
        except Exception as e:
            if cuda:
                log('The graphics card does not work for the speech model, using the processor')
                name = name if name != 'large-v3' else 'small.en'; key = (name, False)
            else:
                log(f'Speech model "{name}" does not work ({str(e)[:80]}), picking another one'); _BAD_MODEL.add(name)
                name = 'medium.en' if purpose == 'captions' and name != 'medium.en' else 'small.en'; key = (name, False)
            if key not in _WHISPER: _WHISPER[key] = WhisperModel(name, device='cpu', compute_type='int8', cpu_threads=thr)
    return _WHISPER[key]

VOICE_FILE = os.path.join(HERE, 'voicelines.txt')
_VL = {'t': 0, 'lines': []}
def voicelines():
    """lines from the game that should never become captions (announcer, agent lines). you can add your own in voicelines.txt"""
    try:
        m = os.path.getmtime(VOICE_FILE)
        if m != _VL['t']:
            _VL['lines'] = [norm_txt(l) for l in open(VOICE_FILE, encoding='utf-8') if l.strip() and not l.startswith('#')]; _VL['t'] = m
    except OSError: pass
    return _VL['lines']
def norm_txt(t): return re.sub(r'[^a-z0-9 ]', '', t.lower().replace('-', ' ')).strip()
def is_voiceline(text):
    import difflib
    t = norm_txt(text)
    if not t: return True
    for vl in voicelines():
        if not vl: continue
        if t == vl or (' ' in vl and vl in t and len(t) <= len(vl) + 12): return True
        if ' ' in vl and len(t.split()) <= 10 and difflib.SequenceMatcher(None, t, vl).ratio() > 0.82: return True
    return False

UNCLEAR = '\u2026'
PREVIEW_DIR = os.path.join(DATA, 'voorbeeld')   # shown as ... in the captions when you said something the model could not understand
UNSURE_TL = threading.local()   # words the model was not quite sure about (start times), for the yellow marks in the editor
def transcribe(wav, purpose='captions', on_prog=None):
    UNSURE_TL.v = []
    if not whisper_ok():
        log('faster-whisper is not installed, no captions'); return []
    model = whisper_model(purpose)
    # read the wav ourselves: newer PyAV versions break faster-whisper's own file reader
    import wave, numpy as np
    if not os.path.exists(wav): return []
    with wave.open(wav, 'rb') as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if len(audio) < 1600: return []
    kw = dict(language=SET.get('language') or None, beam_size=5, word_timestamps=True, vad_filter=True,
              vad_parameters={'min_silence_duration_ms': 300, 'speech_pad_ms': 250, 'threshold': 0.4},
              condition_on_previous_text=False, initial_prompt=vocab_prompt(model), no_speech_threshold=0.5, temperature=[0.0, 0.2, 0.4])
    try: segs, _ = model.transcribe(audio, hallucination_silence_threshold=1.0, **kw)
    except TypeError: segs, _ = model.transcribe(audio, **kw)       # older faster-whisper
    words = []; dropped = 0; unclear = []   # unclear = (start, end) of speech the model could not turn into words
    total = len(audio) / 16000.0
    for sg in segs:
        if on_prog: on_prog(min(1.0, sg.end / max(1.0, total)))
        if getattr(sg, 'no_speech_prob', 0) > 0.7: continue
        txt = (sg.text or '').strip()
        # music: whisper marks it with notes or tags, lyrics are repetitive or very unsure
        if re.search(r'[\u266a\u266b]|\[(music|muziek|applause|laughter)|\((music|muziek)', txt, re.I) or getattr(sg, 'compression_ratio', 0) > 2.4 \
           or (getattr(sg, 'avg_logprob', 0) < -1.15 and getattr(sg, 'no_speech_prob', 0) > 0.3):
            if not re.search(r'[\u266a\u266b]|music|muziek', txt, re.I) and getattr(sg, 'compression_ratio', 0) <= 2.4 and sg.end - sg.start < 6:
                unclear.append((sg.start, sg.end))   # someone spoke, but it was too unclear to write down
            dropped += 1; continue
        if is_voiceline(txt): dropped += 1; continue
        for w in (sg.words or []):
            if getattr(w, 'probability', 1) < 0.2:   # not sure what was said: show that something was said
                if words and words[-1][2] == UNCLEAR and w.start - words[-1][1] < 0.6: words[-1] = (words[-1][0], round(w.end, 2), UNCLEAR)
                else: words.append((round(w.start, 2), round(w.end, 2), UNCLEAR))
                continue
            txt = w.word.strip()
            if not txt: continue
            if words and (txt[0] in "',.!?" or txt.lower() in ("'s", "'t", "'re", "'m", "'ll", "'ve", "'d")) and w.start - words[-1][1] < 0.15:
                words[-1] = (words[-1][0], w.end, words[-1][2] + txt); continue
            words.append((round(w.start, 2), round(w.end, 2), txt))
            if getattr(w, 'probability', 1) < 0.62: UNSURE_TL.v.append(round(w.start, 2))
    # with a mic-only track: speech the model skipped entirely also gets a "..."
    if _WAVMIC.get(wav):
        try:
            from faster_whisper.vad import get_speech_timestamps, VadOptions
            for sp in get_speech_timestamps(audio, VadOptions(threshold=0.55, min_speech_duration_ms=400, min_silence_duration_ms=300)):
                a, b = sp['start'] / 16000.0, sp['end'] / 16000.0
                if b - a >= 0.5 and not any(w[0] < b and w[1] > a for w in words): unclear.append((a, min(b, a + 3)))
        except Exception: pass
    for a, b in unclear:
        if not any(w[0] < b and w[1] > a for w in words): words.append((round(a, 2), round(b, 2), UNCLEAR))
    words.sort(key=lambda w: w[0])
    if dropped: log(f'{dropped} bits of game audio or music removed from the captions')
    return apply_fixes(words)

# ---------------------------------------------------------------- captions (word by word, like the big TikTok channels)
FONT_DIR = os.path.join(HERE, 'fonts')
def font(size, kind='caption'):
    from PIL import ImageFont
    try:
        bf = brand_file(B()['id'], 'font') if kind in ('caption', 'tag') else None
        if bf: return ImageFont.truetype(bf, size)
    except Exception: pass
    files = {'caption': ['BarlowCondensed-ExtraBoldItalic.ttf'], 'tag': ['BarlowCondensed-Bold.ttf']}[kind]
    for f in [os.path.join(FONT_DIR, x) for x in files] + ['C:/Windows/Fonts/ariblk.ttf', 'C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        if os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()

EMPH = re.compile(r"^(no+|what|wow|omg|yes+|nice+|insane|crazy|ace|clutch|bro+|let'?s|lets|go+|w|holy|why|how|wait|god|sheesh|gg|perfect|unreal|nasty|sick|one|tap)\W*$", re.I)
def caption_groups(words):
    groups = []; cur = []
    for w in words:
        txt = w[2]
        if cur and (txt == UNCLEAR or cur[-1][2] == UNCLEAR or len(cur) >= 3 or w[0] - cur[-1][1] > 0.5 or sum(len(x[2]) + 1 for x in cur) + len(txt) > 17 or re.search(r'[.!?,]$', cur[-1][2])):
            groups.append(cur); cur = []
        cur.append(w)
    if cur: groups.append(cur)
    # 6.1: a lonely word joins its neighbour when they belong together (close in time, still short enough)
    def fits(a, b): return len(a) + len(b) <= 4 and sum(len(x[2]) + 1 for x in a + b) <= 21 and b[0][0] - a[-1][1] <= 0.45 and UNCLEAR not in [x[2] for x in a + b] and not re.search(r'[.!?]$', a[-1][2])
    i = 0
    while i < len(groups):
        g = groups[i]
        if len(g) == 1 and not EMPH.match(g[0][2]):
            if i + 1 < len(groups) and fits(g, groups[i + 1]): groups[i:i + 2] = [g + groups[i + 1]]; continue
            if i > 0 and fits(groups[i - 1], g): groups[i - 1:i + 1] = [groups[i - 1] + g]; i -= 1; continue
        i += 1
    return groups

STYLES = ('jele', 'purple', 'classic', 'clean')
def draw_caption(words, active, scale=1.0, W=1080, H=300, style='jele'):
    """one caption line. styles: jele (orange word on dark box), purple (white, active word on a purple box),
    classic (white with black outline, active word yellow), clean (white with soft shadow, active word orange)"""
    from PIL import Image, ImageDraw, ImageFilter
    style = style if style in STYLES else 'jele'
    base = {'jele': 104, 'purple': 92, 'classic': 100, 'clean': 88}[style] * (W / 1080 if W < 1500 else 0.95)
    size = max(20, int(base * scale)); f = font(size, 'tag' if style in ('purple', 'clean') else 'caption')
    txt = ['\u2026' if w[2] == UNCLEAR else (re.sub(r'[^\w\'!?.,%*-]', '', w[2]).upper().rstrip(',.') or '\u2026') for w in words]
    tmp = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    gap = size * (0.26 if style == 'purple' else 0.22)
    widths = [tmp.textlength(t, font=f) for t in txt]
    total = sum(widths) + gap * (len(txt) - 1)
    if total > W - 80 and scale > 0.3:
        return draw_caption(words, active, scale * (W - 80) / total, W, H, style)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); y = H / 2
    stroke = {'jele': 9, 'purple': 5, 'classic': 11, 'clean': 0}[style]
    # soft drop shadow under everything
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh); x = (W - total) / 2
    for t, w in zip(txt, widths):
        ds.text((x + 3, y + 6), t, font=f, anchor='lm', fill=(0, 0, 0, 160), stroke_width=stroke + 3, stroke_fill=(0, 0, 0, 160)); x += w + gap
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 if style == 'clean' else 5)))
    d = ImageDraw.Draw(img); x = (W - total) / 2
    for i, (t, w) in enumerate(zip(txt, widths)):
        on = i == active; emph = bool(EMPH.match(t))
        if style == 'jele':
            col = BC() if on else ((255, 228, 92, 255) if emph else (255, 255, 255, 255)); sc = BI()
            if on:
                pad = size * 0.08
                d.rounded_rectangle((x - pad, y - size * 0.52, x + w + pad, y + size * 0.5), radius=int(size * 0.14), fill=BI(235))
        elif style == 'purple':
            col = (255, 255, 255, 255); sc = (0, 0, 0, 255)
            if on:
                pad = size * 0.14
                d.rounded_rectangle((x - pad, y - size * 0.56, x + w + pad, y + size * 0.52), radius=int(size * 0.18), fill=(124, 58, 237, 255))
        elif style == 'classic':
            col = (255, 230, 0, 255) if on else (255, 255, 255, 255); sc = (0, 0, 0, 255)
        else:
            col = BC() if on else (255, 255, 255, 255); sc = (0, 0, 0, 0)
        d.text((x, y), t, font=f, anchor='lm', fill=col, stroke_width=stroke, stroke_fill=sc); x += w + gap
    return img

def caption_track(words, clip_start, dur, folder, style='jele', W=1080, H=300, scale=1.0, anim='pop'):
    """renders the captions as a series of images with exact durations (ffconcat), one per word change, with a tiny pop on each new line"""
    from PIL import Image
    ws = [(max(0, a - clip_start), max(0, b - clip_start), t) for a, b, t in words if b > clip_start and a < clip_start + dur]
    if not ws: return None
    blank = os.path.join(folder, 'blank.png'); Image.new('RGBA', (W, H), (0, 0, 0, 0)).save(blank)
    groups = caption_groups(ws); items = []; t = 0.0; n = 0
    def add(img_path, until):
        nonlocal t
        if until - t > 0.001: items.append((img_path, until - t)); t = until
    def dc(g, wi, sc=1.0):
        if anim == 'type': return draw_caption(g[:wi + 1], wi, sc * scale, W, H, style)      # words appear one by one
        if anim == 'word': return draw_caption([g[wi]], 0, sc * scale * 1.15, W, H, style)   # one big word at a time
        return draw_caption(g, wi, sc * scale, W, H, style)
    for gi, g in enumerate(groups):
        g_end = (groups[gi + 1][0][0] if gi + 1 < len(groups) else g[-1][1] + 0.4)
        g_end = min(g_end, g[-1][1] + 0.9)
        add(blank, g[0][0])
        for wi, w in enumerate(g):
            w_end = g[wi + 1][0] if wi + 1 < len(g) else g_end
            pops = ((0.86, 1 / 30), (1.06, 1 / 30)) if (wi == 0 and anim in ('pop', 'type')) or anim in ('bounce', 'word') else ()
            for sc, d in pops:   # pop in (bounce and word: on every word)
                p = os.path.join(folder, f'c{n}.png'); dc(g, wi, sc).save(p); n += 1; add(p, min(w_end, t + d))
            p = os.path.join(folder, f'c{n}.png'); dc(g, wi).save(p); n += 1; add(p, max(t, w_end))
    add(blank, dur + 0.5)
    lst = os.path.join(folder, 'caps.txt')
    with open(lst, 'w', encoding='utf-8') as fh:
        fh.write('ffconcat version 1.0\n')
        for p, d in items: fh.write(f"file '{p.replace(os.sep, '/')}'\nduration {d:.4f}\n")
        fh.write(f"file '{items[-1][0].replace(os.sep, '/')}'\n")
    return lst

def tag_png(folder, text, W=1080):
    from PIL import Image, ImageDraw
    f = font(40, 'tag'); img = Image.new('RGBA', (W, 90), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    w = d.textlength(text, font=f); x = (W - w) / 2
    d.rounded_rectangle((x - 30, 14, x + w + 26, 76), radius=31, fill=BI(215))
    d.ellipse((x - 16, 39, x - 4, 51), fill=BC())
    d.text((x + 6, 45), text, font=f, fill=(255, 255, 255, 255), anchor='lm')
    p = os.path.join(folder, 'tag.png'); img.save(p); return p

def frame_pngs(folder, w, h, rnd, brd):
    """mask with rounded corners and a border in your colour, for the whole-picture layout"""
    from PIL import Image, ImageDraw
    r = 34 if rnd else 0
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    mp = os.path.join(folder, 'frame_mask.png'); m.save(mp)
    b = Image.new('RGBA', (w + 24, h + 24), (0, 0, 0, 0)); d = ImageDraw.Draw(b)
    if brd: d.rounded_rectangle((6, 6, w + 17, h + 17), radius=r + 6 if r else 0, outline=BC(), width=7)
    bp = os.path.join(folder, 'frame_border.png'); b.save(bp)
    return mp, bp

def endcard_png(folder, W=1080, H=1920):
    """the last 2 seconds: a dark band with "follow for more" and your channel"""
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    bh = 420 if H > W else 300; y0 = (H - bh) // 2 if H > W else H - bh - 60
    for i in range(bh):   # soft band
        a = int(225 * min(1, min(i, bh - i) / 60)); d.line([(0, y0 + i), (W, y0 + i)], fill=(10, 14, 22, a))
    f1 = font(120 if H > W else 96); f2 = font(64 if H > W else 54, 'tag')
    d.text((W / 2, y0 + bh * 0.36), (B().get('end_text') or 'FOLLOW FOR MORE').upper()[:22], font=f1, fill=(255, 255, 255, 255), anchor='mm', stroke_width=6, stroke_fill=BI())
    tag = (B().get('tag') or SET.get('tag') or default_tag()).strip()
    w = d.textlength(tag, font=f2); x = (W - w) / 2; yy = y0 + bh * 0.72
    if B().get('credit'): d.text((W / 2, y0 + bh + 34), 'made with JelE Clipper', font=font(30, 'tag'), fill=(255, 255, 255, 150), anchor='mm')
    d.rounded_rectangle((x - 34, yy - 46, x + w + 34, yy + 46), radius=46, fill=BC())
    d.text((W / 2, yy), tag, font=f2, fill=BI(), anchor='mm')
    p = os.path.join(folder, 'endcard.png'); img.save(p); return p

def hook_png(folder, text, W=1080):
    """the title at the top: big, on an orange card, over two lines when it is long"""
    from PIL import Image, ImageDraw, ImageFilter
    text = re.sub(r'\s+', ' ', text.strip().upper())
    if not text: return None
    maxw = min(940, W - 140); tmp = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    def lines_for(size):
        f = font(size); words = text.split(); ls = ['']
        for w in words:
            t = (ls[-1] + ' ' + w).strip()
            if tmp.textlength(t, font=f) <= maxw or not ls[-1]: ls[-1] = t
            else: ls.append(w)
        return f, ls
    size = 92
    while True:
        f, ls = lines_for(size)
        if (len(ls) <= 2 and all(tmp.textlength(l, font=f) <= maxw for l in ls)) or size <= 46: break
        size -= 6
    ls = ls[:2]; lh = size * 1.08; widths = [tmp.textlength(l, font=f) for l in ls]; bw = max(widths) + 64; bh = lh * len(ls) + size * 0.34
    H = int(bh + 80); img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    x0 = (W - bw) / 2; y0 = 30
    ds.rounded_rectangle((x0 + 4, y0 + 10, x0 + bw + 4, y0 + bh + 10), radius=22, fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img); d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=22, fill=BC())
    for i, l in enumerate(ls):
        d.text((W / 2, y0 + size * 0.17 + lh * i + lh / 2), l, font=f, fill=BI(), anchor='mm')
    p = os.path.join(folder, 'hook.png'); img.save(p); return p

# ---------------------------------------------------------------- rendering a short
_ENC = {}
def encoder_args():
    want = SET.get('encoder', 'auto')
    if want != 'x264':
        opts = [('h264_nvenc', ['-preset', 'p6', '-tune', 'hq', '-rc', 'vbr', '-cq', '19', '-b:v', '0', '-maxrate', '20M', '-bufsize', '40M']),     # NVIDIA
                ('h264_amf', ['-usage', 'transcoding', '-quality', 'quality', '-rc', 'cqp', '-qp_i', '18', '-qp_p', '20', '-qp_b', '22']),       # AMD Radeon
                ('h264_qsv', ['-preset', 'slower', '-global_quality', '20'])]                                                                  # Intel
        for name, extra in opts:
            if name not in _ENC:
                t = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=s=1280x720:d=0.3', '-pix_fmt', 'yuv420p', '-c:v', name] + extra + ['-f', 'null', '-'], capture_output=True, creationflags=NOWIN)
                _ENC[name] = t.returncode == 0
                if _ENC[name]: log('Making video with your graphics card:', {'h264_nvenc': 'NVIDIA', 'h264_amf': 'AMD', 'h264_qsv': 'Intel'}[name])
            if _ENC[name]: return ['-c:v', name] + extra
    return ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18']

def prog(stage=None, pct=None):
    """progress of the current job, shown in the app"""
    j = STATE.get('job')
    if not j: return
    if stage is not None: j['stage'] = stage
    if pct is not None: j['pct'] = round(max(0.0, min(100.0, pct)), 1)

def load_transcript(sid):
    try: return apply_fixes([tuple(w) for w in json.load(open(os.path.join(sdir(sid), 'transcript.json'), encoding='utf-8'))], game_for(sid))
    except Exception: return []
def load_unsure(sid):
    try: return json.load(open(os.path.join(sdir(sid), 'twijfel.json'), encoding='utf-8'))
    except Exception: return []

def overview(sid, n=800):
    """loudness and chat over the whole stream, for the overview bar in the editor (cached)"""
    import numpy as np
    s = load_sess(sid); path = s['path']; cache = os.path.join(sdir(sid), 'overview.json')
    try:
        c = json.load(open(cache, encoding='utf-8'))
        if c.get('mtime') == os.path.getmtime(path) and c.get('n') == n: peaks = c['peaks']; dur = c['dur']
        else: raise ValueError
    except Exception:
        sr = 1000
        r = subprocess.run([FF, '-v', 'error', '-i', path, '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'], capture_output=True, creationflags=NOWIN)
        x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        dur = len(x) / sr or (s.get('duration') or 1)
        if len(x) >= n:
            x = x[:len(x) // n * n].reshape(n, -1); db = 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-5)
            lo, hi = np.percentile(db, 5), np.percentile(db, 99.5); peaks = np.clip((db - lo) / max(1e-3, hi - lo), 0, 1).round(3).tolist()
        else: peaks = []
        try: json.dump({'mtime': os.path.getmtime(path), 'n': n, 'peaks': peaks, 'dur': dur}, open(cache, 'w', encoding='utf-8'))
        except Exception: pass
    chat = [0] * n
    for t, u, msg in load_chat(sid):
        i = int(t / dur * n)
        if 0 <= i < n: chat[i] += 1
    return {'dur': dur, 'peaks': peaks, 'chat': chat, 'markers': [m['t'] for m in s.get('markers', [])],
            'moments': [{'id': m['id'], 'start': m['start'], 'end': m['end']} for m in s.get('moments', [])], 'has_words': bool(load_transcript(sid)),
            'game': [{'t': e['t'], 'label': e['label'], 'round': e.get('round'), 'weapon': e.get('weapon', '')} for e in s.get('game_events', [])], 'kills': s.get('game_kills', [])}

def words_for(sid, job, path, start, dur, work):
    """the words you kept in the editor, else what was heard during the analysis, else listen now"""
    if isinstance(job.get('words'), list): return [tuple(w) for w in job['words'] if len(w) == 3]
    s = load_sess(sid)
    tw = load_transcript(sid)   # the whole stream was already heard: reuse it
    if tw and tw[0][0] <= start + 30 and tw[-1][1] >= start + dur - 30:
        return [tuple(w) for w in tw if start - 1 <= w[0] <= start + dur + 1]
    for m in s.get('moments', []):
        if m.get('id') == job.get('mid') and m.get('words'):
            ws = m['words']
            if ws and ws[0][0] <= start + 1.5 and ws[-1][1] >= start + dur - 3: return [tuple(w) for w in ws]
    prog('Listening to what you say', 4); wav = os.path.join(work, 'a.wav'); extract_wav(path, start, dur, wav)
    return [(a + start, b + start, w) for a, b, w in transcribe(wav, 'captions', lambda f: prog(None, 5 + 25 * f))]

def post_text(hook, words):
    """a ready-to-paste title, description and hashtags for TikTok / YouTube Shorts / Reels"""
    said = ' '.join(w[2] for w in words if w[2] != UNCLEAR).lower()
    g = cur_game(); P = gprof(g)
    tags = ((SET.get('game_hashtags') or {}).get(g) or (SET.get('hashtags') if g == 'valorant' else '') or P.get('hashtags') or '').split()
    for k, v in (P.get('word_tags') or {}).items():
        if re.search(r'\b' + re.escape(k) + r'\b', said) and v not in tags: tags.insert(2, v)
    title = (hook or '').strip().capitalize() or P.get('fallback') or 'Stream moment'
    if not re.search(r'[.!?]$', title): title += '!' if re.search(r'no way|insane|crazy|let.?s go|what|wow|holy', title, re.I) else ''
    quote = re.sub(r'\s+', ' ', ' '.join(w[2] for w in words if w[2] != UNCLEAR)).strip()
    if len(quote) > 110: quote = quote[:107].rsplit(' ', 1)[0] + '...'
    tag = (B().get('tag') or SET.get('tag') or default_tag()).strip()
    desc = (f'"{quote}"\n\n' if quote else '') + (f'Live on {tag}' if tag else '')
    return {'title': title[:90], 'description': desc, 'hashtags': ' '.join(tags[:9])}

def zoom_times(sid, job, ws, start, dur):
    """moments to punch in: when you shout, press the clip button, or get a kill (matchdata). seconds into the clip"""
    if not ws:
        ws = [tuple(w) for w in (job.get('words') or [])] or [tuple(w) for w in load_transcript(sid) if start <= w[0] <= start + dur]
    times = []
    for i, w in enumerate(ws):
        ph = ' '.join(x[2] for x in ws[i:i + 3] if x[0] - w[0] < 1.5)
        if SAY_STRONG.match(re.sub(r"[^\w' ]", '', ph)): times.append(w[0] - start)
    s = load_sess(sid)
    times += [m['t'] - start - 0.3 for m in s.get('markers', []) if start <= m['t'] <= start + dur]
    times += [kt - start for kt in s.get('game_kills', []) if start <= kt <= start + dur]
    return sorted(times)

def zoom_pick(times, dur):
    ev = []
    for t in sorted(times):
        if 0.3 < t < dur - 1.0 and (not ev or t - ev[-1] > 2.2): ev.append(t)
    return ev[:5]

def zoom_expr_from(ev):
    if not ev: return None
    parts = '+'.join(f'clip((it-{a:.2f})/0.12,0,1)*clip(({a + 1.1:.2f}-it)/0.3,0,1)' for a in ev)
    return f'1+0.15*min(1,{parts})'

def zoom_expr(sid, job, ws, start, dur):
    return zoom_expr_from(zoom_pick(zoom_times(sid, job, ws, start, dur), dur))

def render(job):
    BRAND_TL.b = brand_get(job.get('brand'))
    try: return _render(job)
    finally: BRAND_TL.b = None

def _render(job):
    sid = job['sid']; s = load_sess(sid); path = s['path']
    start = float(job['start']); end = float(job['end']); dur = max(1.0, end - start)
    base_name = job.get('title') or s['title'] + '_' + fmt(start).replace(':', 'm')
    tpl = (SET.get('name_tpl') or '{title}').replace('{titel}', '{title}').replace('{datum}', '{date}').replace('{tijd}', '{time}').replace('{indeling}', '{layout}')
    if not job.get('test') and not job.get('preview') and tpl != '{title}':
        base_name = tpl.replace('{title}', base_name).replace('{date}', time.strftime('%Y-%m-%d')).replace('{time}', time.strftime('%H%M')).replace('{layout}', job.get('layout') or SET.get('layout', 'split'))
    name = re.sub(r'[^\w-]+', '_', base_name).strip('_')[:70] or 'short'
    work = os.path.join(sdir(sid), 'tmp_' + uuid.uuid4().hex[:6]); os.makedirs(work, exist_ok=True)
    dst = os.path.join(OUT, f'{name}.mp4'); i = 2
    while os.path.exists(dst): dst = os.path.join(OUT, f'{name}_{i}.mp4'); i += 1
    try:
        o_start, o_end = start, end   # the clip in the original recording (for the library)
        fx = job.get('fx')
        if fx is None and not job.get('parts'): fx = fx_suggest(sid, start, end, job)   # automatic shorts get the suggested effects
        fx = fx or {}
        ws = []; ztimes = []; cuts_at = []; prepared = False; kf_times = []; stickers = []; chapters = []
        teaser_len = 0.0; replay_at = None; replay_len = 0.0
        if job.get('parts'):   # montage / highlights: several moments glued together
            prog('Preparing the montage', 3); parts = []; tt = 0.0
            for pt in job['parts']:
                ps = load_sess(pt['sid']); a_, b_ = float(pt['a']), float(pt['b']); parts.append((ps['path'], a_, b_, 1.0))
                ws += [(w[0] - a_ + tt, w[1] - a_ + tt, w[2]) for w in load_transcript(pt['sid']) if a_ <= w[0] < b_]
                ztimes += [kt - a_ + tt for kt in ps.get('game_kills', []) + [m['t'] for m in ps.get('markers', [])] if a_ <= kt < b_]
                if job.get('chapters'): chapters.append((tt, pt.get('label') or ''))
                if tt > 0: cuts_at.append(tt); ztimes.append(tt + 0.05)
                tt += b_ - a_
            path = make_mezz(parts, work); start = 0.0; dur = tt; prepared = True
        else:
            if job.get('captions') or job.get('jumpcut', SET.get('jumpcut', True)):
                prog('Listening to what you say', 4)
                try: ws = words_for(sid, job, path, start, dur, work)
                except Exception: traceback.print_exc(); ws = []
            ztimes = [float(z) for z in fx['zooms']] if 'zooms' in fx else zoom_times(sid, job, ws, start, dur)
            kf_times = [float(z) for z in fx.get('killfeed', [])]
            stickers = list(fx.get('stickers', []))
            keep = None
            if job.get('jumpcut', SET.get('jumpcut', True)) and ws:
                keep = keep_segments(path, ws, start, dur, ztimes + kf_times + [float(x.get('t', 0)) for x in stickers] +
                                     ([fx['replay']['a'], fx['replay']['b']] if fx.get('replay') else []), fx.get('peak'))
            keep = keep or [(0.0, dur)]
            cuts = sorted((max(0.0, float(a_) - start), min(dur, float(b_) - start)) for a_, b_ in (job.get('cuts') or []) if float(b_) > float(a_))
            if cuts:   # 6.1: pieces you cut out in the editor (a sentence, a silence)
                nk = []
                for x, y in keep:
                    segs_ = [(x, y)]
                    for ca, cb in cuts: segs_ = [p_ for sa, sb in segs_ for p_ in ((sa, min(sb, ca)), (max(sa, cb), sb)) if p_[1] - p_[0] > 0.2]
                    nk += segs_
                keep = nk or keep
                log(f'{len(cuts)} piece(s) cut out in the editor')
            tz, rp = fx.get('teaser'), fx.get('replay')
            if job.get('loop'): tz = rp = None   # a loop flows from the end straight into the start: no opening glimpse, no replay
            if tz: tz = {'t': max(0.0, min(dur - 0.5, float(tz['t']))), 'len': max(0.6, min(2.5, float(tz.get('len', 1.2)))), 'text': tz.get('text', 'WAIT FOR IT...')}
            if rp: rp = {'a': max(0.0, float(rp['a'])), 'b': min(dur, float(rp['b'])), 'speed': max(0.25, min(1.0, float(rp.get('speed', 0.5))))}
            if rp and rp['b'] - rp['a'] < 0.4: rp = None
            if tz or rp or len(keep) > 1:
                prog('Building the timeline', 12); segs = []
                if tz: segs.append((path, start + tz['t'], start + tz['t'] + tz['len'], 1.0)); teaser_len = tz['len']
                segs += [(path, start + a_, start + b_, 1.0) for a_, b_ in keep]
                if rp: segs.append((path, start + rp['a'], start + rp['b'], rp['speed']))
                path = make_mezz(segs, work); prepared = True
                main_len = sum(b_ - a_ for a_, b_ in keep)
                mp = lambda t_: teaser_len + remap(t_, keep)
                ws = [(mp(a_ - start), mp(b_ - start), t_) for a_, b_, t_ in ws if any(x <= a_ - start <= y for x, y in keep)]
                ztimes = [mp(z) for z in ztimes]; kf_times = [mp(z) for z in kf_times]
                stickers = [dict(x, t=mp(float(x.get('t', 0)))) for x in stickers]
                if rp: replay_at = teaser_len + main_len; replay_len = (rp['b'] - rp['a']) / rp['speed']
                if teaser_len: cuts_at.append(teaser_len)
                if rp: cuts_at.append(replay_at)
                dur = teaser_len + main_len + replay_len; start = 0.0
                if len(keep) > 1: log(f'{len(keep) - 1} boring bits cut')
            else:
                ws = [(a_ - start, b_ - start, t_) for a_, b_, t_ in ws]; start_shift = start
        if not prepared and not job.get('parts'):
            pass
        sw, sh = probe_size(path); k = sw / 1920.0
        if prepared: k = 1.0   # the glued video is always 1920x1080
        layout = job.get('layout') or SET.get('layout') or 'split'
        if layout == 'full': layout = 'gameonly'          # old name
        cam = cam_at(s, o_start) if SET.get('cam_auto', True) else SET['cam']
        cx, cy, cw, ch = [int(v * k) for v in cam]
        if layout == 'split' and cw < 20: layout = 'gameonly'
        OW, OH = (1920, 1080) if layout == 'landscape' else (1080, 1920); FRAME_INPUTS = 0
        style = job.get('style') or SET.get('cap_style') or 'jele'
        caps = None; prog('Preparing', 25)
        # from here on every time is "seconds into the short"; the input starts at `start`
        if job.get('captions'):
            try:
                cws = [w for w in ws if (replay_at is None or w[0] < replay_at) and w[2] != UNCLEAR]   # viewers never see a "..." 
                shift_ = max(-1.5, min(1.5, float(job.get('cap_shift') or 0)))
                if shift_: cws = [(max(0.0, a_ + shift_), max(0.0, b_ + shift_), t_) for a_, b_, t_ in cws]
                if job.get('bleep'): cws = [(a_, b_, censor(t_) if SWEAR.match(t_) else t_) for a_, b_, t_ in cws]
                if not prepared and not job.get('parts'): cws = [(a_ + start, b_ + start, t_) for a_, b_, t_ in cws]
                prog('Drawing the captions', 32)
                cap_scale = float(job.get('cap_scale') or SET.get('cap_scale') or 1.0)
                ec_on = job.get('endcard', SET.get('endcard', True)) and dur > 6 and not job.get('loop')
                caps = caption_track(cws, start if not prepared and not job.get('parts') else 0.0, dur - 2.2 if ec_on else dur, work, style, OW, int(300 * max(1.0, cap_scale)), cap_scale, job.get('cap_anim') or SET.get('cap_anim') or 'pop')
            except Exception: log('Captions failed, making it without'); traceback.print_exc()
        zev = zoom_pick(ztimes, dur) if job.get('zoom', SET.get('auto_zoom', True)) else []
        if replay_at is not None: zev = [z for z in zev if z < replay_at]
        zoom = zoom_expr_from(zev)
        def zp(w_, h_):   # punch-in filter for the gameplay part
            return f",fps=60,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w_}x{h_}:fps=60" if zoom else ''
        inputs = ['-ss', f'{start:.3f}', '-t', f'{dur:.3f}', '-i', path]
        tag_y = OH - 120
        game_x = float(job['game_x']) if job.get('game_x') is not None else SET['game_x']
        if layout == 'gameonly':
            g_h = sh; g_w = int(sh * 1080 / 1920); gx = int(max(0, min(sw - g_w, game_x * sw - g_w / 2)))
            f = f"[0:v]crop={g_w}:{g_h}:{gx}:0,scale=1080:1920:flags=lanczos{zp(1080, 1920)},setsar=1[base]"
            cap_y = 1300; hook_y = 120; kf_pos = (1080 - 40, 330)
        elif layout == 'frame':
            fh = 608; bgk = job.get('bg') or SET.get('frame_bg') or 'blur'; rnd = job.get('round', SET.get('frame_round', False)); brd = job.get('border', SET.get('frame_border', False))
            fw_ = 1000 if (rnd or brd) else 1080; fh = int(fw_ * 9 / 16) // 2 * 2; fx0 = (1080 - fw_) // 2; fy0 = (1920 - fh) // 2
            if bgk == 'color': bgf = f"color=c=0x111827:s=1080x1920:r=60:d={dur + 1:.2f},setsar=1[bg];[0:v]"
            elif bgk == 'gradient': bgf = f"gradients=s=1080x1920:c0=0x2a1604:c1=0x0b0f18:x0=540:y0=0:x1=540:y1=1920:r=60:d={dur + 1:.2f},setsar=1[bg];[0:v]"
            else: bgf = None
            if bgf: f = bgf + f"scale={fw_}:{fh}:flags=lanczos,unsharp=5:5:0.5{zp(fw_, fh)},setsar=1[fg0]"
            else:
                f = (f"[0:v]split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=12:3,"
                     f"scale=1080:1920:flags=bilinear,eq=brightness=-0.22:saturation=1.25,setsar=1[bg];"
                     f"[b]scale={fw_}:{fh}:flags=lanczos,unsharp=5:5:0.5{zp(fw_, fh)},setsar=1[fg0]")
            nin = 1
            if rnd or brd:
                fr_in = frame_pngs(work, fw_, fh, rnd, brd)
                inputs += ['-loop', '1', '-t', f'{dur:.2f}', '-i', fr_in[0], '-loop', '1', '-t', f'{dur:.2f}', '-i', fr_in[1]]
                f += (f";[{nin}:v]format=gray[msk];[fg0]format=rgba[fga];[fga][msk]alphamerge[fg];[bg][fg]overlay={fx0}:{fy0}[bf];"
                      f"[bf][{nin + 1}:v]overlay={fx0 - 12}:{fy0 - 12}[base]"); nin += 2
            else: f += f";[bg][fg0]overlay={fx0}:{fy0}[base]"
            FRAME_INPUTS = nin - 1
            hook_y = (1920 - fh) // 2 - 210; cap_y = (1920 + fh) // 2 + 170; tag_y = 1920 - 190; kf_pos = (1080 - 30, (1920 + fh) // 2 + 20)
        elif layout == 'landscape':
            f = f"[0:v]scale=1920:1080:flags=lanczos{zp(1920, 1080)},setsar=1[base]"
            cap_y = 880; hook_y = 30; kf_pos = (1920 - 40, 120)
        else:
            top_h = int(1080 * ch / max(1, cw))
            if job.get('cam_h'):
                top_h = int(1920 * max(0.18, min(0.5, float(job['cam_h']))))
                want = 1080 / top_h
                if cw / ch > want: nw = int(ch * want); cx += (cw - nw) // 2; cw = nw
                else: nh = int(cw / want); cy += (ch - nh) // 2; ch = nh
            top_h -= top_h % 2; bot_h = 1920 - top_h; cw -= cw % 2; ch -= ch % 2
            g_h = sh; g_w = int(sh * 1080 / bot_h); g_w -= g_w % 2; gx = int(max(0, min(sw - g_w, game_x * sw - g_w / 2)))
            f = (f"[0:v]split=2[a][b];[a]crop={cw}:{ch}:{cx}:{cy},scale=1080:{top_h}:flags=lanczos,setsar=1[cam];"
                 f"[b]crop={g_w}:{g_h}:{gx}:0,scale=1080:{bot_h}:flags=lanczos,unsharp=5:5:0.6{zp(1080, bot_h)},setsar=1[game];[cam][game]vstack=2[stk];" +
                 (f"[stk]drawbox=x=0:y={top_h-4}:w=1080:h=8:color={BHEX()}:t=fill[base]" if job.get('divider', SET.get('divider', True)) else "[stk]null[base]"))
            cap_y = top_h + int(bot_h * 0.55); hook_y = top_h - 200; kf_pos = (1080 - 30, top_h + 40)
        if job.get('cap_y') is not None: cap_y = int(float(job['cap_y']) * OH)
        last = 'base'; n = 1 + (FRAME_INPUTS if layout == 'frame' else 0)
        # killfeed: the corner of the game, big, for a moment after every kill you chose
        kf_times = [t_ for t_ in kf_times if 0 <= t_ < dur and (replay_at is None or t_ < replay_at)]
        if kf_times:
            kb = [int(v * k) for v in (fx.get('kf_box') or SET.get('kf_box') or [1440, 80, 460, 170])]
            kbw = kb[2] - kb[2] % 2; kbh = kb[3] - kb[3] % 2; sc_ = 1.7 if OW == 1080 else 1.4
            ow_, oh_ = int(kbw / k * sc_) // 2 * 2, int(kbh / k * sc_) // 2 * 2
            en = '+'.join(f'between(t,{t_:.2f},{t_ + 1.8:.2f})' for t_ in kf_times[:8])
            inputs += ['-ss', f'{start:.3f}', '-t', f'{dur:.3f}', '-i', path]
            f += (f";[{n}:v]crop={kbw}:{kbh}:{kb[0]}:{kb[1]},scale={ow_}:{oh_}:flags=lanczos,drawbox=x=0:y=0:w=iw:h=ih:color={BHEX()}:t=5,setsar=1[kf];"
                  f"[{last}][kf]overlay={kf_pos[0] - ow_}:{kf_pos[1]}:enable='{en}'[t{n}]"); last = f't{n}'; n += 1
        if layout != 'landscape' and (B().get('tag') or '').strip() and not job.get('chapters'):
            tag = tag_png(work, B().get('tag') or '', OW)
            inputs += ['-i', tag]; f += f";[{last}][{n}:v]overlay=0:{tag_y}[t{n}]"; last = f't{n}'; n += 1
        # teaser: "wait for it" over the first second, then a white flash into the clip
        if teaser_len and not (job.get('hook') or '').strip():   # no title: a "wait for it" over the glimpse
            tp = sticker_png(work, (fx.get('teaser') or {}).get('text') or 'WAIT FOR IT...', 'teaser', OW)
            inputs += ['-loop', '1', '-t', f'{teaser_len:.2f}', '-i', tp]
            f += (f";[{n}:v]format=rgba[tz];[{last}][tz]overlay=(W-w)/2:(H-h)/2:eof_action=pass[t{n}];"
                  f"[t{n}]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.35:t=fill:enable='between(t,{teaser_len - 0.03:.2f},{teaser_len + 0.06:.2f})'[t{n}f]"); last = f't{n}f'; n += 1
        elif teaser_len:   # with a title: only a soft flash where the glimpse goes into the clip
            f += f";[{last}]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.35:t=fill:enable='between(t,{teaser_len - 0.03:.2f},{teaser_len + 0.06:.2f})'[tzf]"; last = 'tzf'
        hook = hook_png(work, job.get('hook') or '', OW)
        if hook:
            h0 = 0.0   # the title is there from the first frame: over the glimpse and on into the clip
            h1 = teaser_len + 2.7
            inputs += ['-loop', '1', '-t', f'{min(dur, h1 + 0.5):.2f}', '-i', hook]
            f += (f";[{n}:v]format=rgba,fade=t=in:st={h0:.2f}:d=0.12:alpha=1,fade=t=out:st={h1:.2f}:d=0.4:alpha=1[hk];"
                  f"[{last}][hk]overlay=0:{max(0, hook_y)}:eof_action=pass:enable='gte(t,{h0:.2f})'[t{n}]"); last = f't{n}'; n += 1
        if caps:
            inputs += ['-f', 'concat', '-safe', '0', '-i', caps]
            f += f";[{n}:v]format=rgba[cp];[{last}][cp]overlay=0:{cap_y-150}:eof_action=pass[t{n}]"; last = f't{n}'; n += 1
        # stickers you placed (ACE, NO WAY, ...), the REPLAY label and chapter titles
        if replay_at is not None: stickers.append({'t': replay_at, 'dur': min(replay_len, 2.5), 'text': 'REPLAY', 'x': 0.5, 'y': 0.16, 'kind': 'replay'})
        for ct, cl in chapters:
            if cl: stickers.append({'t': ct + 0.2, 'dur': 2.6, 'text': cl, 'x': 0.04, 'y': 0.86, 'kind': 'chapter'})
        for i_, st_ in enumerate(stickers[:12]):
            t_ = float(st_.get('t', 0)); d_ = float(st_.get('dur', 1.4))
            if not (0 <= t_ < dur): continue
            sp = sticker_png(work, st_.get('text') or 'NO WAY', st_.get('kind') or 'stamp', OW, i_)
            from PIL import Image as _I
            sw_, sh_ = _I.open(sp).size
            x_ = int(max(0, min(OW - sw_, float(st_.get('x', 0.5)) * OW - (0 if st_.get('kind') == 'chapter' else sw_ / 2))))
            y_ = int(max(0, min(OH - sh_, float(st_.get('y', 0.3)) * OH - sh_ / 2)))
            inputs += ['-loop', '1', '-t', f'{min(dur, t_ + d_):.2f}', '-i', sp]
            f += (f";[{n}:v]format=rgba,fade=t=in:st={t_:.2f}:d=0.12:alpha=1,fade=t=out:st={max(t_, t_ + d_ - 0.2):.2f}:d=0.2:alpha=1[sk{i_}];"
                  f"[{last}][sk{i_}]overlay={x_}:{y_}:eof_action=pass:enable='between(t,{t_:.2f},{t_ + d_:.2f})'[t{n}]"); last = f't{n}'; n += 1
        if job.get('progress', SET.get('progress_bar', False)):
            f += f";[{last}]drawbox=x=0:y=0:w='max(2,iw*t/{dur:.2f})':h=12:color={BHEX()}@0.95:t=fill[pb]"; last = 'pb'
        if job.get('endcard', SET.get('endcard', True)) and dur > 6 and not job.get('chapters') and not job.get('loop'):
            ec = endcard_png(work, OW, OH)
            inputs += ['-loop', '1', '-t', f'{dur:.2f}', '-i', ec]; st0 = max(0, dur - 2.2)
            f += f";[{n}:v]format=rgba,fade=t=in:st={st0:.2f}:d=0.25:alpha=1[ec];[{last}][ec]overlay=0:0:enable='gte(t,{st0:.2f})'[t{n}]"; last = f't{n}'; n += 1
        f, last, n = watermark_filter(f, last, inputs, n, dur, OW, OH)
        f += f";[{last}]" + ("scale=540:-2," if job.get('preview') else '') + "format=yuv420p[v]"
        # ---- sound: your voice cleaned up, sound effects, music that goes quiet when you talk
        a_fx = 'aformat=sample_rates=48000:channel_layouts=stereo'
        pre = a_fx + (',highpass=f=80,afftdn=nf=-25:tn=1' if job.get('voice', fx.get('voice', SET.get('voice_clean', False))) else '')
        bleeps = [(a_ + float(job.get('cap_shift') or 0) * 0, b_) for a_, b_, t_ in ws if SWEAR.match(t_) and b_ > 0 and a_ < dur] if job.get('bleep') else []
        if bleeps:   # 6.1: swear words beeped out
            en_ = '+'.join(f'between(t,{a_ - 0.03:.2f},{b_ + 0.03:.2f})' for a_, b_ in bleeps[:40])
            pre += f",volume=0:enable='{en_}'"
        f += f";[0:a]{pre},afade=t=in:d=0.12[a0]"; labels = ['[a0]']
        if bleeps:
            inputs += ['-f', 'lavfi', '-t', f'{dur:.2f}', '-i', 'sine=f=1000:r=48000']
            f += f";[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.22,volume=0:enable='not({en_})'[bp]"; labels.append('[bp]'); n += 1
        mus = fx.get('music') or job.get('music')
        mfile = os.path.join(MUSIC_DIR, os.path.basename(mus['file'])) if mus and mus.get('file') else None
        if mfile and os.path.exists(mfile):
            inputs += ['-stream_loop', '-1', '-ss', f"{float(mus.get('offset', 0)):.2f}", '-i', mfile]
            vol = max(0.0, min(1.0, float(mus.get('vol', 0.25))))
            f += f";[{n}:a]{a_fx},volume={vol:.2f},afade=t=in:d=0.6[mu]"
            if mus.get('duck', True):
                f += ";[a0]asplit=2[a0m][a0s];[mu][a0s]sidechaincompress=threshold=0.03:ratio=12:attack=15:release=450[mud]"; labels = ['[a0m]', '[mud]']
            else: labels.append('[mu]')
            n += 1
        if job.get('sfx', SET.get('sfx', True)):
            try:
                fxf = sfx_files()
                for i_, (fp, at) in enumerate([(fxf['boom'], z) for z in zev] + [(fxf['whoosh'], max(0, c_ - 0.2)) for c_ in cuts_at]):
                    inputs += ['-i', fp]; ms_ = int(at * 1000)
                    f += f";[{n}:a]{a_fx},adelay={ms_}|{ms_},volume={0.55 if 'boom' in fp else 0.45}[fx{i_}]"; labels.append(f'[fx{i_}]'); n += 1
            except Exception: traceback.print_exc()
        mix = f"amix=inputs={len(labels)}:duration=first:normalize=0," if len(labels) > 1 else ''
        f += f";{''.join(labels)}{mix}afade=t=out:st={max(0, dur-0.35):.2f}:d=0.35" + (",loudnorm=I=-14:TP=-1.2:LRA=11" if SET.get('loud', True) else '') + "[aud]"
        # inline filter: newer ffmpeg builds (8+) dropped -filter_complex_script
        tmp_out = os.path.join(work, 'out.mp4')   # only shows up in Shorts when it is finished
        venc = (['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', '-threads', str(max(2, CORES // 2))] + ['-r', '30']) if job.get('preview') else (encoder_args() + ['-r', '60'])
        args = ['-y'] + inputs + ['-filter_complex', f, '-map', '[v]', '-map', '[aud]'] + venc + ['-c:a', 'aac', '-b:a', '128k' if job.get('preview') else '192k', '-ar', '48000', '-movflags', '+faststart', tmp_out]
        prog('Making the video', 40)
        errf = os.path.join(work, 'ff_err.txt')
        with open(errf, 'w', encoding='utf-8', errors='replace') as eh:
            pr = subprocess.Popen([FF, '-hide_banner', '-loglevel', 'error', '-nostats', '-progress', 'pipe:1'] + args, stdout=subprocess.PIPE, stderr=eh, text=True, creationflags=NOWIN | (LOWPRIO if is_live() else 0))
            STATE['proc'] = pr
            for ln in pr.stdout:
                if STATE.get('cancel'): pr.kill(); break
                if ln.startswith('out_time_us=') or ln.startswith('out_time_ms='):
                    try: prog(None, 40 + 59 * (int(ln.split('=')[1]) / 1e6) / dur)
                    except ValueError: pass
            pr.wait()
        STATE['proc'] = None
        if STATE.get('cancel'): log('Short stopped'); STATE['why'] = 'stopped'; return None
        if pr.returncode != 0:
            err = open(errf, encoding='utf-8', errors='replace').read()
            log('Rendering failed:', err[-800:]); STATE['why'] = (err.strip().splitlines() or ['unknown error'])[-1][:160]; return None
        if job.get('preview'):   # a quick look at the end result: not in your library
            os.makedirs(PREVIEW_DIR, exist_ok=True); pv_ = os.path.join(PREVIEW_DIR, f"voorbeeld_{job['preview']}.mp4"); shutil.move(tmp_out, pv_); prog('Done', 100); return pv_
        shutil.move(tmp_out, dst); prog('Done', 100)
        s = load_sess(sid); s.setdefault('shorts', []).append({'file': os.path.basename(dst), 'start': o_start, 'end': o_end, 'at': time.time(), 'mid': job.get('mid'), 'layout': layout}); save_sess(s)
        mo = next((m for m in s.get('moments', []) if m.get('id') == job.get('mid')), {})
        lib = lib_load(); lib[os.path.basename(dst)] = {'test': bool(job.get('test')), 'sid': sid, 'mid': job.get('mid'), 'start': o_start, 'end': o_end, 'layout': layout, 'style': style, 'fx': fx, 'dur': round(dur, 1),
            'title': job.get('hook') or mo.get('title') or '', 'auto': bool(job.get('auto')), 'status': 'nieuw' if job.get('auto') else 'goed',
            'reasons': mo.get('reasons', []), 'score': mo.get('score', 0), 'session': s.get('title'), 'at': time.time(), 'game': cur_game(),
            'post': post_text(job.get('hook') or mo.get('title') or '', ws or [tuple(w) for w in (job.get('words') or mo.get('words') or [])]),
            'opts': {k: job.get(k) for k in ('cap_y', 'cap_scale', 'game_x', 'cam_h', 'progress', 'endcard', 'zoom', 'captions', 'jumpcut', 'sfx', 'voice')}, 'montage': bool(job.get('parts')), 'kind': job.get('kind', 'short')}
        if chapters:   # highlights: chapters for the YouTube description
            lib[os.path.basename(dst)]['post']['description'] = 'Chapters:\n' + '\n'.join(f'{fmt(ct)} {cl}' for ct, cl in chapters) + '\n\n' + lib[os.path.basename(dst)]['post']['description']
        lib[os.path.basename(dst)]['job'] = {k: v for k, v in job.items() if k not in ('replace', 'variant', 'test', 'preview')}
        lib[os.path.basename(dst)]['file'] = os.path.basename(dst); lib[os.path.basename(dst)]['brand'] = B().get('id')
        lib_save(lib)
        try:
            sw_ = [tuple(w) for w in (ws or [])]; Q_WORDS[os.path.basename(dst)] = sw_
            if sw_ and job.get('captions', True): srt_write(os.path.basename(dst), sw_)
        except Exception: pass
        if not job.get('auto') and mo and not job.get('variant') and not job.get('replace'): taste_note(mo.get('reasons'), True)
        if job.get('replace') and job['replace'] != os.path.basename(dst):   # re-edited from the inbox: the new one replaces the old one
            old = os.path.join(OUT, os.path.basename(job['replace']))
            if os.path.exists(old): os.remove(old)
            lib = lib_load(); oe = lib.pop(os.path.basename(job['replace']), None)
            if oe and oe.get('status') == 'nieuw': taste_note(oe.get('reasons'), True)
            lib_save(lib)   # you made this one yourself: you like this kind
        log('Short ready:', dst); return dst
    finally:
        shutil.rmtree(work, ignore_errors=True)

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
        elif 'twitch-clip' in r or 'twitch clip' in r: ks.add('tclip')
        elif re.search(r'\b(ace|[345]k|clutch)\b', r): ks.add('game')
    return ks
def taste_load():
    try: return json.load(open(TASTE_F, encoding='utf-8'))
    except Exception: return {}
def taste_note(reasons, good, length=None):
    """remember what kind of moments you keep and which you throw away"""
    try: taste_example(reasons, good, length)
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
    hub = os.path.join(os.path.expanduser('~'), '.cache', 'huggingface', 'hub'); key = name.replace('.', '-'); tot = 0
    try:
        for d in os.listdir(hub):
            if key in d and 'whisper' in d:
                for r, _, fs in os.walk(os.path.join(hub, d)):
                    for f in fs:
                        try: tot += os.path.getsize(os.path.join(r, f))
                        except OSError: pass
    except OSError: pass
    return tot / 1e6
def model_status():
    ms = []
    for n in model_names():
        mb = hub_mb(n); total = MODEL_MB.get(n, 1500)
        ms.append({'name': n, 'mb': round(mb), 'total': total, 'ready': model_cached(n) and mb > total * 0.9})
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
    if e: sid = sid or e.get('sid'); t = t if t is not None else (e.get('start', 0) + e.get('end', 0)) / 2; text = text or e.get('title') or ''
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

# ---------------------------------------------------------------- job queue
import queue
RIJ_F = os.path.join(DATA, 'rij.json')

class _State(dict):
    """shared app state; job, cancel, why and proc belong to the worker thread that runs the job (two can run at once)"""
    LOCAL = ('job', 'cancel', 'why', 'proc')
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._tl = threading.local(); self._jobs = {}
    def _d(self):
        d = getattr(self._tl, 'd', None)
        if d is None: d = self._tl.d = {}
        return d
    def jobs(self): return [j for j in list(self._jobs.values()) if j]
    def get(self, k, default=None):
        if k in self.LOCAL:
            d = self._d()
            if k == 'job': return d.get('job') if 'job' in d else (self.jobs() or [None])[0]
            if k == 'cancel': return bool(d.get('cancel') or (d.get('job') or {}).get('cancel'))
            return d.get(k, default)
        return super().get(k, default)
    def __getitem__(self, k):
        if k in self.LOCAL: return self.get(k)
        return super().__getitem__(k)
    def __setitem__(self, k, v):
        if k in self.LOCAL:
            self._d()[k] = v
            if k == 'job':
                tid = threading.get_ident()
                if v: self._jobs[tid] = v
                else: self._jobs.pop(tid, None)
            return
        super().__setitem__(k, v)

class JobQueue(queue.Queue):
    """a normal queue that also keeps a readable list of what is waiting, and saves itself so it survives a restart"""
    TITLES = {'remux': 'Converting the recording to MP4', 'proxy': 'Making a working copy'}
    def __init__(self):
        super().__init__(); self.pending = []; self.items = []; self.running = {}; self.glock = threading.Lock(); self.slock = threading.Lock()
    def meta(self, kind, arg):
        if kind == 'render': return {'kind': kind, 'title': ('Preview: ' if arg.get('preview') else '') + (arg.get('hook') or arg.get('title') or ''), 'layout': arg.get('layout'), 'len': round(float(arg['end']) - float(arg['start'])), 'preview': bool(arg.get('preview'))}
        if kind == 'download': return {'kind': kind, 'title': arg.get('url', '')[:60]}
        if kind == 'analyse':
            try: t = load_sess(arg).get('title') or ''
            except Exception: t = ''
            return {'kind': kind, 'title': t}
        return {'kind': kind, 'title': self.TITLES.get(kind, '')}
    def put(self, item, *a, **k):
        kind, arg = item
        with self.slock: self.pending.append(self.meta(kind, arg)); self.items.append(item)
        super().put(item, *a, **k); self.save()
    def get(self, *a, **k):
        with self.glock:
            while True:
                item = super().get(*a, **k)
                with self.slock:
                    meta = self.pending.pop(0) if self.pending else {}
                    if self.items: self.items.pop(0)
                if not meta.get('skip'):
                    self.running[threading.get_ident()] = item; self.save(); return item
                self.save()
    def done(self):
        self.running.pop(threading.get_ident(), None); self.save()
    def put_front(self, item):
        """a quick preview goes before everything else"""
        kind, arg = item
        with self.slock: self.pending.insert(0, self.meta(kind, arg)); self.items.insert(0, item)
        with self.mutex:
            self.queue.appendleft(item); self.unfinished_tasks += 1; self.not_empty.notify()
    def remove(self, i):
        with self.slock:
            if 0 <= i < len(self.pending): self.pending[i]['skip'] = True
        self.save()
    def save(self):
        try:
            with self.slock:
                keep = list(self.running.values()) + [it for it, m in zip(self.items, self.pending) if not m.get('skip')]
            keep = [(kd, ag) for kd, ag in keep if not (isinstance(ag, dict) and ag.get('test'))]
            tmp = RIJ_F + '.tmp'; json.dump(keep, open(tmp, 'w', encoding='utf-8')); os.replace(tmp, RIJ_F)
        except Exception: pass
    def restore(self):
        try: items = json.load(open(RIJ_F, encoding='utf-8'))
        except Exception: return 0
        n = 0
        for kd, ag in items:
            try:
                if kd in ('analyse', 'remux', 'proxy'): load_sess(ag)
                elif kd == 'render': load_sess(ag['sid'])
                self.put((kd, ag)); n += 1
            except Exception: pass
        if n: log(f'The queue picks up where it was ({n} jobs)')
        return n

JOBS = JobQueue(); STATE = _State({'job': None, 'done': [], 'previews': {}})
ANALYSE_LOCK = threading.Lock()   # whisper is heavy: only one stream is analysed at a time

def is_live(): return bool(CUR['id'] or STATE.get('live'))
def paused():
    """heavy work waits while you stream or record, so your stream does not drop frames"""
    return bool(SET.get('pause_live', True) and is_live() and not STATE.get('run_live'))

# ---- learning how long things take on this pc (for a real "time left")
TEMPO_F = os.path.join(DATA, 'tempo.json')
def tempo_load():
    try: return json.load(open(TEMPO_F, encoding='utf-8'))
    except Exception: return {}
def tempo_key(kind, arg):
    if kind == 'render': return 'render_' + ('voorbeeld' if arg.get('preview') else 'montage' if arg.get('parts') else (arg.get('layout') or SET.get('layout', 'split')))
    return kind
def tempo_units(kind, arg):
    if kind == 'render': return max(1.0, float(arg.get('end', 0)) - float(arg.get('start', 0)))
    if kind in ('analyse', 'remux', 'proxy'):
        try: return max(1.0, float(load_sess(arg).get('duration') or 0))
        except Exception: return 0
    return 0
def tempo_est(kind, arg):
    u = tempo_units(kind, arg); L = tempo_load().get(tempo_key(kind, arg)) or tempo_load().get(kind) or []
    if not u or len(L) < 2: return None
    L = sorted(L)[-12:]; rate = L[len(L) // 2]
    return round(rate * u + 2, 1)
def tempo_note(kind, arg, secs):
    u = tempo_units(kind, arg)
    if not u or secs < 1: return
    d = tempo_load()
    for k in {tempo_key(kind, arg), kind}:
        d.setdefault(k, []).append(round(secs / u, 4)); d[k] = d[k][-20:]
    try: json.dump(d, open(TEMPO_F, 'w', encoding='utf-8'))
    except Exception: pass

# ---- clear error messages instead of Python errors
ERRORS = collections.deque(maxlen=30)
def friendly(txt, stage=''):
    t = str(txt or '')
    rules = [(r'No space left|Errno 28|disk full', 'Your disk is full. Free up space in System > Storage and try again.'),
             (r'Permission denied|Errno 13|being used by another process|WinError 32', 'I am not allowed to open a file. Is it still open in another program (a video player, for example)?'),
             (r'No such file|Errno 2|niet gevonden|does not exist', 'A file was not found. Was the recording moved or deleted?'),
             (r'out of memory|MemoryError|CUDA error|Cannot allocate', 'Your PC ran out of memory. Close other heavy programs and try again.'),
             (r'moov atom|Invalid data found|End of file|corrupt', 'The recording is damaged or not finished yet. Record as MKV in OBS and this will not happen again.'),
             (r'Error while opening encoder|amf|nvenc|qsv', 'Your graphics card did not cooperate. I will use the processor from now on; or set Graphics card to "Processor only" in Settings.'),
             (r'gestopt|stopped', 'Stopped.'),
             (r'urlopen|timed out|Temporary failure|getaddrinfo|ConnectionError|HTTP Error', 'No internet connection, or the website is not responding. Try again later.')]
    for pat, msg in rules:
        if re.search(pat, t, re.I): return msg
    return f'Something went wrong{" while " + stage.lower() if stage else ""}. Make an error report in System so it can be fixed.'
def note_error(where, exc_text):
    ERRORS.append({'at': time.time(), 'where': where, 'error': scrub(exc_text)[-3000:]})

RENDER_EXTRA = ('cuts', 'cap_shift', 'bleep', 'bg', 'round', 'border', 'divider', 'cap_anim', 'loop', 'unsure_left', 'brand')
Q_WORDS = {}   # the words of each short in its own timeline, for the quality check

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
        while paused() and kind != 'download' and not (kind == 'render' and isinstance(arg, dict) and (arg.get('preview') or arg.get('live'))):
            STATE['paused'] = True; time.sleep(2)
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

def restart_app(delay=1.5):
    def go():
        time.sleep(delay)
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
        if p == '/api/status':
            cur = None
            if CUR['id']:
                try:
                    cs = load_sess(CUR['id']); cur = {'id': cs['id'], 'title': cs.get('title'), 'start': cs.get('start'), 'markers': cs.get('markers', [])[-8:], 'n_markers': len(cs.get('markers', []))}
                except Exception: pass
            return self.j({'cur': cur, 'now': time.time(), 'obs': obs.ok, 'recording': bool(CUR['id']), 'job': STATE['job'], 'jobs': STATE.jobs(), 'queue': JOBS.qsize(), 'pending': [x for x in JOBS.pending if not x.get('skip')], 'done': STATE['done'][-10:], 'test': STATE.get('test'), 'ffmpeg': FF, 'settings': SET,
                           'version': VERSION, 'paused': paused() and bool(STATE.jobs() or JOBS.qsize()), 'live': bool(STATE.get('live')), 'health': health(), 'safe': SAFE['on'], 'update': bool(UPD.get('newer')),
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
            return self.file(os.path.join(FONT_DIR, os.path.basename(p)), 'font/ttf')
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
    for fn in (planner, proxy_loop, update_loop, backup_loop, phone_guard_loop, selftest, confirm_start, live_loop, trash_loop):
        threading.Thread(target=fn, daemon=True).start()
    log(f'Open http://localhost:{PORT} in your browser')
    if SET.get('phone'): phone_start()
    if os.name == 'nt' and '--no-browser' not in sys.argv:
        try: os.startfile(f'http://localhost:{PORT}')
        except Exception: pass
    srv.serve_forever()

if __name__ == '__main__':
    main()
