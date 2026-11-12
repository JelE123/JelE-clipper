# JelE Clipper speed test (plan F1.8): measures the speed goals on this pc and writes a short report.
# Usage: start the clipper, then run: python tests/bench.py [report.md]
# It makes its own 4 minute test video, imports it, lets the Clipper find the moments and renders one short.
import json, os, sys, time, subprocess, tempfile, urllib.request

BASE = 'http://localhost:8765'
GOALS = {'page': 1.0, 'api': 0.2, 'analyse_per_min': 30.0, 'render': 120.0}   # seconds; on a normal pc without graphics card


def api(p, b=None, timeout=60):
    req = urllib.request.Request(BASE + p, data=json.dumps(b).encode() if b is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b'{}')


def timed(fn):
    t = time.perf_counter(); fn(); return time.perf_counter() - t


def wait_idle(limit=1800):
    t0 = time.time()
    while time.time() - t0 < limit:
        s = api('/api/status')
        if not s.get('jobs') and not s.get('pending') and not s.get('queue'): return s
        time.sleep(1)
    raise SystemExit('the queue does not get empty')


def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'


def make_video(path, minutes=4):
    # moving picture, quiet sound with a few loud bursts (so there is something to find)
    dur = int(minutes * 60)
    loud = '+'.join(f'between(t\\,{a}\\,{a + 3})' for a in range(25, dur - 10, 50))   # commas escaped for ffmpeg
    subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', f'testsrc2=size=1920x1080:rate=30:duration={dur}',
                    '-f', 'lavfi', '-i', f'aevalsrc=0.05*sin(2*PI*220*t)*(1+12*({loud})):s=48000:d={dur}',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28', '-c:a', 'aac', '-shortest', path], check=True)
    return dur


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    R = {}
    R['page'] = timed(lambda: urllib.request.urlopen(BASE + '/', timeout=30).read())
    R['api'] = sum(timed(lambda: api('/api/status')) for _ in range(20)) / 20
    vid = os.path.join(tempfile.gettempdir(), 'jele_bench.mp4')
    t = time.perf_counter(); dur = make_video(vid); R['make_video'] = time.perf_counter() - t
    wait_idle()
    t = time.perf_counter(); r = api('/api/import', {'path': vid}); sid = r['sid']
    while time.perf_counter() - t < 1800:   # until the moments are found (the automatic shorts after that do not count)
        ss = [x for x in api('/api/sessions') if x['id'] == sid]
        if ss and ss[0].get('status') in ('klaar', 'onderbroken'): break
        time.sleep(0.5)
    R['analyse'] = time.perf_counter() - t
    wait_idle()
    R['analyse_per_min'] = R['analyse'] / (dur / 60)
    n0 = len(api('/api/status').get('done') or [])
    t = time.perf_counter()
    api('/api/render', {'sid': sid, 'start': 20, 'end': 40, 'title': 'bench', 'hook': 'SPEED TEST', 'layout': 'split', 'captions': True})
    wait_idle(); R['render'] = time.perf_counter() - t
    done = api('/api/status').get('done') or []
    R['render_ok'] = bool(done[len(done) - 1].get('ok')) if len(done) > n0 else False
    for d in done:
        if d.get('title') == 'bench' and d.get('file'):
            try: api('/api/delete-short', {'file': d['file']})
            except Exception: pass
    ok = lambda k: '✅' if R[k] <= GOALS[k] else '❌'
    rows = [('Open the app', 'page', f"{R['page']:.2f} s"), ('Answer of the app (average)', 'api', f"{R['api'] * 1000:.0f} ms"),
            ('Find the moments, per minute of video', 'analyse_per_min', f"{R['analyse_per_min']:.1f} s"),
            ('Render a 20 s short with captions', 'render', f"{R['render']:.1f} s" + ('' if R['render_ok'] else ' (failed)'))]
    md = ['### Speed test', '', f'On the test pc of GitHub ({os.cpu_count()} cores, no graphics card), with a {dur // 60} minute test video.', '',
          '| What | Result | Goal | |', '|---|---|---|---|']
    for name, k, val in rows:
        goal = f"{GOALS[k] * 1000:.0f} ms" if k == 'api' else f"{GOALS[k]:g} s"
        md.append(f'| {name} | {val} | under {goal} | {ok(k)} |')
    text = '\n'.join(md) + '\n'
    print(text); print(json.dumps(R))
    if out: open(out, 'w', encoding='utf-8').write(text)
    return 0 if R['render_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
