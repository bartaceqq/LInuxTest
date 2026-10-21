#!/usr/bin/env python3
"""Pouze potvrzený reset tří diskových souborů vlastní instance."""
import json,os,sys,subprocess,time,xml.etree.ElementTree as ET,fcntl
from config import P,D,VM,BOOT,MANIFEST,DISKS,baseline

def virsh(*args):
    return subprocess.check_output(['virsh','-c','qemu:///system',*args],stdin=subprocess.DEVNULL,text=True).strip()
def require(condition,message):
    if not condition:raise RuntimeError(message)
def validate(require_baseline=True):
    m=json.loads(MANIFEST.read_text())
    require(m['directory']==str(D) and m['name']==VM and tuple(m['disks'])==DISKS,'Neplatný manifest cvičného VM.')
    expected={str(D/(n+'.qcow2')) for n in DISKS}|{str(D/'seed.iso')}
    configurations=[ET.fromstring(virsh('dumpxml',VM,'--inactive'))]
    if virsh('domstate',VM)!='shut off':configurations.append(ET.fromstring(virsh('dumpxml',VM)))
    for root in configurations:
        require(root.findtext('uuid')==m['uuid'],'Nesouhlasí UUID cvičného VM.')
        require(root.find('devices/hostdev') is None and root.find('devices/filesystem') is None,'Neočekávané sdílení hostitele.')
        disks=root.findall('devices/disk')
        require(len(disks)==4 and all(x.get('type')=='file' for x in disks),'Neočekávaný typ disku.')
        require({x.find('source').get('file') for x in disks}==expected,'Připojené disky se liší od vyhrazených souborů.')
    for name in DISKS:
        active=D/(name+'.qcow2');base=baseline(m,name)
        require(active.is_file() and not active.is_symlink(),'Neplatný aktivní virtuální disk.')
        require(not require_baseline or base.is_file() and not base.is_symlink(),'Chybí bezpečná výchozí kopie.')
    return m

def stop(timeout=45,force=False):
    if virsh('domstate',VM)=='shut off':return
    subprocess.run(['virsh','-c','qemu:///system','shutdown',VM],check=True)
    end=time.monotonic()+timeout
    while virsh('domstate',VM)!='shut off' and time.monotonic()<end:time.sleep(.5)
    if virsh('domstate',VM)!='shut off':
        if not force:raise RuntimeError('VM se zatím nevypnul; jeho disky se nemění.')
        print('Po potvrzeném resetu ukončuji nereagující cvičný VM.')
        subprocess.run(['virsh','-c','qemu:///system','destroy',VM],check=True)

def reset():
    with open(BOOT/'operations.lock','a') as lock:
        os.chmod(BOOT/'operations.lock',0o644);fcntl.flock(lock,fcntl.LOCK_EX)
        m=validate()
        for name in DISKS:
            subprocess.run(['qemu-img','info','--output=json',str(baseline(m,name))],check=True,stdout=subprocess.DEVNULL)
        stop(force=True)
        marker=BOOT/'reset-in-progress';marker.touch()
        uid=__import__('pwd').getpwnam('libvirt-qemu').pw_uid;gid=__import__('grp').getgrnam('kvm').gr_gid
        for name in DISKS:
            tmp=D/(name+'.reset.qcow2')
            if tmp.exists():tmp.unlink()
            subprocess.run(['qemu-img','create','-q','-f','qcow2','-F','qcow2','-b',str(baseline(m,name)),str(tmp)],check=True)
            os.chown(tmp,uid,gid);os.chmod(tmp,0o640)
        for name in DISKS:os.replace(D/(name+'.reset.qcow2'),D/(name+'.qcow2'))
        marker.unlink()
        subprocess.run(['virsh','-c','qemu:///system','start',VM],check=True)
        print('VM obnoven: 0/34. Nových 65 minut začne až příkazem starttest.')
if __name__=='__main__':
    if os.geteuid()!=0:raise SystemExit('Reset disků vyžaduje sudo.')
    if sys.argv[1:]!=['--confirmed']:raise SystemExit('Spusť linux-exam reset; vyžaduje potvrzení.')
    reset()
