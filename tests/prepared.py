#!/usr/bin/env python3
"""Čistý QA smoke report svázaný s konkrétní neměnnou baseline pro publikaci."""
import base64,hashlib,json,os,subprocess,sys,time
from pathlib import Path
P=Path('/opt/linux-exam-simulator');sys.path.insert(0,str(P/'host'))
import guest
from config import MANIFEST,D,REPORTS,baseline
assert guest.VM=='linux-essentials-exam-qa' and os.geteuid()==0,'Pouze sudo env LINUX_EXAM_INSTANCE=qa python3 tests/prepared.py.'
def cmd(command):
 c,o,e=guest.execute(command);assert c==0,(o,e);return o
guest.wait(120)
for _ in range(60):
 if guest.execute('test -f /run/linux-exam/processes.json')[0]==0:break
 time.sleep(.5)
else:raise AssertionError('Výchozí procesy nejsou připravené.')
for name in ('integration','ui-regression'):
 assert json.loads((REPORTS/(name+'.json')).read_text())['passed'],name
assert all(json.loads((REPORTS/'disks.json').read_text())[key] for key in ('practice_disk_reset','flash_disk_reset','no_awards_before_start','baselines_unchanged'))
data=base64.b64encode((P/'tests/initial.py').read_bytes()).decode()
print(cmd("printf '%s' '"+data+"' | base64 -d | python3"))
s=json.loads(cmd('cat /var/lib/linux-exam/state.json'))
files={str(p.relative_to(P/'guest')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (P/'guest').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
actual=json.loads(cmd("python3 - <<'HASH'\nimport hashlib,json\nfrom pathlib import Path\np=Path('/opt/linux-exam');print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts}))\nHASH"))
assert all(actual.get(name)==digest for name,digest in files.items()),'Guest neobsahuje aktuální zdrojové soubory.'
m=json.loads(MANIFEST.read_text());root=baseline(m,'root')
chain=json.loads(subprocess.check_output(['qemu-img','info','--force-share','--output=json',str(D/'root.qcow2')],text=True))
assert chain['full-backing-filename']==str(root),'Aktivní QA není overlay ověřované baseline.'
root_hash=hashlib.sha256()
with root.open('rb') as stream:
 for block in iter(lambda:stream.read(4*1024*1024),b''):root_hash.update(block)
report=dict(passed=True,instance='qa',uuid=m['uuid'],root_baseline=root.name,root_sha256=root_hash.hexdigest(),state=s,source_sha256=files,checked_at=time.time())
path=REPORTS/'publish-ready.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2));path.chmod(0o644)
print('PASS: čistá připravená baseline, aktuální zdrojové soubory a vazba SHA-256. Report:',path)
