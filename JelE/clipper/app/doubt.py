# the doubt check: words the speech model was not sure about get a second chance.
# 1. listen again to just that bit, with a better model and the words around it as a hint
# 2. collect options: what it heard the second time, what you corrected before, game names and names on the screen
# 3. pick what fits the sentence best (the local AI helps when it is on). still not sure: you get the options to click

DOUBT_TL = threading.local()   # what the last check changed: {start of the old word: new text}
DOUBT_MAX = 40   # bits to listen to again per run (keeps it quick)
def _core(t): return re.sub(r"^[^\w]+|[^\w']+$", '', t or '')

def doubt_pass(sid, path, words, unsure, ranges, names=(), budget=120, on_prog=None):
    """words: [(a, b, text, ...)], unsure: start times. only looks inside ranges [(a, b)].
    -> (words, unsure_left, opts {ms: [options]}, fixed count)"""
    t0 = time.time(); U = {round(u, 2) for u in unsure}; game = cur_game()
    idx = [i for i, w in enumerate(words) if (round(w[0], 2) in U or w[2] == UNCLEAR) and any(a <= w[0] <= b for a, b in ranges)]
    if not idx: return words, sorted(U), {}, 0
    wins = []
    for i in idx:
        s_, e_ = words[i][0], words[i][1]
        if wins and s_ - wins[-1][1] < 2.0 and e_ - wins[-1][0] < 12: wins[-1][1] = max(wins[-1][1], e_); wins[-1][2].append(i)
        else: wins.append([s_, e_, [i]])
    wins = wins[:DOUBT_MAX]; idx = [i for w in wins for i in w[2]]
    cands = {i: {} for i in idx}; multi = {}   # multi: unclear bit -> the words heard there the second time
    orig = {i: words[i][2] for i in idx}
    def add(i, t, sc):
        t = t.strip()
        if t: cands[i][t] = cands[i].get(t, 0) + sc
    work = os.path.join(sdir(sid), 'tmp_doubt'); os.makedirs(work, exist_ok=True)
    langs = [cur_lang()]
    if SET.get('mixed_lang', True) and cur_lang() not in ('en', 'auto'): langs.append('en')   # Dutch and English mixed in one sentence
    old_lang = getattr(LANG_TL, 'v', None)
    try:
        if whisper_ok():
            for k, (a, b, ii) in enumerate(wins):
                if time.time() - t0 > budget: log('Doubt check: out of time, the rest stays marked'); break
                if on_prog: on_prog(k / max(1, len(wins)))
                a0 = max(0, a - 1.5); b0 = b + 1.0
                ctx = ' '.join(w[2] for w in words if a0 - 8 <= w[0] < a0 and w[2] != UNCLEAR)[-160:]
                hint = [ctx] if ctx else []
                hint += [x for i in ii for x in gamewords.similar(orig[i], game, names)] if gamewords else []
                wav = os.path.join(work, 'd.wav'); extract_wav(path, a0, b0 - a0, wav)
                for lg in langs:
                    LANG_TL.v = lg; PROMPT_TL.v = hint
                    try: got = transcribe(wav, 'captions')
                    except Exception: traceback.print_exc(); got = []
                    finally: PROMPT_TL.v = []
                    uns2 = set(getattr(UNSURE_TL, 'v', []) or [])
                    done_ = True
                    for i in ii:
                        s_, e_ = words[i][0] - a0, words[i][1] - a0
                        ov = [g for g in got if g[2] != UNCLEAR and g[0] < e_ + 0.08 and g[1] > s_ - 0.08]
                        if orig[i] == UNCLEAR:
                            if ov and all(round(g[0], 2) not in uns2 for g in ov): multi[i] = [(round(g[0] + a0, 2), round(g[1] + a0, 2), g[2]) for g in ov]
                            elif not multi.get(i): done_ = False
                            continue
                        if not ov: done_ = False; continue
                        g = max(ov, key=lambda g: min(g[1], e_) - max(g[0], s_))
                        sure = round(g[0], 2) not in uns2
                        add(i, g[2], (2.0 if sure else 0.8) * (1 if lg == langs[0] else 0.9))
                        if not sure: done_ = False
                    if done_: break   # sure in the first language: no need to try English
    finally:
        LANG_TL.v = old_lang; shutil.rmtree(work, ignore_errors=True)
    L = word_learn()
    for i in idx:
        t = orig[i]
        if t == UNCLEAR: continue
        add(i, t, 0.5)   # what it heard first is still a fair guess
        k = _wk(t); near = {_wk(x[2]) for x in words[max(0, i - 3):i] + words[i + 1:i + 4]}
        for f, e in (L.get(k) or {}).items(): add(i, f, 1.0 + (1.5 if near & set(e.get('ctx') or []) else 0) + 0.3 * min(3, e.get('n', 1)))
        if gamewords:
            gameish = any(gamewords.CUES.match(_core(x[2]).lower()) or _core(x[2]).lower() in {n.lower() for n in gamewords._names(game)} for x in words[max(0, i - 5):i + 6] if x is not words[i])
            for nm in gamewords.similar(t, game, ()): add(i, re.sub(re.escape(_core(t)), nm, t, count=1), 0.6 + (0.8 if gameish else 0))
            for nm in gamewords.similar(t, game, names, 5):
                if nm in names: add(i, re.sub(re.escape(_core(t)), nm, t, count=1), 1.5)   # it is on the screen right now
    # the local AI picks between the options, with the whole sentence (one question for all of them)
    open_ = [i for i in idx if len(cands[i]) > 1]
    if open_ and SET.get('llm_judge', True):
        try:
            if llm_ready():
                lines = []
                for n_, i in enumerate(open_[:25], 1):
                    ctx = ' '.join(('[?]' if j == i else x[2]) for j, x in enumerate(words[max(0, i - 8):i + 6], max(0, i - 8)))
                    lines.append(f'{n_}. "{ctx}"  options: ' + ' / '.join(sorted(cands[i], key=lambda t: -cands[i][t])[:4]))
                msg = ('A gamer streaming ' + (game or 'a game') + ' said these sentences. One word is unclear, shown as [?]. Pick the option that makes the most sense. '
                       'Answer only JSON like {"1": "option", "2": "option"}.\n' + '\n'.join(lines))
                r = llm_chat([{'role': 'user', 'content': msg}], max_tokens=300, port=llm_start())
                m = re.search(r'\{.*\}', r or '', re.S); ans = json.loads(m.group(0)) if m else {}
                for n_, i in enumerate(open_[:25], 1):
                    v = str(ans.get(str(n_)) or '').strip()
                    if v in cands[i]: cands[i][v] += 1.5
        except Exception: traceback.print_exc()
    # decide
    rep = {}; left = set(U); opts = {}; fixed = 0
    for i in idx:
        st = round(words[i][0], 2)
        if orig[i] == UNCLEAR:
            if multi.get(i): rep[i] = multi[i]; left.discard(st); fixed += 1
            continue
        rk = sorted(cands[i].items(), key=lambda x: -x[1])
        best, sc = rk[0]; sec = rk[1][1] if len(rk) > 1 else 0
        if sc >= 1.8 and sc - sec >= 0.8:
            left.discard(st)
            if best != orig[i]: rep[i] = [(words[i][0], words[i][1], best) + tuple(words[i][3:])]; fixed += 1
        else: opts[str(int(round(st * 100)))] = [t for t, _ in rk[:4]]
    out = []
    for i, w in enumerate(words): out += rep.get(i, [w])
    DOUBT_TL.changes = {round(words[i][0], 2): ' '.join(x[2] for x in ws_) for i, ws_ in rep.items()}
    if fixed or opts: log(f'Doubt check: {fixed} unsure word(s) filled in, {len(opts)} left for you to pick')
    return out, sorted(left), opts, fixed

def opts_file(sid): return os.path.join(sdir(sid), 'twijfel_opties.json')
def load_opts(sid):
    try: return json.load(open(opts_file(sid), encoding='utf-8'))
    except Exception: return {}
def save_opts(sid, o):
    try: d = load_opts(sid); d.update(o); json.dump(d, open(opts_file(sid), 'w', encoding='utf-8'))
    except Exception: pass

def doubt_range(sid, a, b):
    """the editor's 'Check unsure words': the doubt check for one clip. -> fixes the editor can show"""
    s = load_sess(sid); words = load_transcript(sid); uns = load_unsure(sid)
    names = []
    for m in s.get('moments', []):
        if m.get('start', 0) < b and m.get('end', 0) > a: names += m.get('screen_names') or []
    new, left, opts, n = doubt_pass(sid, s['path'], words, uns, [(a, b)], names)
    ch = getattr(DOUBT_TL, 'changes', None) or {}
    fixes = [{'t': t, 'text': x} for t, x in ch.items()]
    if ch:   # keep one word per word (the editor counts words), an unclear bit becomes one piece of text
        raw = [tuple(w) for w in json.load(open(os.path.join(sdir(sid), 'transcript.json'), encoding='utf-8'))]
        raw = [(w[0], w[1], ch[round(w[0], 2)]) + tuple(w[3:]) if round(w[0], 2) in ch else w for w in raw]
        json.dump(raw, open(os.path.join(sdir(sid), 'transcript.json'), 'w', encoding='utf-8'))
    save_opts(sid, opts)
    try: json.dump(sorted(set(left)), open(os.path.join(sdir(sid), 'twijfel.json'), 'w', encoding='utf-8'))
    except Exception: pass
    return {'ok': True, 'fixes': fixes, 'opts': opts, 'left': len([u for u in left if a <= u <= b]), 'n': n}
