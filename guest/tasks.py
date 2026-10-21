"""Skutečné, pouze čtecí kontroly stavu uvnitř cvičného VM."""
import os,stat,pwd,grp,spwd,crypt,hashlib,json,subprocess,time,tarfile,gzip,datetime,re,ctypes,locale,ipaddress
from pathlib import Path

TASKS=[
('1',1,'Instalace Midnight Commander'),('2',1,'Odinstalování curl'),
('3',1,'Uživatelka aneta a její domov'),('4',1,'Heslo uživatelky aneta'),('5',1,'Odstranění lubose i domova'),('6',1,'Skupina spravci'),
('7',1,'Záloha úvodní stránky'),('8',2,'Úplná kopie protokolů nginx'),('9',1,'Aktuální datum v souboru'),('10',1,'Přejmenování hesla.doc'),('11',2,'Soubor adam_bartak.txt'),('12',1,'Odstranění karlovy zálohy'),
('13',1,'Vlastnictví /var/tajny'),('14',1,'Vstup do /var/mojedata'),('15',1,'Vlastnictví /var/uloziste'),('16',3,'Přístup do domova webapp'),('17',3,'Přístup do domova webapp2'),
('18',1,'Ukončení nginx'),('19',2,'Ukončení odolného apache'),('20',1,'Nekomprimovaný archiv /etc'),('21',2,'Komprimovaný archiv domova anety'),('22',1,'Kompilace nyancat'),('23',1,'Připojení /dev/sda1'),('24',1,'Odpojení flashky'),('25a',1,'Adresa rozhraní eth1'),('25b',1,'Překlad jecnavecna.cz')]
assert len(TASKS)==26 and sum(t[1] for t in TASKS)==34

def run(args,timeout=4):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=timeout)
    return p.returncode,p.stdout.strip()
def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def regular(p): return Path(p).is_file() and not Path(p).is_symlink()
def directory(p): return Path(p).is_dir() and not Path(p).is_symlink()
def absent(p): return not os.path.lexists(p)
def user(n):
    try:return pwd.getpwnam(n)
    except KeyError:return None
def group(n):
    try:return grp.getgrnam(n)
    except KeyError:return None
def package(n):return run(['dpkg-query','-W','-f=${Status}',n])[1]=='install ok installed'
def proc_identity(pid):
    data=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return data[0],data[19]
def terminated(name):
    info=json.loads(Path('/run/linux-exam/processes.json').read_text())[name]
    try:
        state,ticks=proc_identity(info['pid'])
        return state in ('Z','X') or ticks!=info['ticks']
    except FileNotFoundError:return True

def acl(p):
    code,txt=run(['getfacl','-cp',p])
    if code:raise ValueError('Nelze načíst ACL')
    rows={}
    for line in txt.splitlines():
        line=line.split('#')[0].strip()
        if not line or line.startswith('default:'):continue
        kind,name,perms=line.split(':')
        rows[(kind,name)]=set(perms.replace('-',''))
    mask=rows.get(('mask',''),set('rwx'))
    return {k:(v&mask if k[0]=='group' or k[0]=='user' and k[1] else v) for k,v in rows.items() if k[0]!='mask'}
def permissions(p,task):
    if not directory(p):return False
    s=os.stat(p);a=acl(p)
    if task==14:
        return 'x' in a[('user','')] and 'x' in a[('group','')] and 'x' not in a[('other','')] and all('x' not in v for k,v in a.items() if k[1])
    owner='webapp' if task==16 else 'webapp2'
    if s.st_uid!=pwd.getpwnam(owner).pw_uid or 'x' not in a[('user','')]:return False
    # POSIX nejprve vyhodnotí vlastníka. Named-user ACL stejného UID se
    # nikdy nepoužije a nemůže přístup ostatních rozšířit ani vlastníka omezit.
    a={k:v for k,v in a.items() if not (k[0]=='user' and k[1] in (owner,str(s.st_uid)))}
    if task==16:return all('x' not in v for k,v in a.items() if k!=('user',''))
    if 'w' not in a[('user','')] or a[('other','')]:return False
    apps=grp.getgrnam('apps').gr_gid
    allowed=False
    for (kind,name),perms in a.items():
        if (kind,name) in [('user',''),('other','')]:continue
        is_apps=kind=='group' and (name=='apps' or not name and s.st_gid==apps)
        if is_apps:
            if 'w' in perms:return False
            allowed=allowed or 'x' in perms
        elif perms:return False
    return allowed

def tree_matches(source,dest):
    # os.walk neexistující či nečitelný zdroj jinak tiše přeskočí.
    if not directory(source) or not directory(dest):return False
    def fail(error):raise error
    seen=False
    try:
        for root,dirs,files in os.walk(source,onerror=fail):
            seen=True
            relative=Path(root).relative_to(source);target=Path(dest)/relative
            if not directory(target):return False
            for name in dirs+files:
                s=Path(root)/name;d=target/name
                if s.is_symlink():
                    if not d.is_symlink() or os.readlink(s)!=os.readlink(d):return False
                elif s.is_dir():
                    if not directory(d):return False
                elif not regular(s) or not regular(d) or digest(s)!=digest(d):return False
        return seen
    except OSError:return False

def current_date():
    p=Path('/tmp/datum.txt')
    if not regular(p) or p.stat().st_size>256:return False
    value=p.read_text().strip()
    if not value or '\n' in value or re.fullmatch(r'[0-9]+',value):return False
    code,out=run(['date','--date='+value,'+%s'])
    if code==0 and abs(time.time()-int(out))<=300 and re.search(r'\d{1,2}:\d{2}',value):return True
    # GNU date neumí zpětně parsovat vlastní české názvy měsíců.
    original=locale.setlocale(locale.LC_TIME)
    normalized_value=' '.join(value.split())
    try:
        for language in ('cs_CZ.UTF-8','en_US.UTF-8','C'):
            try:locale.setlocale(locale.LC_TIME,language)
            except locale.Error:continue
            fmt=locale.nl_langinfo(locale.D_T_FMT)
            now=int(time.time())
            for stamp in range(now-300,now+301):
                if any(' '.join(time.strftime(pattern,time.localtime(stamp)).split())==normalized_value for pattern in (fmt,fmt+' %Z')):return True
    finally:locale.setlocale(locale.LC_TIME,original)
    return False

def normalized(name):
    p=Path(name)
    if '..' in p.parts:raise ValueError('Neplatná cesta v archivu')
    while name.startswith('./'):name=name[2:]
    return name.lstrip('/').rstrip('/')
def archive(path,home=False,*,source_root=None,fixture_manifest=None):
    if not regular(path):return False
    p=Path(path)
    source_root=Path(source_root or ('/home/aneta' if home else '/etc'))
    fixture_manifest=Path(fixture_manifest or '/opt/linux-exam/fixture-manifest.json')
    if p.stat().st_size>1024*1024*1024:return False
    # Archiv je snímek v okamžiku dokončení, nikoli zrcadlo pozdějšího stavu.
    # Např. exit ze su může až potom zapsat novou .bash_history.
    archive_time=p.stat().st_mtime_ns
    with p.open('rb') as stream:magic=stream.read(2)
    if home:
        u=user('aneta')
        if not u or p.stat().st_uid!=u.pw_uid or magic!=b'\x1f\x8b':return False
    elif magic==b'\x1f\x8b':return False
    with tarfile.open(path,'r:gz' if home else 'r:') as tf:
        entries={};total=0
        for member in tf:
            name=normalized(member.name)
            if member.isfile():
                if member.size>512*1024*1024:return False
                h=hashlib.sha256();stream=tf.extractfile(member)
                for block in iter(lambda:stream.read(1024*1024),b''):
                    total+=len(block)
                    if total>2*1024*1024*1024:return False
                    h.update(block)
                entries[name]=('file',h.hexdigest())
            elif member.issym():entries[name]=('link',member.linkname)
            elif member.isdir():entries[name]=('dir','')
            elif member.islnk():entries[name]=('hardlink',normalized(member.linkname))
        if not entries:return False
    def entry(name):
        """Tvrdý odkaz musí vést na skutečná data téhož archivu."""
        seen=set()
        while name in entries and entries[name][0]=='hardlink':
            if name in seen:return None
            seen.add(name);name=entries[name][1]
        return entries.get(name)
    # Ani nereprezentativní dangling/cyklický hardlink není úplná záloha.
    if any(kind=='hardlink' and (entry(name) is None or entry(name)[0]!='file')
           for name,(kind,value) in entries.items()):return False
    if home:
        # Povoleny jsou tar -C /home aneta, absolutní cesta i tar -C /home/aneta .
        prefixes=['home/aneta/','aneta/','']
        sources=[f for f in source_root.rglob('*') if f!=p and (f.is_file() or f.is_dir() or f.is_symlink())]
        if not sources:return False
        def matching(prefix):
            represented=False
            for f in sources:
                name=prefix+str(f.relative_to(source_root))
                archived=entry(name)
                if archived and archived[0]=='file':represented=True
                # Nový nebo později přepsaný soubor nemůže vyvrátit správnost
                # dřívějšího snímku. Starší soubory vyžadujeme včetně obsahu.
                if f.lstat().st_mtime_ns<=archive_time:
                    expected_content=('link',os.readlink(f)) if f.is_symlink() else ('dir','') if f.is_dir() else ('file',digest(f))
                    if archived!=expected_content:return False
            return represented
        if not any(matching(prefix) for prefix in prefixes):return False
        # gzip musí být včetně CRC a závěru čitelný až do EOF.
        with gzip.open(path,'rb') as stream:
            while stream.read(1024*1024):pass
        return True
    expected=json.loads(fixture_manifest.read_text())['etc']
    names=set(entries)
    if 'etc' not in names or entries['etc'][0]!='dir':return False
    if len(names & set(expected))/len(expected)<0.90:return False
    for f in ['etc/passwd','etc/group','etc/hosts','etc/fstab','etc/os-release']:
        if f not in entries:return False
        archived=entry(f)
        if not archived or archived[0] not in ('file','link'):return False
        source=source_root/Path(f).relative_to('etc')
        if os.path.lexists(source) and source.lstat().st_mtime_ns<=archive_time:
            expected_content=('link',os.readlink(source)) if source.is_symlink() else ('file',digest(source))
            if archived!=expected_content:return False
    # Ověření neporušeného taru navíc nástrojem GNU tar.
    return run(['tar','-tf',path],timeout=8)[0]==0

def compiled():
    p='/opt/nyancat/src/nyancat'
    if not regular(p) or not os.access(p,os.X_OK) or Path(p).open('rb').read(4)!=b'\x7fELF':return False
    # Program se spouští bez root práv a s časovým limitem.
    code,out=run(['runuser','-u','student','--',p,'--help'])
    return code==0 and 'nyancat' in out.lower()
def mounted_disk():
    code,out=run(['findmnt','-rn','-M','/mnt/disk','-o','MAJ:MIN'])
    s=os.stat('/dev/sda1')
    return code==0 and out==f'{os.major(s.st_rdev)}:{os.minor(s.st_rdev)}'
def hosts():
    lines=Path('/etc/hosts').read_text().splitlines();mapping={}
    for line in lines:
        fields=line.split('#',1)[0].split()
        if len(fields)>1:
            for name in fields[1:]:mapping.setdefault(name,set()).add(fields[0])
    if mapping.get('jecnavecna.cz')!={'127.0.0.1'}:return False
    important=json.loads(Path('/opt/linux-exam/fixture-manifest.json').read_text())['hosts']
    if any(not set(addresses)<=mapping.get(name,set()) for name,addresses in important.items()):return False
    code,out=run(['getent','ahostsv4','jecnavecna.cz'])
    code6,out6=run(['getent','ahostsv6','jecnavecna.cz'])
    addresses={line.split()[0] for line in (out+'\n'+out6).splitlines() if line.strip()}
    addresses={str(ipaddress.ip_address(a).ipv4_mapped or ipaddress.ip_address(a)) if isinstance(ipaddress.ip_address(a),ipaddress.IPv6Address) else a for a in addresses}
    return code==0 and addresses=={'127.0.0.1'}
def validate(task):
    if task=='1':return package('mc')
    if task=='2':return not package('curl') and not Path('/usr/bin/curl').exists()
    if task=='3':
        u=user('aneta');return bool(u and u.pw_dir=='/home/aneta' and directory(u.pw_dir) and os.stat(u.pw_dir).st_uid==u.pw_uid)
    if task=='4':
        if not user('aneta'):return False
        h=spwd.getspnam('aneta').sp_pwdp
        return h not in ('','!','*') and crypt.crypt('xy5631786',h)==h
    if task=='5':return user('lubos') is None and absent('/home/lubos')
    if task=='6':return group('spravci') is not None
    if task=='7':
        src='/var/www/html/index.nginx-debian.html';dest=src+'.bak'
        return regular(src) and regular(dest) and digest(src)==digest(dest)
    if task=='8':return tree_matches('/var/log/nginx','/var/zalohy-nginx/nginx')
    if task=='9':return current_date()
    if task=='10':return absent('/home/jan/hesla.doc') and regular('/home/jan/hesla.doc.bak') and digest('/home/jan/hesla.doc.bak')==json.loads(Path('/opt/linux-exam/fixture-manifest.json').read_text())['hesla']
    if task=='11':return regular('/home/pepa/adam_bartak.txt')
    if task=='12':return absent('/home/karel/zaloha')
    if task=='13':
        s=os.stat('/var/tajny');return directory('/var/tajny') and s.st_uid==pwd.getpwnam('nobody').pw_uid and s.st_gid==grp.getgrnam('nogroup').gr_gid
    if task in ('14','16','17'):return permissions({'14':'/var/mojedata','16':'/home/webapp','17':'/home/webapp2'}[task],int(task))
    if task=='15':return directory('/var/uloziste') and os.stat('/var/uloziste').st_uid==pwd.getpwnam('jouda').pw_uid
    if task in ('18','19'):return terminated('nginx' if task=='18' else 'apache')
    if task=='20':return archive('/home/aneta/zaloha-etc.tar')
    if task=='21':return archive('/home/aneta/zaloha.tar.gz',True)
    if task=='22':return compiled()
    if task=='23':return mounted_disk()
    if task=='24':return run(['mountpoint','-q','/mnt/flashka'])[0]!=0
    if task=='25a':
        code,out=run(['ip','-j','addr','show','dev','eth1'])
        return code==0 and any(a.get('local')=='192.168.99.5' and a.get('prefixlen')==24 for i in json.loads(out) for a in i['addr_info'])
    if task=='25b':return hosts()
    return False
