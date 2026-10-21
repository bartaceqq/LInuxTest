#!/usr/bin/env python3
"""Publikace nové baseline pro příští reset; běžící hlavní VM se nemění.

Použití (root):
  python3 linux-exam-publish.py publish --qa-report /opt/linux-exam-simulator/reports/qa/publish-ready.json
  python3 linux-exam-publish.py --cleanup-qa

Report musí mít passed=true, instance="qa", uuid, root_baseline (název),
root_sha256 a state={status:"not_started",score:0,start:null,deadline:null,
completed:{}}. Report je důkazem předchozího smoke testu; tento nástroj bez
libguestfs nečte stav uvnitř vypnutého filesystému a nic takového nepředstírá.
"""
import argparse
import contextlib
import fcntl
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

PROJECT=Path('/opt/linux-exam-simulator')
IMAGE_ROOT=Path('/var/lib/libvirt/images/linux-exam-simulator')
DISKS=('root','practice','flash')


def require(condition,message):
    if not condition:raise RuntimeError(message)


def plain_directory(path):
    require(path.is_absolute() and path.resolve(strict=True)==path,
            'Adresář musí být skutečná absolutní cesta bez symlinků: '+str(path))
    require(path.is_dir() and not path.is_symlink(),'Neplatný adresář: '+str(path))
    require(path.stat().st_uid==0,'Adresář nevlastní root: '+str(path))


def regular_file(path,root_owner=False):
    details=path.lstat()
    require(stat.S_ISREG(details.st_mode) and not path.is_symlink(),
            'Očekáván prostý soubor bez symlinku: '+str(path))
    require(path.resolve(strict=True)==path,'Nepřímá cesta k souboru: '+str(path))
    if root_owner:require(details.st_uid==0,'Soubor nevlastní root: '+str(path))
    return details


def config(instance):
    path=PROJECT/'host/config.py';regular_file(path,root_owner=True)
    previous=os.environ.get('LINUX_EXAM_INSTANCE')
    try:
        os.environ['LINUX_EXAM_INSTANCE']=instance
        spec=importlib.util.spec_from_file_location('linux_exam_publish_'+instance,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    finally:
        if previous is None:os.environ.pop('LINUX_EXAM_INSTANCE',None)
        else:os.environ['LINUX_EXAM_INSTANCE']=previous
    expected_disk=IMAGE_ROOT/('qa' if instance=='qa' else '')
    expected_boot=PROJECT/'build'/('qa' if instance=='qa' else '')
    expected_vm='linux-essentials-exam'+('-qa' if instance=='qa' else '')
    require(module.P==PROJECT and module.D==expected_disk and module.BOOT==expected_boot
            and module.VM==expected_vm and tuple(module.DISKS)==DISKS
            and module.MANIFEST==expected_boot/'manifest.json','Neočekávaná konfigurace instance.')
    for directory in (PROJECT,expected_boot,expected_disk):plain_directory(directory)
    return module


def command(args):
    return subprocess.check_output(args,text=True,env=dict(os.environ,LC_ALL='C')).strip()


def virsh(*args):return command(['virsh','-c','qemu:///system',*args])


@contextlib.contextmanager
def locked(directory):
    path=directory/'operations.lock'
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o644)
    try:
        details=os.fstat(fd)
        require(stat.S_ISREG(details.st_mode) and details.st_uid==0 and details.st_nlink==1,
                'Neplatný zámek operací: '+str(path))
        os.fchmod(fd,0o644);fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:os.close(fd)


def manifest(instance):
    regular_file(instance.MANIFEST,root_owner=True)
    data=json.loads(instance.MANIFEST.read_text())
    require(data['name']==instance.VM and data['directory']==str(instance.D)
            and tuple(data['disks'])==DISKS,'Manifest neodpovídá pevně vymezené instanci.')
    uuid.UUID(data['uuid'])
    for name in DISKS:regular_file(instance.baseline(data,name))
    return data


def domain(instance,data,shutoff=False):
    require(virsh('domuuid',instance.VM)==data['uuid'],'Nesouhlasí UUID VM '+instance.VM)
    state=virsh('domstate',instance.VM)
    if shutoff:require(state=='shut off','QA musí být bezpečně vypnuté, bez uloženého běhu.')
    expected={str(instance.D/(name+'.qcow2')) for name in DISKS}|{str(instance.D/'seed.iso')}
    configurations=[ET.fromstring(virsh('dumpxml',instance.VM,'--inactive'))]
    if state!='shut off':configurations.append(ET.fromstring(virsh('dumpxml',instance.VM)))
    for root in configurations:
        require(root.findtext('uuid')==data['uuid'],'UUID XML neodpovídá manifestu.')
        require(root.find('devices/hostdev') is None and root.find('devices/filesystem') is None,
                'VM obsahuje neočekávané sdílení hostitele.')
        disks=root.findall('devices/disk')
        require(len(disks)==4 and all(d.get('type')=='file' for d in disks)
                and {d.find('source').get('file') for d in disks}==expected,
                'VM má neočekávané diskové soubory.')
    # Samostatně uložený běh by mohl po undefine nebo následném startu obnovit
    # jiný diskový stav. Nepovolujeme jeho smazání jako vedlejší efekt.
    if shutoff:
        info=virsh('dominfo',instance.VM)
        for line in info.splitlines():
            if line.startswith('Managed save:'):
                require(line.split(':',1)[1].strip()=='no','QA má uložený běh; publikace odmítnuta.')


def metadata(path):
    result=json.loads(command(['qemu-img','info','--output=json',str(path)]))
    require(result.get('format')=='qcow2' and not result.get('backing-filename')
            and not result.get('full-backing-filename') and not result.get('encrypted')
            and not result.get('snapshots'),'Baseline musí být samostatné QCOW2 bez dalších vazeb.')
    require(result.get('virtual-size',0)>0,'Baseline má neplatnou virtuální velikost.')
    return result


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def fsync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish(main,qa,report_path):
    main_data=manifest(main);qa_data=manifest(qa)
    domain(main,main_data);domain(qa,qa_data,shutoff=True)
    source=qa.baseline(qa_data,'root');details=regular_file(source)
    require(not details.st_mode&0o222,'QA baseline musí být pouze pro čtení.')
    qa_metadata=metadata(source)
    require(qa_metadata['virtual-size']==metadata(main.baseline(main_data,'root'))['virtual-size'],
            'Virtuální velikosti výchozích systémových disků nesouhlasí.')
    require(report_path.is_absolute() and report_path.parent==PROJECT/'reports/qa',
            'Report musí ležet přímo v dedikovaném reports/qa.')
    regular_file(report_path,root_owner=True)
    report=json.loads(report_path.read_text())
    require(report.get('passed') is True and report.get('instance')=='qa'
            and report.get('uuid')==qa_data['uuid'] and report.get('root_baseline')==source.name,
            'Smoke report neodpovídá testované QA baseline.')
    state=report.get('state',{})
    require(state.get('status')=='not_started' and state.get('score')==0
            and state.get('completed')=={} and state.get('start') is None
            and state.get('deadline') is None,'Report nedokládá čistý, nezahájený pokus.')
    source_hash=sha256(source)
    require(report.get('root_sha256')==source_hash,'Hash QA baseline neodpovídá smoke reportu.')
    subprocess.run(['qemu-img','check','-q','-f','qcow2',str(source)],check=True)
    original_manifest=main.MANIFEST.read_bytes()
    filename='root.baseline-ui3-'+str(time.time_ns())+'.qcow2'
    final=main.D/filename
    fd,temporary=tempfile.mkstemp(prefix='.'+filename+'.',suffix='.tmp',dir=main.D)
    os.close(fd);temporary=Path(temporary)
    try:
        subprocess.run(['qemu-img','convert','-f','qcow2','-O','qcow2',str(source),str(temporary)],check=True)
        metadata(temporary)
        subprocess.run(['qemu-img','check','-q','-f','qcow2',str(temporary)],check=True)
        require(sha256(source)==source_hash,'QA baseline se během publikace změnila.')
        domain(main,main_data);domain(qa,qa_data,shutoff=True)
        require(main.MANIFEST.read_bytes()==original_manifest,'Manifest byl souběžně změněn.')
        with temporary.open('rb') as stream:
            os.fchown(stream.fileno(),0,grp.getgrnam('kvm').gr_gid)
            os.fchmod(stream.fileno(),0o440);os.fsync(stream.fileno())
        # link odmítne již existující název. Žádná stará baseline se nepřepisuje.
        os.link(temporary,final);temporary.unlink();fsync_directory(main.D)
        updated=dict(main_data);updated['baselines']=dict(main_data.get('baselines',{}))
        updated['baselines']['root']=filename
        fd,manifest_temporary=tempfile.mkstemp(prefix='.manifest-publish-',dir=main.BOOT)
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(updated,stream,ensure_ascii=False,indent=2);stream.write('\n')
                stream.flush();os.fchmod(stream.fileno(),0o644);os.fsync(stream.fileno())
            os.replace(manifest_temporary,main.MANIFEST);fsync_directory(main.BOOT)
        finally:
            if os.path.exists(manifest_temporary):os.unlink(manifest_temporary)
        print('Publikována nová výchozí kopie pro příští potvrzený reset: '+str(final))
        print('Běžící hlavní VM, jeho aktivní disky i všechny staré baseline zůstaly zachovány.')
    finally:
        # Maže se výhradně náš náhodný pracovní soubor, nikdy stará baseline.
        if temporary.exists():temporary.unlink()


def inside(path,directory):
    try:path.relative_to(directory);return True
    except ValueError:return False


def unreferenced_qa(main,main_data,qa):
    for name in DISKS:
        paths=[main.D/(name+'.qcow2'),main.baseline(main_data,name)]
        for path in paths:
            chain=json.loads(command(['qemu-img','info','--force-share','--backing-chain','--output=json',str(path)]))
            for image in chain:
                for key in ('filename','backing-filename','full-backing-filename'):
                    filename=image.get(key)
                    if not filename:continue
                    candidate=Path(filename)
                    if not candidate.is_absolute():candidate=Path(image['filename']).parent/candidate
                    require(not inside(candidate.resolve(),qa.D),'Hlavní disk odkazuje na QA soubor.')
    for name in virsh('list','--all','--name').splitlines():
        if not name or name==qa.VM:continue
        for flag in (('--inactive',),()):
            root=ET.fromstring(virsh('dumpxml',name,*flag))
            for source in root.findall('.//source'):
                for key in ('file','dir'):
                    filename=source.get(key)
                    if filename:
                        require(not inside(Path(filename).resolve(),qa.D),
                                'Jiný VM odkazuje na QA adresář: '+name)


def safe_removal_tree(directory):
    plain_directory(directory)
    # Zahrnuje i bind mounty na stejném filesystému.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        field=line.split()[4]
        for escaped,value in (('\\040',' '),('\\011','\t'),('\\012','\n'),('\\134','\\')):
            field=field.replace(escaped,value)
        require(not inside(Path(field),directory),'QA strom obsahuje přípojný bod.')
    for root,dirs,files in os.walk(directory,followlinks=False):
        for name in dirs+files:
            path=Path(root)/name;details=path.lstat()
            require(stat.S_ISREG(details.st_mode) or stat.S_ISDIR(details.st_mode),
                    'QA strom obsahuje symlink nebo zvláštní soubor: '+str(path))


def cleanup(main,qa):
    main_data=manifest(main);qa_data=manifest(qa)
    domain(main,main_data);domain(qa,qa_data,shutoff=True)
    unreferenced_qa(main,main_data,qa)
    require(qa.D==IMAGE_ROOT/'qa' and qa.BOOT==PROJECT/'build/qa','Neplatná cesta úklidu QA.')
    safe_removal_tree(qa.D);safe_removal_tree(qa.BOOT)
    # Undefine bez --remove-all-storage/--nvram/--managed-save: libvirt nesmí
    # odstranit žádné další prostředky. Při chybě se adresáře nemažou.
    subprocess.run(['virsh','-c','qemu:///system','undefine',qa.VM],check=True)
    shutil.rmtree(qa.D);shutil.rmtree(qa.BOOT)
    fsync_directory(main.D);fsync_directory(main.BOOT)
    print('Odstraněn pouze vypnutý QA VM a jeho dedikované diskové/build adresáře.')
    print('Reporty QA, hlavní VM a všechny hlavní baseline zůstaly zachovány.')


def main():
    parser=argparse.ArgumentParser(description='Bezpečná publikace verzované výchozí kopie Linux Essentials.')
    parser.add_argument('action',nargs='?',default='publish',choices=('publish','cleanup-qa'))
    parser.add_argument('--cleanup-qa',action='store_true',help='Pouze úklid vypnuté oddělené QA instance.')
    parser.add_argument('--qa-report',type=Path,default=PROJECT/'reports/qa/publish-ready.json')
    args=parser.parse_args()
    require(os.geteuid()==0,'Nástroj vyžaduje roota.')
    primary=config('main');qa=config('qa')
    with locked(primary.BOOT),locked(qa.BOOT):
        if args.cleanup_qa or args.action=='cleanup-qa':cleanup(primary,qa)
        else:publish(primary,qa,args.qa_report)


if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,ValueError,KeyError,subprocess.CalledProcessError) as error:
        print('Odmítnuto / chyba: '+str(error),file=sys.stderr);sys.exit(1)
