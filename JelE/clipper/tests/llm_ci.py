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
tl = ['   0s you say: "this guy has been camping all game"', '   4s you say: "I am going to sneak behind him"', '   9s you say: "shh shh"', '  13s game sound: 1 gunshot',
      '  13s screen: you are dead', '  14s you: laughing', '  15s you say: "he turned around he was waiting for me"', '  16s chat: 18 messages in 10s', '  19s you say: "unbelievable"', '  30s you say: "okay next round"']
t0 = time.time(); raw_br = c.llm_brief({'t': 13}, tl, 100.0, 'Valorant', 'en', port)
items = [{'t': 100.0, 'e': 102.5, 'k': 'say', 'v': 'this guy has been camping all game'}, {'t': 104.0, 'e': 106.0, 'k': 'say', 'v': 'I am going to sneak behind him'},
         {'t': 109.0, 'e': 109.8, 'k': 'say', 'v': 'shh shh'}, {'t': 113.0, 'k': 'game sound', 'v': '1 gunshot'}, {'t': 113.0, 'k': 'screen', 'v': 'you are dead'},
         {'t': 114.0, 'k': 'you', 'v': 'laughing'}, {'t': 115.0, 'e': 117.5, 'k': 'say', 'v': 'he turned around he was waiting for me'}, {'t': 116.0, 'k': 'chat', 'v': '18 messages'},
         {'t': 119.0, 'e': 119.8, 'k': 'say', 'v': 'unbelievable'}, {'t': 130.0, 'e': 131.0, 'k': 'say', 'v': 'okay next round'}]
br = c.brief_merge(raw_br, c.brief_rules({'t': 113}, items, 100.0, 113.0), items)
print('BRIEF raw', raw_br, '| merged', {k: br.get(k) for k in ('start', 'payoff', 'end', 'zoom', 'about')}, round(time.time() - t0, 1), 's')
mum = ['   0s screen: END SCREEN: the match is over, scoreboard', '   2s you say: "uh yeah so … … that was … okay"', '   6s speech: 55% of the words are unclear (mumbling)',
       '   9s you say: "hmm … I think … yeah whatever"', '  14s you say: "okay … let me … queue again maybe"', '   0s note: no game events, no gunshots, no chat activity, no laughing or screaming in this part']
bm = c.llm_brief({'t': 8}, mum, 500.0, 'Valorant', 'en', port)
jm = c.llm_judge({'start': 500, 'end': 520, 'reasons': ['it suddenly got loud', 'end screen after the match'], 't': 508},
                 W('uh yeah so that was okay hmm I think yeah whatever okay let me queue again maybe', 500), 'Valorant', 'en', port)
print('MUMBLE brief', bm, '| judge', jm)
tox = ['   0s you say: "okay we need this round"', '   4s on screen (chat): "xToxicGuy: jele is the worst player ever uninstall"', '  10s game sound: 2 gunshots',
       '  18s you say: "wait what did he say"', '  19s you say: "he said jele is the worst player ever uninstall"', '  22s you: screaming', '  23s you say: "WHAT bro I have 30 kills"',
       '  26s chat: 25 messages in 10s', '  29s you say: "okay okay focus"']
bt_raw = c.llm_brief({'t': 22}, tox, 300.0, 'Valorant', 'en', port)
ti_ = [{'t': 300.0, 'e': 301.5, 'k': 'say', 'v': 'okay we need this round'}, {'t': 304.0, 'k': 'on screen (chat)', 'v': 'xToxicGuy: jele is the worst player ever uninstall', 'box': [0.02, 0.79, 0.43, 0.03], 'region': 'chat'},
       {'t': 310.0, 'k': 'game sound', 'v': '2 gunshots'}, {'t': 318.0, 'e': 319.0, 'k': 'say', 'v': 'wait what did he say'}, {'t': 319.2, 'e': 321.5, 'k': 'say', 'v': 'he said jele is the worst player ever uninstall'},
       {'t': 322.0, 'k': 'you', 'v': 'screaming'}, {'t': 323.0, 'e': 325.0, 'k': 'say', 'v': 'WHAT bro I have 30 kills'}, {'t': 326.0, 'k': 'chat', 'v': '25 messages'}, {'t': 329.0, 'e': 330.0, 'k': 'say', 'v': 'okay okay focus'}]
bt = c.brief_merge(bt_raw, c.brief_rules({'t': 322}, ti_, 300.0, 322.0), ti_)
print('RAWBRIEF', repr(c.LLM.get('last_brief'))[:400]); print('TOXIC raw', bt_raw, '| merged', {k: bt.get(k) for k in ('start', 'cause', 'payoff', 'end')}, 'focus' if bt.get('focus') else 'no focus')
cases = ['could you trim it so it is a bit snappier, like 4 seconds', 'take the zoom out', 'zet de muziek uit', 'make the captions purple', 'begin 2 seconden later']
for q in cases: print('CMD', repr(q), '->', c.cmd_parse(q))
odd = c.cmd_parse('the ending feels a bit flat and the song is way too loud')
print('CMD (model)', odd)
c.llm_stop()
ok = bool(bt.get('focus')) and bt['start'] <= 302 and bt['cause'] <= 304.5 and (not bm or int(bm.get('score') or 10) <= 4) and (not jm or jm['score'] <= (3 if c.SET['llm_size'] == 'smart' else 5)) and (bool(raw_br) or c.SET['llm_size'] != 'smart') and br['start'] <= 109 and 112 <= br['payoff'] <= 116 and 117 <= br['end'] <= 125 and len(ti) >= 1 and all(c.cmd_parse(q) for q in cases) and jg and jb and jg['score'] > jb['score']
print('LLM CI', 'GOOD' if ok else 'BAD'); sys.exit(0 if ok else 1)
