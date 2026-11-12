# CI test for the local AI model (plan F4.7): llama-server + Qwen2.5 1.5B, through the same code the app uses.
# run from JelE/clipper with engine/llama/llama-server and data/models/<model> in place.
import os, sys, time
sys.argv = ['clipper.py', '--no-server']
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, here); os.chdir(here)
import clipper as c
print('ready', c.llm_ready(), c.llm_exe(), os.path.getsize(c.llm_model()) // 1048576, 'MB')
t0 = time.time(); port = c.llm_start(); print('started on port', port, 'in', round(time.time() - t0, 1), 's', c.LLM['error'])
if not port: sys.exit(1)
ti = c.llm_titles('no way no way he was one hp and I hit the one tap oh my god', ['you said "no way"', 'chat went off'], 'Valorant', 'en')
print('TITLES', ti, 'RAW', repr(c.LLM.get('last')))
cases = ['could you trim it so it is a bit snappier, like 4 seconds', 'take the zoom out', 'zet de muziek uit', 'make the captions purple', 'begin 2 seconden later']
for q in cases: print('CMD', repr(q), '->', c.cmd_parse(q))
c.llm_stop()
ok = len(ti) >= 1 and all(c.cmd_parse(q) for q in cases)
print('LLM CI', 'GOOD' if ok else 'BAD'); sys.exit(0 if ok else 1)
