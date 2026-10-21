"""Atomický a zamčený stav zkoušky; čas je absolutní UTC Unix timestamp."""
import json,os,time,fcntl,contextlib,tempfile
from pathlib import Path
ROOT=Path('/var/lib/linux-exam');STATE=ROOT/'state.json';DURATION=65*60

def empty():return dict(start=None,deadline=None,completed={},score=0,status='not_started',events=[])
def read():
    try:return json.loads(STATE.read_text())
    except FileNotFoundError:return empty()
def write(s):
    ROOT.mkdir(mode=0o755,parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.state-',dir=ROOT)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(s,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o644)
        os.replace(name,STATE)
        d=os.open(ROOT,os.O_DIRECTORY);os.fsync(d);os.close(d)
    finally:
        if os.path.exists(name):os.unlink(name)
@contextlib.contextmanager
def locked():
    ROOT.mkdir(mode=0o755,parents=True,exist_ok=True)
    with open(ROOT/'state.lock','a') as f:
        os.chmod(ROOT/'state.lock',0o600);fcntl.flock(f,fcntl.LOCK_EX)
        yield

def event(s,text):s['events'].append(dict(time=time.time(),text=text))
def start():
    with locked():
        s=read()
        if s['status']=='not_started':
            now=time.time();s.update(start=now,deadline=now+DURATION,status='running')
            event(s,'[SYSTEM] Zkouška zahájena. Máte přesně 65 minut.');write(s)
        return s
