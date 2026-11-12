# JelE Clipper: hearing what happens without words (plan F2.5)
# laughing, screaming, cheering, gunshots and music, found from the sound itself with simple measurements
# (no AI model needed). runs over the whole recording in pieces of a minute, so it stays light.
#
# per half second you get a few numbers:
#   laugh  0..1   short bursts of voice, 3.5 to 7 times a second, the same pitch again and again ("ha ha ha")
#   scream 0..1   much louder than you normally talk, high and long
#   cheer  0..1   lots of noise with no rhythm and no tone for a while (a crowd, a team going wild)
#   shots  count  sharp bangs that start out of nothing and die away fast
#   music  0..1   steady tones that last (a song in the background, a menu)

SOUND_SR = 16000
SOUND_HOP = 0.010          # 10 ms per small piece

def _sound_read(path, amap, start, dur):
    import numpy as np
    r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-ss', f'{max(0, start):.2f}', '-t', f'{dur:.2f}', '-i', path] + amap +
                       ['-vn', '-ac', '1', '-ar', str(SOUND_SR), '-f', 's16le', '-'], capture_output=True, creationflags=NOWIN)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0

def sound_frames(x, sr=SOUND_SR):
    """small pieces of 10 ms: loudness (dB), how bright, how noisy (flatness), and how strongly it repeats (voice pitch)"""
    import numpy as np
    hop = int(sr * SOUND_HOP); win = hop * 3
    n = max(0, (len(x) - win) // hop + 1)
    if n == 0: return None
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    fr = x[idx] * np.hanning(win)[None, :]
    rms = np.sqrt((fr ** 2).mean(1)) + 1e-7
    db = 20 * np.log10(rms)
    sp = np.abs(np.fft.rfft(fr, axis=1)) + 1e-9
    fq = np.fft.rfftfreq(win, 1.0 / sr)
    cent = (sp * fq[None, :]).sum(1) / sp.sum(1)
    flat = np.exp(np.log(sp).mean(1)) / sp.mean(1)
    # voice pitch strength: autocorrelation peak between 80 and 500 Hz
    ac = np.fft.irfft(sp ** 2, axis=1)[:, :win // 2]
    lo, hi = int(sr / 500), int(sr / 80)
    pk = ac[:, lo:hi].max(1) / (ac[:, 0] + 1e-9)
    f0 = sr / (lo + ac[:, lo:hi].argmax(1))
    return {'db': db, 'cent': cent, 'flat': flat, 'voiced': np.clip(pk, 0, 1), 'f0': f0}

def _mod_strength(env, lo=3.5, hi=7.0, fs=1.0 / SOUND_HOP):
    """how much of the loudness wobble falls between lo and hi times a second (laughing is 4-6)"""
    import numpy as np
    e = env - env.mean()
    if len(e) < 32 or e.std() < 1e-3: return 0.0
    sp = np.abs(np.fft.rfft(e * np.hanning(len(e)))) ** 2
    f = np.fft.rfftfreq(len(e), 1.0 / fs)
    band = sp[(f >= lo) & (f <= hi)].sum(); tot = sp[(f >= 0.5) & (f <= 20)].sum() + 1e-9
    peak = sp[(f >= lo) & (f <= hi)].max() if band > 0 else 0
    return float(min(1.0, (band / tot) * 1.4)) * float(min(1.0, peak / (band + 1e-9) * 3))

def _laugh_score(ld, vo, f0):
    """laughing = 4 or more short voice bursts in a row with a steady beat: bursts about as long as each other,
    gaps about as long as each other, 3.5 to 7 a second, and almost the same pitch. talking is much less regular"""
    import numpy as np
    x = ld.astype(np.int8); ed = np.diff(np.concatenate([[0], x, [0]]))
    st, en = np.where(ed == 1)[0], np.where(ed == -1)[0]
    keep = [(a, b) for a, b in zip(st, en) if 4 <= b - a <= 25]          # bursts of 40 to 250 ms
    if len(keep) < 4: return 0.0
    L = np.array([b - a for a, b in keep], dtype=float); G = np.array([keep[i + 1][0] - keep[i][1] for i in range(len(keep) - 1)], dtype=float)
    per = np.array([keep[i + 1][0] - keep[i][0] for i in range(len(keep) - 1)], dtype=float) * SOUND_HOP
    rate = 1.0 / per.mean() if per.mean() > 0 else 0
    if not 3.2 <= rate <= 7.5: return 0.0
    cv = lambda v: float(np.std(v) / (np.mean(v) + 1e-9))
    pit = np.array([np.median(f0[a:b][vo[a:b] > 0.3]) if (vo[a:b] > 0.3).sum() >= 2 else np.nan for a, b in keep])
    pit = pit[~np.isnan(pit)]
    if len(pit) < 3: return 0.0
    reg = max(0.0, 1 - cv(L) / 0.45) * max(0.0, 1 - cv(G) / 0.6) * max(0.0, 1 - cv(per) / 0.35)
    same = max(0.0, 1 - cv(pit) / 0.15)
    voiced = float(np.mean(vo[ld]) if ld.any() else 0)
    return round(float(np.clip(reg * same * min(1.0, voiced * 1.6) * 1.8, 0, 1)), 2)

def sound_scan(x, base_db=None, step=0.5, voice=True):
    """one piece of sound -> per half second: laugh, scream, cheer, shots, music"""
    import numpy as np
    F = sound_frames(x)
    if F is None: return []
    db, cent, flat, vo, f0 = F['db'], F['cent'], F['flat'], F['voiced'], F['f0']
    per = int(step / SOUND_HOP); nb = len(db) // per
    if base_db is None: base_db = float(np.percentile(db, 60))
    loud = db > base_db - 2
    out = []
    # gunshots: a jump of 18 dB or more within 30 ms, broadband, and 150 ms later much quieter again
    on = np.zeros(len(db), dtype=bool)
    for i in range(3, len(db) - 15):
        if db[i] - db[i - 3] > 18 and db[i] > base_db + 6 and flat[i] > 0.12 and db[i] - db[i + 15] > 9 and not on[i - 8:i].any(): on[i] = True
    for b in range(nb):
        a0, a1 = b * per, (b + 1) * per
        w0, w1 = max(0, a0 - per), min(len(db), a1 + per)       # look 1.5 s wide for the rhythm
        seg_db = db[w0:w1]; ld = loud[w0:w1]
        r = {'laugh': 0.0, 'scream': 0.0, 'cheer': 0.0, 'shots': int(on[a0:a1].sum()), 'music': 0.0}
        if voice and ld.mean() > 0.3:
            r['laugh'] = _laugh_score(ld, vo[w0:w1], f0[w0:w1])
        hi = db[a0:a1] > base_db + 14
        if voice and hi.mean() > 0.6:
            r['scream'] = round(float(np.clip((np.mean(db[a0:a1]) - base_db - 14) / 10 + 0.4, 0, 1) * (1 if np.mean(cent[a0:a1]) > 900 else 0.5)), 2)
        if not voice:
            noisy = (flat[w0:w1] > 0.25) & ld
            if noisy.mean() > 0.7 and _mod_strength(seg_db, 2, 8) < 0.25 and np.mean(seg_db) > base_db + 3:
                r['cheer'] = round(float(min(1, (noisy.mean() - 0.7) / 0.3 + 0.3)), 2)
        tonal = (flat[a0:a1] < 0.15) & loud[a0:a1]
        r['music'] = round(float(tonal.mean()), 2) if loud[a0:a1].mean() > 0.92 else 0.0   # music has no pauses, talking does
        out.append(r)
    # music only counts when it lasts: 20 s of steady tones in a row
    mus = np.array([o['music'] for o in out])
    if len(mus):
        k = int(20 / step); sm = np.convolve(mus, np.ones(k) / k, mode='same') if len(mus) >= k else np.zeros_like(mus)
        for o, v in zip(out, sm): o['music'] = round(float(v), 2) if v > 0.55 else 0.0
    return out

def sound_events(path, dur, step=0.5, on_prog=None):
    """the whole recording, a minute at a time: your mic for laughing and screaming, the rest for shots, cheering and music"""
    import numpy as np
    mic = mic_map(path)
    allmap = []
    n = len(audio_tracks(path)) if os.path.exists(path) else 1
    if mic and n > 1:   # the game sound: the first track that is not your mic
        ms = int(mic[1].split(':')[-1]) if len(mic) > 1 else -1
        other = next((i for i in range(n) if i != ms), 0); allmap = ['-map', f'0:a:{other}']
    T = int(dur / step) + 1
    res = [{'laugh': 0.0, 'scream': 0.0, 'cheer': 0.0, 'shots': 0, 'music': 0.0} for _ in range(T)]
    CH = 60.0; t = 0.0; base_v = None; base_g = None
    while t < dur:
        d = min(CH + 1.5, dur - t)
        xv = _sound_read(path, mic, t, d)
        if len(xv) > SOUND_SR:
            if base_v is None: base_v = float(np.percentile(20 * np.log10(np.abs(xv[::40]) + 1e-5), 75)) - 6
            for k, r in enumerate(sound_scan(xv, None, step, voice=True)):
                i = int(t / step) + k
                if i < T: res[i]['laugh'] = r['laugh']; res[i]['scream'] = r['scream']; res[i]['music'] = r['music']
        if True:   # the game sound for bangs and cheering (all audio when there is no separate mic track)
            xg = _sound_read(path, allmap, t, d) if mic else xv
            if len(xg) > SOUND_SR:
                for k, r in enumerate(sound_scan(xg, None, step, voice=False)):
                    i = int(t / step) + k
                    if i < T: res[i]['shots'] = r['shots']; res[i]['cheer'] = r['cheer']; res[i]['music'] = max(res[i]['music'], r['music'])
        t += CH
        if on_prog: on_prog(min(1.0, t / max(1.0, dur)))
    return res

def sound_moments(res, step=0.5):
    """from the numbers per half second to a score and a reason per half second"""
    import numpy as np
    T = len(res); sc = np.zeros(T, dtype=np.float32); why = [None] * T
    lg = np.array([r['laugh'] for r in res]); scr = np.array([r['scream'] for r in res])
    ch = np.array([r['cheer'] for r in res]); sh = np.array([r['shots'] for r in res], dtype=np.float32); mu = np.array([r['music'] for r in res])
    k = int(2 / step)
    lg2 = np.convolve(lg > 0.45, np.ones(k), mode='same')          # laughing for at least a second
    sh3 = np.convolve(sh, np.ones(int(3 / step)), mode='same')      # 3 or more bangs within 3 seconds = a fight
    for i in range(T):
        if lg2[i] >= 2: sc[i] += 1.5; why[i] = 'you laughed'
        if scr[i] > 0.5: sc[i] += 1.5 * scr[i]; why[i] = why[i] or 'you screamed'
        if ch[i] > 0.5: sc[i] += 1.0; why[i] = why[i] or 'cheering'
        if sh3[i] >= 3: sc[i] += min(1.2, 0.25 * sh3[i]); why[i] = why[i] or f'a fight ({int(sh3[i])} shots)'
        if mu[i] > 0: sc[i] -= 0.4          # long music: a menu, a break, a song
    return sc, why
