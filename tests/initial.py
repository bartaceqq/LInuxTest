#!/usr/bin/env python3
"""Spouštět uvnitř cvičného VM jako root."""
import sys,os,json,pwd,grp,subprocess
from pathlib import Path
sys.path.insert(0,'/opt/linux-exam');import tasks,state
assert 'VERSION_ID="22.04"' in Path('/etc/os-release').read_text()
assert os.uname().nodename=='linux-exam'
for n in ('student','lubos','jan','pepa','karel','jouda','webapp','webapp2','nobody'):pwd.getpwnam(n)
assert tasks.user('aneta') is None and tasks.group('spravci') is None
assert tasks.package('curl') and not tasks.package('mc')
assert not tasks.terminated('nginx') and not tasks.terminated('apache')
processes=json.loads(Path('/run/linux-exam/processes.json').read_text())
assert os.path.realpath(f"/proc/{processes['nginx']['pid']}/exe")=='/usr/sbin/nginx'
assert Path('/dev/sda1').is_block_device()
assert tasks.run(['ip','link','show','eth1'])[0]==0
assert tasks.run(['mountpoint','-q','/mnt/flashka'])[0]==0
for p in ['/var/www/html/index.nginx-debian.html','/var/log/nginx/access.log','/home/jan/hesla.doc','/home/karel/zaloha/dokumenty/zprava.txt','/opt/nyancat/src/nyancat.c','/home/student/test.sh','/home/student/zadani.txt','/usr/local/bin/starttest','/usr/local/bin/statstest','/usr/local/bin/zadanitest','/usr/local/bin/pomoc-test','/usr/local/bin/vysledektest']:assert Path(p).is_file(),p
assert os.access('/usr/local/bin/starttest',os.X_OK) and os.access('/usr/local/bin/statstest',os.X_OK)
s=state.read();assert s['score']==0 and s['status']=='not_started' and s['start'] is None and s['deadline'] is None
assert not Path('/var/lib/linux-exam/started').exists()
assert subprocess.run(['systemctl','is-active','--quiet','linux-exam-grader']).returncode!=0
bad=[]
for key,_,_ in tasks.TASKS:
    try:
        if tasks.validate(key):bad.append(key)
    except FileNotFoundError:pass
assert not bad,f'Předem splněné úkoly: {bad}'
print('A: PASS — Ubuntu 22.04, všechny výchozí podmínky, 0/34, 26 nesplněných kontrol.')
