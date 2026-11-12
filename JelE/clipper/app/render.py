# JelE Clipper part: rendering a short. Loaded by clipper.py into one shared namespace, do not run on its own.
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
    if job.get('fresh_words'):   # made again with new captions (maybe in another language): listen again
        prog('Listening to what you say', 4); wav = os.path.join(work, 'a.wav'); extract_wav(path, start, dur, wav)
        return [(a + start, b + start, w) for a, b, w in transcribe(wav, 'captions', lambda f: prog(None, 5 + 25 * f))]
    tw = [] if os.path.exists(os.path.join(sdir(sid), 'transcript_bron.json')) else load_transcript(sid)   # the whole stream was already heard: reuse it (not when heard with the light model during the stream)
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
        if job.get('remake_of'): lib[os.path.basename(dst)]['remake_of'] = job['remake_of']
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
