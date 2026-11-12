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
VERSION = '6.20'

# the app lives in clipper/app/, split by topic. every part runs in this one namespace (same as one big file),
# so a part can use everything from the parts before it. the order matters.
PARTS = ('core', 'helpers', 'sessions', 'game', 'moments', 'speech', 'captions', 'render',
         'library', 'setup', 'jobs', 'extras', 'upkeep', 'server')
def _load_parts():
    for p in PARTS:
        f = os.path.join(HERE, 'app', p + '.py')
        with open(f, encoding='utf-8') as fh: code = compile(fh.read(), f, 'exec')
        exec(code, globals())
_load_parts()

if __name__ == '__main__':
    main()
