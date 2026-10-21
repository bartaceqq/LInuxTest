#!/usr/bin/env python3
"""Instalace ze zdrojového stromu. Existující stroje ani pokusy se neaktualizují."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

SOURCE=Path(__file__).resolve().parents[1]
TARGET=Path('/opt/linux-exam-simulator')
DISKS=Path('/var/lib/libvirt/images/linux-exam-simulator')
COMMAND=Path('/usr/local/bin/linux-exam')
VM='linux-essentials-exam'
PACKAGES=('qemu-system-x86','qemu-utils','libvirt-daemon-system','libvirt-clients',
          'cloud-image-utils','python3','python3-yaml','ca-certificates','curl',
          'git','gpgv','libslirp0','iproute2')
COPY=('guest','host','tests','keys','docs','.github','install.sh','README.md','LICENSE','.gitignore')
NYANCAT='32fd2eb40332ae0001995705f0c1f8de69a2d543'


def run(args,check=True,capture=False,cwd=None):
    return subprocess.run([str(a) for a in args],check=check,cwd=cwd,
                          stdin=subprocess.DEVNULL,stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None,text=True,
                          env=dict(os.environ,LC_ALL='C',DEBIAN_FRONTEND='noninteractive',
                                   NEEDRESTART_MODE='l'))


def require(condition,message):
    if not condition:raise RuntimeError(message)


def clean_path(path):
    """Žádná existující část vyhrazené cesty nesmí být symlink."""
    require(path.is_absolute(),'Cesta musí být absolutní.')
    for part in (path,*path.parents):
        require(not part.is_symlink(),'Odmítám symlink v cílové cestě: '+str(part))


def occupied(path):return path.exists() or path.is_symlink()


def collision_check(target=TARGET,disks=DISKS,command=COMMAND,which=None):
    for p in (target,disks,command.parent):clean_path(p)
    if occupied(command):
        require(command.is_symlink() and command.resolve()==target/'host/linux-exam',
                'Příkaz linux-exam už patří jinému projektu; nic nepřepisuji.')
    if which:
        require(Path(which)==command or Path(which).resolve()==target/'host/linux-exam',
                'V PATH již existuje jiný linux-exam: '+str(which))
    ready=target/'build/baseline-ready'
    if ready.exists():
        require((target/'build/manifest.json').is_file() and (target/'host/reset.py').is_file(),
                'Výchozí obraz nemá platný projektový manifest.')
        return True
    require(not occupied(target),'Cílový adresář již existuje. Nepřepisuji rozpracovanou ani neznámou instalaci: '+str(target))
    require(not occupied(disks) or disks.is_dir() and not any(disks.iterdir()),
            'Adresář disků není prázdný; nic nemažu ani nepřepisuji: '+str(disks))
    require(not occupied(command),'Zůstal zde starý příkaz linux-exam bez hotové instalace.')
    return False


def choose_resources(total,available,cpus):
    require(total>=3000 and available>=2200,'Málo paměti: doporučeno alespoň 4 GiB RAM a 2,2 GiB právě volné paměti.')
    return dict(memory_mib=2048 if available>=3000 else 1536,vcpus=min(2,max(1,cpus)))


def packages_missing():
    return [p for p in PACKAGES if run(['dpkg-query','-W','-f=${Status}',p],False,True).stdout.strip()!='install ok installed']


def domain_names():
    if not shutil.which('virsh'):return []
    result=run(['virsh','-c','qemu:///system','list','--all','--name'],False,True)
    return result.stdout.split() if result.returncode==0 else []


def source_check(source=SOURCE):
    for name in ('guest/provision.sh','host/build.py','host/bootstrap.sh','tests/initial.py',
                 'keys/ubuntu-cloudimage-keyring.gpg'):
        require((source/name).is_file(),'Neúplný zdrojový projekt: '+name)
    for name in COPY:
        base=source/name
        if not base.exists():continue
        for p in ([base]+list(base.rglob('*')) if base.is_dir() else [base]):
            require(not p.is_symlink(),'Zdroj nesmí obsahovat symlinky: '+str(p))


def storage_check(target=TARGET,disks=DISKS):
    def existing_parent(path):
        while not path.exists():path=path.parent
        return path
    project_parent=existing_parent(target.parent);disk_parent=existing_parent(disks.parent)
    if project_parent.stat().st_dev==disk_parent.stat().st_dev:
        require(shutil.disk_usage(project_parent).free>=12*1024**3,
                'Vyžadováno nejméně 12 GiB volného místa (doporučeno 25 GiB).')
    else:
        require(shutil.disk_usage(project_parent).free>=2*1024**3,
                'Projekt a stažený obraz potřebují alespoň 2 GiB na filesystému /opt.')
        require(shutil.disk_usage(disk_parent).free>=10*1024**3,
                'Virtuální disky potřebují alespoň 10 GiB na filesystému /var/lib/libvirt/images.')


def preflight():
    require(sys.platform=='linux' and os.uname().machine=='x86_64','Podporován je Linux x86_64, nikoli ARM nebo Windows.')
    require(Path('/run/systemd/system').is_dir(),'Hostitel musí používat spuštěný systemd; kontejner se nepoužívá.')
    require(Path('/dev/kvm').is_char_device(),'Chybí /dev/kvm. Zapni virtualizaci v BIOS/UEFI; ve VM je nutné nested KVM.')
    if os.geteuid()==0:require(os.access('/dev/kvm',os.R_OK|os.W_OK),'Root nemá přístup k /dev/kvm.')
    require(shutil.which('apt-get') and shutil.which('dpkg-query'),'Vyžadován Debian/Ubuntu s APT.')
    release={}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            k,v=line.split('=',1);release[k]=v.strip('"')
    require(any(x in ('debian','ubuntu') for x in (release.get('ID','')+' '+release.get('ID_LIKE','')).split()),
            'Distribuce není označená jako Debian/Ubuntu ani kompatibilní derivát.')
    version=release.get('VERSION_ID','0').split('.')[0]
    if release.get('ID')=='debian':require(version.isdigit() and int(version)>=12,'Vyžadován Debian 12 nebo novější.')
    if release.get('ID')=='ubuntu':require(version.isdigit() and int(version)>=22,'Vyžadováno Ubuntu 22.04 nebo novější.')
    source_check()
    already=collision_check(which=shutil.which('linux-exam'))
    if already:
        require(TARGET.stat().st_uid==0 and all(p.stat().st_uid==0 and not p.is_symlink() for p in (TARGET/'host').glob('*.py')),
                'Existující instalace musí mít rootem vlastněné řídicí soubory.')
        if os.geteuid()==0:
            run(['python3','-c',"import sys;sys.path.insert(0,'/opt/linux-exam-simulator/host');from reset import validate;validate()"])
        return dict(already=True,release=release)
    require(VM not in domain_names(),'Jméno VM je již obsazeno; instalace jej nepřepíše.')
    mem={k:int(v.split()[0])//1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
    resources=choose_resources(mem['MemTotal'],mem['MemAvailable'],os.cpu_count() or 1)
    storage_check()
    missing=packages_missing()
    if any(x.startswith(('libvirt','qemu')) for x in missing) and shutil.which('virsh'):
        running=run(['virsh','-c','qemu:///system','list','--name'],False,True)
        require(not running.stdout.strip(),'Běží jiné VM a chybí virtualizační balíčky. Nejdřív připrav závislosti v plánované údržbě; instalace služby nerestartuje.')
    return dict(already=False,release=release,resources=resources,missing=missing)


def copy_source(source=SOURCE,target=TARGET):
    target.mkdir(mode=0o755);target.chmod(0o755)
    for name in COPY:
        src=source/name;dst=target/name
        if not src.exists():continue
        if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copyfile(src,dst)
    for p in target.rglob('*'):
        if p.is_dir():p.chmod(0o755)
        elif p.is_file():p.chmod(0o755 if p.suffix=='.sh' or p.name=='linux-exam' else 0o644)
    for name in ('build','downloads','reports'):
        (target/name).mkdir(mode=0o755);(target/name).chmod(0o755)
    (target/'.linux-exam-project').write_text('linux-exam-simulator v1\n')


def start_libvirt():
    if run(['virsh','-c','qemu:///system','uri'],False,True).returncode==0:return
    # Ponechat modulární/monolitickou architekturu distribuce. Nikdy nemigrovat.
    for unit in ('virtqemud.socket','libvirtd.socket','libvirtd.service'):
        if run(['systemctl','cat',unit],False,True).returncode==0:
            run(['systemctl','enable','--now',unit]);break
    require(run(['virsh','-c','qemu:///system','uri'],False,True).returncode==0,
            'Libvirt neodpovídá. Zkontroluj systemctl status libvirtd nebo virtqemud.')


def verify_downloads():
    dest=TARGET/'downloads';base='https://cloud-images.ubuntu.com/jammy/current/'
    for name in ('SHA256SUMS','SHA256SUMS.gpg'):
        run(['curl','--fail','--location','--retry','3','--proto','=https','--tlsv1.2','-o',str(dest/name),base+name])
    run(['gpgv','--keyring',TARGET/'keys/ubuntu-cloudimage-keyring.gpg',dest/'SHA256SUMS.gpg',dest/'SHA256SUMS'])
    rows=[line for line in (dest/'SHA256SUMS').read_text().splitlines() if line.split()[-1].lstrip('*')=='jammy-server-cloudimg-amd64.img']
    require(len(rows)==1 and len(rows[0].split()[0])==64,'Podepsaný seznam neobsahuje jednoznačný SHA-256 Ubuntu amd64.')
    expected=rows[0].split()[0]
    run(['curl','--fail','--location','--retry','3','--proto','=https','--tlsv1.2','-o',str(dest/'jammy-server-cloudimg-amd64.img'),base+'jammy-server-cloudimg-amd64.img'])
    import hashlib
    digest=hashlib.sha256()
    with (dest/'jammy-server-cloudimg-amd64.img').open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    require(digest.hexdigest()==expected,'SHA-256 staženého Ubuntu nesouhlasí. VM se nevytvořila.')
    run(['git','clone','--no-checkout','https://github.com/klange/nyancat.git',str(dest/'nyancat')])
    run(['git','-C',dest/'nyancat','checkout','--detach',NYANCAT])


def provision():
    run(['bash',TARGET/'host/bootstrap.sh'],cwd=TARGET)
    sys.path.insert(0,str(TARGET/'host'));import guest
    guest.wait(600)
    end=time.monotonic()+1200
    while time.monotonic()<end:
        if guest.execute('test -f /var/lib/linux-exam/provisioned')[0]==0:break
        time.sleep(2)
    else:raise RuntimeError('Cloud-init nedokončil přípravu. Zkontroluj konzoli a /var/log/linux-exam-provision.log ve VM; nic se automaticky nemaže.')
    run(['python3',TARGET/'host/finalize.py'],cwd=TARGET)
    guest.wait(180)
    for _ in range(120):
        if guest.execute('test -f /run/linux-exam/processes.json')[0]==0:break
        time.sleep(1)
    # Test jde přes stdin, nezůstane v systémovém obrazu ani nezačne časovač.
    import base64
    data=base64.b64encode((TARGET/'tests/initial.py').read_bytes()).decode()
    c,o,e=guest.execute("printf '%s' '"+data+"' | base64 -d | python3")
    (TARGET/'reports/install-smoke.log').write_text(o+e)
    require(c==0,'Výchozí smoke test neprošel; viz reports/install-smoke.log. VM nebyla resetována ani odstraněna.')
    print(o,flush=True)


def install(plan,yes):
    require(os.geteuid()==0,'Instalaci spusť pomocí sudo ./install.sh.')
    if not yes:
        answer=input('Instalovat uvedené chybějící balíčky a vytvořit vlastní VM? [ano/NE]: ')
        require(answer.strip().lower() in ('ano','yes','y'),'Instalace zrušena; žádné změny se neprovedly.')
    # Zámek je mimo dosud neexistující cílový projekt.
    lock_path=Path('/run/lock/linux-exam-install.lock')
    fd=os.open(lock_path,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not collision_check(which=shutil.which('linux-exam')),'Instalace již existuje.')
        fresh_libvirt=not Path('/etc/libvirt/qemu').exists() and not Path('/etc/libvirt/qemu/networks/default.xml').exists()
        if plan['missing']:
            run(['apt-get','update'])
            run(['apt-get','install','--no-install-recommends','--no-upgrade','--no-remove','-y',*plan['missing']])
        start_libvirt()
        if fresh_libvirt:
            # Pouze default vytvořený právě naší čerstvou instalací balíčků.
            # Existující síť se nikdy nevypíná ani nedefinuje znovu.
            info=run(['virsh','-c','qemu:///system','net-info','default'],False,True)
            if info.returncode==0:
                run(['virsh','-c','qemu:///system','net-autostart','default','--disable'])
                if any(line.startswith('Active:') and line.split(':',1)[1].strip()=='yes' for line in info.stdout.splitlines()):
                    run(['virsh','-c','qemu:///system','net-destroy','default'])
        require(VM not in domain_names(),'Jméno VM bylo mezitím obsazeno; nic nepřepisuji.')
        copy_source()
        (TARGET/'build/resources.json').write_text(json.dumps(plan['resources']))
        log=TARGET/'reports/install.log'
        print('Průběh přípravy: '+str(log),flush=True)
        # Zachovat všechny české zprávy i původní výjimku do diagnostického logu.
        try:
            with log.open('w') as output:
                command=['python3',TARGET/'host/install.py','--prepare']
                process=subprocess.Popen([str(x) for x in command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,stdin=subprocess.DEVNULL)
                for line in process.stdout:print(line,end='',flush=True);output.write(line);output.flush()
                require(process.wait()==0,'Příprava VM selhala; viz '+str(log)+'. Rozpracované prostředí zůstalo zachované.')
        except Exception:raise
        COMMAND.parent.mkdir(parents=True,exist_ok=True)
        require(not occupied(COMMAND),'Příkaz linux-exam byl mezitím obsazen; nepřepisuji jej.')
        COMMAND.symlink_to(TARGET/'host/linux-exam')
        print('\nHotovo: linux-exam con\nUvnitř VM: starttest | statstest | pomoc-test\nNový pokus: linux-exam reset (potvrzení RESET).',flush=True)


def main():
    os.environ['LINUX_EXAM_INSTANCE']='main'
    parser=argparse.ArgumentParser(description='Bezpečná instalace Linux Essentials pro Debian/Ubuntu.')
    parser.add_argument('--check',action='store_true',help='Pouze čtení; nic nemění.')
    parser.add_argument('--yes',action='store_true',help='Potvrdit instalaci bez otázky.')
    parser.add_argument('--prepare',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.prepare:
        require(os.geteuid()==0 and SOURCE==TARGET,'Interní příprava je možná jen z nainstalovaného projektu.')
        verify_downloads();provision();return
    plan=preflight()
    print('Systém: '+plan['release'].get('PRETTY_NAME','Debian/Ubuntu'))
    if plan['already']:
        if not occupied(COMMAND):
            if args.check:print('Připravenému prostředí chybí příkaz; sudo ./install.sh jej bezpečně doplní.')
            else:
                require(os.geteuid()==0,'Doplnění příkazu vyžaduje sudo.')
                COMMAND.parent.mkdir(parents=True,exist_ok=True)
                COMMAND.symlink_to(TARGET/'host/linux-exam')
                print('Doplněn chybějící příkaz linux-exam. Disky ani pokus se nezměnily.')
        print('Prostředí je již připravené. Pokus zůstává beze změn. Připojení: linux-exam con.');return
    print('VM: {vcpus} vCPU, {memory_mib} MiB RAM, disky 20 GiB + 1 GiB + 128 MiB.'.format(**plan['resources']))
    print('Chybějící balíčky: '+(', '.join(plan['missing']) or 'žádné'))
    print('Zdroj: '+str(SOURCE)+'\nCíl: '+str(TARGET)+'\nVirtualizace: KVM; síť VM: QEMU user NAT.')
    if args.check:print('Kontrola dokončena. Nic se nezměnilo.');return
    install(plan,args.yes)

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,subprocess.CalledProcessError,ValueError) as error:
        print('Instalace odmítnuta / chyba: '+str(error),file=sys.stderr);sys.exit(1)
    except KeyboardInterrupt:print('\nInstalace přerušena. Existující prostředí se nemaže.',file=sys.stderr);sys.exit(130)
