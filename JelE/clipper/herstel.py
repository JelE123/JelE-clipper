# JelE Clipper: puts the previous version back.
# start.bat runs this by itself when the clipper does not start properly after an update.
# You can also run it yourself: double-click herstel.bat
import os, sys, json, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, 'data')
PENDING = os.path.join(DATA, 'update_pending.json')
DONE = os.path.join(DATA, 'hersteld.json')
VERS = os.path.join(DATA, 'versies')


def restore(backup, root=ROOT):
    """put every file from the backup zip back, and remove files the update added"""
    n = 0
    with zipfile.ZipFile(backup) as z:
        added = []
        if '_added.json' in z.namelist():
            try: added = json.loads(z.read('_added.json').decode('utf-8'))
            except Exception: added = []
        for m in z.infolist():
            if m.is_dir() or m.filename in ('_added.json', '_info.json') or '..' in m.filename: continue
            dst = os.path.join(root, m.filename.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as fh: fh.write(z.read(m))
            n += 1
    for rel in added:
        if '..' in rel or os.path.basename(rel).lower() == 'config.js': continue
        p = os.path.join(root, rel.replace('/', os.sep))
        try: os.remove(p)
        except OSError: pass
    return n


def newest_backup():
    try: fs = [os.path.join(VERS, f) for f in os.listdir(VERS) if f.endswith('.zip')]
    except OSError: return None
    return max(fs, key=os.path.getmtime) if fs else None


def main():
    info = {}
    try: info = json.load(open(PENDING, encoding='utf-8'))
    except Exception: pass
    backup = info.get('backup') or newest_backup()
    if not backup or not os.path.exists(backup):
        print(' No previous version found to put back.')
        return 1
    n = restore(backup)
    try: os.remove(PENDING)
    except OSError: pass
    json.dump({'from': info.get('to'), 'to': info.get('from'), 'at': time.time(), 'files': n}, open(DONE, 'w', encoding='utf-8'))
    print(f' Previous version restored ({n} files).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
