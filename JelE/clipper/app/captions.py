# JelE Clipper part: captions. Loaded by clipper.py into one shared namespace, do not run on its own.
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
FILLERS = re.compile(r"^(u+h+m*|u+m+|e+r+m+|e+h+m*|h+m+|mm+|ehm|uhm)[.,!?]*$", re.I)
def drop_fillers(words):
    """uh, um, ehm: out of the captions (the sound stays)"""
    if not SET.get('cap_fillers', True): return words
    return [w for w in words if not FILLERS.match(w[2])]

def name_pairs():
    """two-word names (game words and your own words) that must stay on one caption line"""
    out = set()
    try:
        if gamewords: out |= {k for k in gamewords.canon(cur_game())[0] if k.count(' ') == 1}
    except Exception: pass
    out |= {w.strip().lower() for w in re.split(r'[,\n]+', SET.get('vocab') or '') if w.strip().count(' ') == 1}
    return out

def caption_groups(words):
    """words -> caption lines. you can steer it in the editor (plan F3.4): a word that starts with ¶ starts a new line,
    a word that ends with ~ stays on one line with the next word"""
    groups = []; cur = []; pairs = name_pairs(); forced = set(); glued = set()
    for w in words:
        txt = w[2]
        brk = txt.startswith('\u00b6'); glue = bool(cur) and cur[-1][2].endswith('~')
        if brk: txt = txt.lstrip('\u00b6').strip()
        w = (w[0], w[1], txt) + tuple(w[3:])
        if brk and cur: groups.append(cur); forced.add(len(groups)); cur = []; cur.append(w); continue
        if glue and sum(len(x[2]) + 1 for x in cur) + len(txt) <= 26: glued.add(len(groups)); cur.append(w); continue
        pair = bool(cur) and (re.sub(r"[^\w' ]", '', cur[-1][2].lower()) + ' ' + re.sub(r"[^\w' ]", '', txt.lower())) in pairs
        if pair and sum(len(x[2]) + 1 for x in cur) + len(txt) <= 24 and txt != UNCLEAR: cur.append(w); continue   # never split a name over two lines
        if cur and (txt == UNCLEAR or cur[-1][2] == UNCLEAR or len(cur) >= 3 or w[0] - cur[-1][1] > 0.5 or sum(len(x[2]) + 1 for x in cur) + len(txt) > 17 or re.search(r'[.!?,]$', cur[-1][2])):
            groups.append(cur); cur = []
        cur.append(w)
    if cur: groups.append(cur)
    # 6.1: a lonely word joins its neighbour when they belong together (close in time, still short enough). never over your own line break
    def fits(a, b): return len(a) + len(b) <= 4 and sum(len(x[2]) + 1 for x in a + b) <= 21 and b[0][0] - a[-1][1] <= 0.45 and UNCLEAR not in [x[2] for x in a + b] and not re.search(r'[.!?]$', a[-1][2])
    i = 0
    while i < len(groups):
        g = groups[i]
        if len(g) == 1 and not EMPH.match(g[0][2]):
            if i + 1 < len(groups) and (i + 1) not in forced and fits(g, groups[i + 1]): groups[i:i + 2] = [g + groups[i + 1]]; forced = {f - 1 if f > i else f for f in forced}; continue
            if i > 0 and i not in forced and fits(groups[i - 1], g): groups[i - 1:i + 1] = [groups[i - 1] + g]; forced = {f - 1 if f > i - 1 else f for f in forced}; i -= 1; continue
        i += 1
    return [[(x[0], x[1], x[2].rstrip('~')) + tuple(x[3:]) for x in g] for g in groups]

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
    room = W - 80 if W >= 1500 else W - 200   # vertical: stay clear of the buttons on the right of TikTok and Reels
    if total > room and scale > 0.3:
        return draw_caption(words, active, scale * room / total, W, H, style)
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
    ws = [(max(0, a - clip_start), max(0, b - clip_start), t) for a, b, t in drop_fillers(words) if b > clip_start and a < clip_start + dur]
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
