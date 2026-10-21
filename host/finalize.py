#!/usr/bin/env python3
"""Nová neměnná verze připravených disků. Žádný starý backing se nepřepisuje."""
import os,json,time,fcntl,subprocess,sys,grp
from config import D,BOOT,MANIFEST,DISKS
import guest
from reset import validate,stop,reset
if os.geteuid()!=0:raise SystemExit('Příprava obrazů vyžaduje sudo.')
with open(BOOT/'operations.lock','a') as lock:
    os.chmod(BOOT/'operations.lock',0o644);fcntl.flock(lock,fcntl.LOCK_EX)
    m=validate(require_baseline=False)
    guest.wait()
    c,o,e=guest.execute('test -f /var/lib/linux-exam/provisioned && test ! -f /var/lib/linux-exam/started && python3 -c "import json; s=json.load(open(\'/var/lib/linux-exam/state.json\')); assert s[\'score\']==0 and s[\'status\']==\'not_started\'"')
    if c:raise SystemExit('Výchozí obraz lze vytvořit jen z čisté nezačaté zkoušky. Současný pokus se nemění.')
    stop(timeout=120)
    version=str(time.time_ns());versions={}
    for name in DISKS:
        path=D/(name+'.baseline-'+version+'.qcow2')
        subprocess.run(['qemu-img','convert','-O','qcow2',str(D/(name+'.qcow2')),str(path)],check=True)
        os.chown(path,0,grp.getgrnam('kvm').gr_gid);os.chmod(path,0o440);versions[name]=path.name
    m['baselines']=versions
    temp=MANIFEST.with_suffix('.new')
    with open(temp,'w') as f:json.dump(m,f,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(temp,MANIFEST);(BOOT/'baseline-ready').touch()
reset()
