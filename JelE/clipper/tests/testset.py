# JelE Clipper test set: runs all layouts, effects and pages before every update.
# Usage: start the clipper, make sure it has a recording, and run: python tests/testset.py
import json, sys, time, urllib.request
BASE = 'http://localhost:8765'
def api(p, b=None):
    req = urllib.request.Request(BASE + p, data=json.dumps(b).encode() if b is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
def wait_idle(limit=900):
    t0 = time.time()
    while time.time() - t0 < limit:
        s = api('/api/status')
        if not s['jobs'] and not s['pending']: return s
        time.sleep(1.5)
    raise SystemExit('rij wordt niet leeg')
fails = []
def check(name, ok, info=''):
    print(('OK   ' if ok else 'FAIL ') + name + (' · ' + info if info else ''))
    if not ok: fails.append(name)
# 1: every page answers
for p in ('/', '/api/status', '/api/sessions', '/api/shorts', '/api/week', '/api/check', '/api/keys', '/api/backups', '/api/whatsnew', '/api/update-check', '/api/selftest', '/api/storage', '/api/music', '/api/plan', '/api/brands', '/api/insights', '/api/trash', '/api/changelog'):
    try: urllib.request.urlopen(BASE + p, timeout=60).read(); check('page ' + p, True)
    except Exception as e: check('page ' + p, False, str(e)[:80])
ss = [x for x in api('/api/sessions') if x.get('path') and x.get('duration')]
if not ss: raise SystemExit('geen opname om mee te testen')
sid = ss[0]['id']; t = min(30, ss[0]['duration'] / 3)
T0 = time.time()
# 2: every layout, with and without effects
jobs = []
for lay in ('split', 'frame', 'gameonly', 'landscape'):
    jobs.append(dict(sid=sid, start=t, end=t + 8, title=f'test_{lay}', hook='TESTSET', layout=lay, captions=False))
jobs.append(dict(sid=sid, start=t, end=t + 10, title='test_fx', hook='EFFECTS', layout='split', captions=False,
                 fx={'zooms': [t + 2], 'killfeed': [t + 3], 'stickers': [{'t': t + 4, 'dur': 1.5, 'text': 'ACE', 'kind': 'stamp', 'x': .5, 'y': .3}], 'teaser': {'t': 6, 'len': 1}, 'replay': {'a': 5, 'b': 7, 'speed': .5}}))
W = [[t + .2, t + .5, 'what'], [t + .6, t + .9, 'the'], [t + 1.0, t + 1.4, 'fuck'], [t + 3, t + 3.3, 'no'], [t + 3.4, t + 3.8, 'way']]
jobs.append(dict(sid=sid, start=t, end=t + 8, title='test_61', hook='6.1', layout='frame', captions=True, words=W, bg='gradient', round=True, border=True,
                 bleep=True, cap_anim='word', cap_shift=.2, cuts=[[t + 1.6, t + 2.6]]))
jobs.append(dict(sid=sid, start=t, end=t + 8, title='test_61b', layout='split', captions=True, words=W, divider=False, cap_anim='type'))
for j in jobs: api('/api/render', j)
pv = api('/api/preview', dict(sid=sid, start=t, end=t + 6, layout='split', captions=True, words=W))
s = wait_idle()
done = [d for d in s['done'] if d['at'] >= T0]
for d in done: check('short ' + (d.get('title') or '?'), d['ok'], d.get('why') or d.get('file') or '')
check('number of shorts', len(done) == len(jobs), f'{len(done)} of {len(jobs)}')
pr = api('/api/preview?id=' + pv['id']); check('preview of the result', bool(pr.get('ok')), pr.get('why') or pr.get('file') or '')
# 3: clean up the test shorts
for d in done:
    if d.get('file'): api('/api/delete-short', {'file': d['file']})
print('\n' + ('ALL GOOD' if not fails else f'{len(fails)} FAILURE(S): ' + ', '.join(fails)))
sys.exit(1 if fails else 0)
