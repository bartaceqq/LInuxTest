#!/usr/bin/env python3
"""Čtecí snímek hostitele. Obsah databází účtů se ukládá pouze jako SHA-256."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET

PROJECT=Path('/opt/linux-exam-simulator')
IMAGE_ROOT=Path('/var/lib/libvirt/images/linux-exam-simulator')
VIRSH=('virsh','-c','qemu:///system')


def probe(*args,json_output=False):
    try:
        process=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               timeout=30,env=dict(os.environ,LC_ALL='C'))
    except (FileNotFoundError,subprocess.TimeoutExpired) as error:
        return {'ok':False,'error':str(error)}
    if process.returncode:
        return {'ok':False,'error':process.stderr.strip() or f'Návratový kód {process.returncode}'}
    value=process.stdout.strip()
    return {'ok':True,'value':json.loads(value) if json_output else value}


def command_fingerprint(name):
    path=shutil.which(name)
    if path is None:return {'exists':False}
    source=Path(path).absolute();target=source.resolve(strict=True)
    return {'exists':True,'path':str(source),'target':str(target),
            'symlink':os.readlink(source) if source.is_symlink() else None,
            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


def account_snapshot(path):
    content=Path(path).read_bytes();entries={};groups={}
    for line in content.splitlines():
        fields=line.decode().split(':');name=fields[0]
        entries[name]=hashlib.sha256(line).hexdigest()
        if path in ('/etc/group','/etc/gshadow') and len(fields)==4:
            prefix=fields[:3] if path=='/etc/group' else fields[:2]
            groups[name]={'identity_sha256':hashlib.sha256(':'.join(prefix).encode()).hexdigest(),
                          'members':sorted(filter(None,fields[3].split(','))),
                          'admins':sorted(filter(None,fields[2].split(','))) if path=='/etc/gshadow' else []}
    return {'sha256':hashlib.sha256(content).hexdigest(),'entries':entries,'groups':groups}


def owned_domain(name,root):
    """Samotné očekávané jméno VM nikdy není důkazem vlastnictví projektu."""
    if name=='linux-essentials-exam':boot=PROJECT/'build';directory=IMAGE_ROOT
    elif name=='linux-essentials-exam-qa':boot=PROJECT/'build/qa';directory=IMAGE_ROOT/'qa'
    else:return False
    try:
        manifest_path=boot/'manifest.json'
        if manifest_path.is_symlink():return False
        manifest=json.loads(manifest_path.read_text())
        uuid.UUID(manifest['uuid'])
        expected={str(directory/(disk+'.qcow2')) for disk in ('root','practice','flash')}|{str(directory/'seed.iso')}
        disks=root.findall('devices/disk')
        return (manifest.get('name')==name and manifest.get('directory')==str(directory)
                and manifest.get('disks')==['root','practice','flash']
                and manifest.get('uuid')==root.findtext('uuid')
                and root.findtext('name')==name and len(disks)==4
                and all(d.get('type')=='file' for d in disks)
                and {d.find('source').get('file') for d in disks}==expected
                and root.find('devices/hostdev') is None and root.find('devices/filesystem') is None)
    except (OSError,ValueError,KeyError,AttributeError,TypeError):return False


def domains():
    listed=probe(*VIRSH,'list','--all','--name')
    if not listed['ok']:return listed,[]
    result={};excluded=[]
    for name in sorted(filter(None,listed['value'].splitlines())):
        config=probe(*VIRSH,'dumpxml',name,'--inactive')
        if not config['ok']:config=probe(*VIRSH,'dumpxml',name)
        state=probe(*VIRSH,'domstate',name)
        if not config['ok'] or not state['ok']:
            return {'ok':False,'error':'Nelze přečíst konfiguraci/stav VM '+name},excluded
        root=ET.fromstring(config['value'])
        owned=owned_domain(name,root)
        if owned and state['value']!='shut off':
            live=probe(*VIRSH,'dumpxml',name)
            owned=live['ok'] and owned_domain(name,ET.fromstring(live['value']))
        if owned:
            excluded.append({'name':name,'uuid':root.findtext('uuid')});continue
        result[name]={'xml':config['value'],'state':state['value']}
    return {'ok':True,'value':result},excluded


def networks():
    listed=probe(*VIRSH,'net-list','--all','--name')
    if not listed['ok']:return listed
    result={}
    for name in sorted(filter(None,listed['value'].splitlines())):
        config=probe(*VIRSH,'net-dumpxml',name);info=probe(*VIRSH,'net-info',name)
        if not config['ok'] or not info['ok']:
            return {'ok':False,'error':'Nelze přečíst síť libvirt '+name}
        fields={line.split(':',1)[0]:line.split(':',1)[1].strip()
                for line in info['value'].splitlines() if ':' in line}
        result[name]={'xml':config['value'],'active':fields.get('Active'),
                      'autostart':fields.get('Autostart'),'persistent':fields.get('Persistent')}
    return {'ok':True,'value':result}


def capture():
    vms,excluded=domains()
    services=probe('systemctl','list-units','--type=service','--state=running','--no-legend','--plain')
    if services['ok']:services['value']=sorted(line.split()[0] for line in services['value'].splitlines() if line.strip())
    return {'schema_version':2,
            'accounts':{path:account_snapshot(path)
                        for path in ('/etc/passwd','/etc/shadow','/etc/group','/etc/gshadow')},
            'virt_command':command_fingerprint('virt'),
            'routes':probe('ip','-j','route',json_output=True),
            'addresses':probe('ip','-j','addr',json_output=True),
            'mounts':probe('findmnt','-J','-o','SOURCE,TARGET,FSTYPE',json_output=True),
            'vms':vms,'excluded_owned_vms':excluded,'services':services,'networks':networks()}


if __name__=='__main__':
    if os.geteuid()!=0:raise SystemExit('Snímek hostitele vyžaduje sudo kvůli hashům databází účtů.')
    print(json.dumps(capture(),ensure_ascii=False,indent=2))
