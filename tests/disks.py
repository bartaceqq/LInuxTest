#!/usr/bin/env python3
"""Zápis a reset dat na obou virtuálních pomocných discích; nikdy na hostu."""
import os,sys,pathlib,json,time,subprocess,hashlib
P=pathlib.Path('/opt/linux-exam-simulator');sys.path.insert(0,str(P/'host'));import guest
from config import REPORTS,D,MANIFEST,baseline as baseline_path
assert guest.VM=='linux-essentials-exam-qa','Testy běží pouze v oddělené QA VM.'
assert os.geteuid()==0,'Kontrola chráněných baseline vyžaduje sudo env LINUX_EXAM_INSTANCE=qa python3 tests/disks.py.'

def cmd(s):
 c,o,e=guest.execute(s);assert c==0,(s,o,e);return o

def baseline_hashes():
 return {p.name:subprocess.check_output(['sha256sum',str(p)],text=True).split()[0] for p in [baseline_path(json.loads(MANIFEST.read_text()),name) for name in ('root','practice','flash')]}
def reset():
 p=subprocess.run(['linux-exam','reset'],input='RESET\n',capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
 guest.wait(120)
 for _ in range(30):
  if guest.execute('test -f /run/linux-exam/processes.json')[0]==0:return
  time.sleep(.5)
 raise RuntimeError('Procesy se po resetu nespustily')
s=json.loads(cmd('cat /var/lib/linux-exam/state.json'));assert s['status']=='not_started' and s['score']==0,'Test vyžaduje čistý VM.'
start=baseline_hashes()
cmd('''test "$(hostname)" = linux-exam
mkdir -p /run/exam-disk-check
mount /dev/sda1 /run/exam-disk-check
printf 'data k odstranění resetem\n' > /run/exam-disk-check/reset-test.txt
printf 'data k odstranění resetem\n' > /mnt/flashka/reset-test.txt
umount /run/exam-disk-check
chown nobody:nogroup /var/tajny
''')
time.sleep(2)
s=json.loads(cmd('cat /var/lib/linux-exam/state.json'));assert s['status']=='not_started' and s['score']==0
reset()
cmd('''test ! -e /mnt/flashka/reset-test.txt
mkdir -p /run/exam-disk-check
mount -o ro /dev/sda1 /run/exam-disk-check
test ! -e /run/exam-disk-check/reset-test.txt
umount /run/exam-disk-check
''')
assert start==baseline_hashes(),'Změnil se obsah výchozích obrazů'
reset()
report={'practice_disk_reset':True,'flash_disk_reset':True,'no_awards_before_start':True,'baselines_unchanged':True,'baseline_sha256':start}
(REPORTS/'disks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('PASS: reset odstranil zápisy z obou pomocných disků, výchozí obrazy jsou beze změn.')
print('PASS: ani správně změněné vlastnictví nepřidělilo body před zahájením zkoušky.')
