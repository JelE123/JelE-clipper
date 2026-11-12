# CI test for the local AI model (plan F4.7): llama-server + Qwen2.5, through the same code the app uses.
# run from JelE/clipper with engine/llama/llama-server and the model in data/models. LLM_SIZE=small|smart
import os, sys, time
sys.argv = ['clipper.py', '--no-server']
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, here); os.chdir(here)
import clipper as c
c.SET['llm_size'] = os.environ.get('LLM_SIZE', 'small')
print('ready', c.llm_ready(), c.llm_model(), os.path.getsize(c.llm_model()) // 1048576, 'MB')
t0 = time.time(); port = c.llm_start(); print('started on port', port, 'in', round(time.time() - t0, 1), 's', c.LLM['error'])
if not port: sys.exit(1)
ti = c.llm_titles('no way no way he was one hp and I hit the one tap oh my god', ['you said "no way"', 'chat went off'], 'Valorant', 'en')
print('TITLES', ti, 'RAW', repr(c.LLM.get('last')))
W = lambda txt, a=0: [[a + i * 0.4, a + i * 0.4 + 0.3, w] for i, w in enumerate(txt.split())]
good = {'start': 0, 'end': 18, 'reasons': ['you laughed', 'chat went off', 'a fight (6 shots)'], 't': 12}
bad = {'start': 0, 'end': 25, 'reasons': ['it suddenly got loud'], 't': 12}
t0 = time.time()
jg = c.llm_judge(good, W('okay okay one more push three of them wait WAIT I got all three ACE no way bro chat ace I am shaking'), 'Valorant', 'en', port)
jb = c.llm_judge(bad, W('so yeah I was thinking maybe we buy a vandal this round uh I do not know what do you guys think okay sure'), 'Valorant', 'en', port)
print('JUDGE good', jg, '| bad', jb, '|', round(time.time() - t0, 1), 's')
cases = ['could you trim it so it is a bit snappier, like 4 seconds', 'take the zoom out', 'zet de muziek uit', 'make the captions purple', 'begin 2 seconden later']
for q in cases: print('CMD', repr(q), '->', c.cmd_parse(q))
odd = c.cmd_parse('the ending feels a bit flat and the song is way too loud')
print('CMD (model)', odd)
c.llm_stop()
ok = len(ti) >= 1 and all(c.cmd_parse(q) for q in cases) and jg and jb and jg['score'] > jb['score']
print('LLM CI', 'GOOD' if ok else 'BAD'); sys.exit(0 if ok else 1)
