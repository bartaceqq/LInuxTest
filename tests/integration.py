#!/usr/bin/env python3
"""Skutečné systémové operace přes QGA a skutečná sériová konzole přes PTY.
Mění pouze dedikovaný cvičný VM. Po testech automaticky obnoví čistý stav.
"""
import sys,os,subprocess,json,time,base64,pathlib,select,pty,signal,traceback,hashlib
P=pathlib.Path('/opt/linux-exam-simulator');sys.path.insert(0,str(P/'host'));import guest
from config import REPORTS,D,MANIFEST,baseline as baseline_path
assert guest.VM=='linux-essentials-exam-qa','Testy běží pouze v oddělené QA VM.'
owned=False
report={'checks':[],'passed':False,'started':time.time()}
def check(name,condition=True):
    assert condition,name
    report['checks'].append(name);print('PASS:',name,flush=True)
def cmd(text,timeout=180,allowed=(0,)):
    code,out,err=guest.execute(text,timeout)
    if code not in allowed:raise AssertionError(f'Příkaz ve VM selhal ({code}): {text}\n{out}\n{err}')
    return out

def state():return json.loads(cmd('cat /var/lib/linux-exam/state.json'))
def wait_task(key,points,total):
    until=time.monotonic()+12
    while time.monotonic()<until:
        s=state()
        if key in s['completed']:
            check(f'B: úkol {key}: +{points}, celkem {total}/34',s['completed'][key]['points']==points and s['score']==total);return
        time.sleep(.4)
    raise AssertionError(f'Úkol {key} nebyl automaticky uznán: {state()}')
def wait_until(predicate,description,console=None,timeout=30):
    end=time.monotonic()+timeout
    last=None
    while time.monotonic()<end:
        try:
            result=predicate()
            if result:return result
        except (AssertionError,RuntimeError) as error:last=error
        if console:console.collect(.1)
        else:time.sleep(.15)
    raise AssertionError('Čekání selhalo: '+description+'; '+str(last))

def shell_ready(console):
    console.send('\x02');time.sleep(.06);console.send('1')
    wait_until(lambda:cmd('runuser -u student -- tmux display-message -p -t praktikum "#{@linux_exam_role}"').strip()=='shell',
               'aktivní skutečný shell po Ctrl+b, 1',console)

class Console:
    def __init__(self):
        assert guest.VM=='linux-essentials-exam-qa','Konzole testu smí mířit pouze na QA.'
        self.master,slave=pty.openpty()
        import fcntl,termios,struct
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
        self.proc=subprocess.Popen(['linux-exam','con'],stdin=slave,stdout=slave,stderr=slave,cwd='/tmp',start_new_session=True,env=dict(os.environ,TERM='xterm-256color',LINUX_EXAM_INSTANCE='qa'))
        os.close(slave);self.output=b'';self.connected=False;self.closed=False
        try:self.wait_connected()
        except Exception:
            self.close();raise
    def wait_connected(self,timeout=120):
        # Host nejprve může čekat na boot/QGA a opravit terminál. Do té doby
        # nesmíme do jeho PTY poslat Enter, prefix tmux ani příkazy studenta.
        expected="Connected to domain 'linux-essentials-exam-qa'"
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            text=self.collect(min(.2,max(0,end-time.monotonic())))
            if 'Connected to domain ' in text:
                assert expected in text,'Konzole se připojila k neočekávanému VM: '+text[-2000:]
                if 'Escape character is ' in text:
                    self.connected=True;return
            if self.proc.poll() is not None:break
        raise AssertionError('QA sériová konzole se nepřipojila včas: '+self.output.decode(errors='replace')[-4000:])
    def send(self,data):
        assert self.connected and not self.closed,'Před připojením QA konzole se neposílají žádné klávesy.'
        os.write(self.master,data.encode())
    def collect(self,seconds=2):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if select.select([self.master],[],[],min(.1,max(.001,end-time.monotonic())))[0]:
                try:
                    data=os.read(self.master,65536)
                    if not data:break
                    self.output+=data
                except OSError:break
        return self.output.decode(errors='replace')
    def close(self):
        if self.closed:return
        if self.connected:
            try:self.send('\x1d')
            except OSError:pass
        else:self.proc.terminate()
        try:self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=5)
        os.close(self.master);self.closed=True

def reset():
    p=subprocess.run(['linux-exam','reset'],input='RESET\n',capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr
    guest.wait(120)
    # QGA může přijít o chvíli dříve než příprava procesů.
    until=time.monotonic()+30
    while time.monotonic()<until:
        if guest.execute('test -f /run/linux-exam/processes.json')[0]==0:break
        time.sleep(.5)

def initial():
    data=base64.b64encode((P/'tests/initial.py').read_bytes()).decode()
    print(cmd("printf '%s' '"+data+"' | base64 -d | python3"),flush=True)
    check('A/D: všechny podmínky čistého VM a prázdné skóre')
try:
    guest.wait(120);initial();owned=True
    subprocess.run(['linux-exam','stop'],check=True,capture_output=True)
    until=time.monotonic()+60
    while subprocess.check_output(['virsh','-c','qemu:///system','domstate',guest.VM],text=True).strip()!='shut off' and time.monotonic()<until:time.sleep(.5)
    check('Ovládání: bezpečné vypnutí VM',subprocess.check_output(['virsh','-c','qemu:///system','domstate',guest.VM],text=True).strip()=='shut off')
    c=Console();text=c.collect(1)
    until=time.monotonic()+40
    while 'student@linux-exam' not in text and time.monotonic()<until:
        c.send('\r');text=c.collect(1)
    guest.wait(60)
    check('Konzole: automatický student@linux-exam', 'student@linux-exam' in text)
    before_status=state()
    before_text=cmd('runuser -u student -- bash -c "cd /tmp; command -v starttest; statstest"')
    check('Nové příkazy: dostupné z libovolného adresáře, žluté skóre a bez spuštění časovače','/usr/local/bin/starttest' in before_text and '\033[33mSKÓRE 0/34' in before_text and state()==before_status)
    c.send('stty rows 24 cols 80; starttest\r');text=c.collect(5)
    wait_until(lambda:state()['status']=='running','zahájení časovače',c)
    wait_until(lambda:cmd('runuser -u student -- tmux display-message -p -t praktikum "#{@linux_exam_role}"').strip()=='assignment','úplné první zadání',c)
    text=c.collect(.2)
    (REPORTS/'console-start.txt').write_text(text)
    s=state();check('Časovač: přesně 3900 sekund od prvního spuštění',s['deadline']-s['start']==3900 and s['score']==0)
    original_start=s['start'];original_deadline=s['deadline']
    check('Rozhraní: pět oken tmux',len(cmd('runuser -u student -- tmux list-windows -t praktikum').splitlines())==5)
    check('Rozhraní: automaticky zobrazené úplné zadání','ZADÁNÍ' in text or 'PRAKTIKUM' in text)
    shell_ready(c)
    c.send('sudo -n id -u > /tmp/exam-console-probe\r');c.collect(1)
    wait_until(lambda:cmd('cat /tmp/exam-console-probe',allowed=(0,1)).strip()=='0','Bash a sudo vykonaly skutečný příkaz',c)
    check('Konzole: skutečný interaktivní Bash a funkční sudo')
    # Nesprávné výsledky musejí zůstat bez bodů.
    cmd('''useradd -M -d /home/aneta -s /bin/bash aneta
printf 'aneta:nespravneheslo\n' | chpasswd
printf 'špatná záloha\n' > /var/www/html/index.nginx-debian.html.bak
mkdir -p /var/zalohy-nginx/nginx
printf '2020-01-01 00:00:00\n' > /tmp/datum.txt
printf 'nesprávný obsah\n' > /home/jan/hesla.doc.bak
ln -s /etc/hosts /home/pepa/adam_bartak.txt
chown nobody:root /var/tajny
mkdir /var/mojedata /var/uloziste
chmod 704 /var/mojedata
chmod 700 /home/webapp
chown webapp2:apps /home/webapp2
chmod 770 /home/webapp2
mkdir /home/aneta
printf 'není tar\n' > /home/aneta/zaloha-etc.tar
printf '\\037\\213není gzip\n' > /home/aneta/zaloha.tar.gz
printf '#!/bin/sh\necho nyancat\n' > /opt/nyancat/src/nyancat
chmod 755 /opt/nyancat/src/nyancat
mkdir /mnt/disk
mount -t tmpfs tmpfs /mnt/disk
ip addr add 192.168.99.5/32 dev eth1
cp /etc/hosts /run/exam-original-hosts
printf '127.0.0.2 jecnavecna.cz\n' >> /etc/hosts
kill -TERM $(pgrep -x apache)
''')
    time.sleep(3);check('B: nesprávné heslo, kopie, ACL/módy, archivy, falešný binární soubor, disk, IP a DNS bez bodů',state()['score']==0)
    check('B: apache odolává SIGTERM',cmd('pgrep -x apache').strip().isdigit())
    # Odstranění pouze nesprávných testovacích výstupů uvnitř VM.
    cmd('''rm -f /home/pepa/adam_bartak.txt /opt/nyancat/src/nyancat /home/aneta/zaloha-etc.tar /home/aneta/zaloha.tar.gz
rmdir /home/aneta
umount /mnt/disk
ip addr del 192.168.99.5/32 dev eth1
cp /run/exam-original-hosts /etc/hosts
''')
    operations=[
      ('1',1,'DEBIAN_FRONTEND=noninteractive apt-get install -y mc'),
      ('2',1,'DEBIAN_FRONTEND=noninteractive apt-get remove -y curl'),
      ('3',1,'install -d -o aneta -g aneta /home/aneta; cp -a /etc/skel/. /home/aneta/; chown -R aneta:aneta /home/aneta'),
      ('4',1,"printf 'aneta:xy5631786\\n' | chpasswd"),
      ('5',1,'userdel -r lubos'),('6',1,'groupadd spravci'),
      ('7',1,'cp /var/www/html/index.nginx-debian.html /var/www/html/index.nginx-debian.html.bak'),
      ('8',2,'cp -a /var/log/nginx /var/zalohy-nginx/'),
      ('9',1,'LC_ALL=cs_CZ.UTF-8 date > /tmp/datum.txt'),
      ('10',1,'mv /home/jan/hesla.doc /home/jan/hesla.doc.bak'),
      ('11',2,'touch /home/pepa/adam_bartak.txt'),('12',1,'rm -rf /home/karel/zaloha'),
      ('13',1,'chown nobody:nogroup /var/tajny'),('14',1,'chmod 710 /var/mojedata'),
      ('15',1,'chown jouda /var/uloziste'),('16',3,'chown webapp:webapp /home/webapp; chmod 740 /home/webapp'),
      ('17',3,'chmod 750 /home/webapp2'),('18',1,'kill -TERM $(pgrep -x nginx)'),('19',2,'kill -KILL $(pgrep -x apache)'),
      ('20',1,'tar -cf /home/aneta/zaloha-etc.tar /etc'),
      ('21',2,'chown aneta:aneta /home/aneta/zaloha-etc.tar; runuser -u aneta -- tar --exclude=aneta/zaloha.tar.gz -czf /home/aneta/zaloha.tar.gz -C /home aneta'),
      ('22',1,'runuser -u student -- make -C /opt/nyancat'),
      ('23',1,'mount /dev/sda1 /mnt/disk'),('24',1,'umount /mnt/flashka'),
      ('25a',1,'ip addr add 192.168.99.5/24 dev eth1'),
      ('25b',1,"printf '127.0.0.1 jecnavecna.cz\\n' >> /etc/hosts")]
    total=0
    for key,points,operation in operations:
        cmd(operation,300,allowed=(0,1) if key=='21' else (0,))
        total+=points;wait_task(key,points,total)
        if key=='1':
            panel=cmd('runuser -u student -- tmux capture-pane -p -t praktikum:1.2')
            check('Rozhraní: okamžitá událost v odděleném panelu', 'Midnight Commander' in panel and 'SKÓRE' in panel)
            manual=cmd('runuser -u student -- statstest')
            history=cmd('runuser -u student -- tmux capture-pane -p -S -150 -t praktikum:1.2')
            check('statstest: zelený splněný úkol, žluté chybějící úkoly a skóre', '\033[32m✓   1.' in manual and '\033[33m□   2.' in manual and '\033[33mSKÓRE 1/34' in manual)
            check('Automatický panel: celý stejný přehled jako statstest','SPLNĚNÉ ÚKOLY: 1 / 26' in history and 'ZBÝVÁ SPLNIT: 25 úkolů' in history and 'Heslo uživatelky aneta' in history)
        if key=='8':
            before=state();c.close();time.sleep(2);c=Console();c.collect(2);c.send('\x02d');c.collect(1);c.send('starttest\r');c.collect(3)
            after=state();check('C: odpojení a opětovné starttest zachová skóre, start a termín',after['score']==before['score'] and after['start']==original_start and after['deadline']==original_deadline)
            check('C: pokračuje čas a existuje jediná relace tmux',time.time()>before['start']+2 and len(cmd('runuser -u student -- tmux list-sessions -F "#{session_name}"').splitlines())==1)
            cmd('systemctl restart linux-exam-grader');time.sleep(1)
            check('C: restart hodnotiče zachová termín',state()['deadline']==original_deadline)
    check('B: přesně 34/34, 26 kontrol, stav finished',state()['score']==34 and len(state()['completed'])==26 and state()['status']=='finished')
    cmd('touch /home/pepa/adam_bartak.txt; chmod 750 /home/webapp2; systemctl restart linux-exam-grader');time.sleep(3)
    check('B: žádné duplicitní body',state()['score']==34 and len(state()['completed'])==26)
    (REPORTS/'solved-state.json').write_text(json.dumps(state(),ensure_ascii=False,indent=2))
    cmd('runuser -u aneta -- tar --exclude=./zaloha.tar.gz -czf /home/aneta/zaloha.tar.gz -C /home/aneta .',allowed=(0,1))
    check('B: archiv domova s cestami ./ a skrytými soubory',cmd("python3 -c \"import sys;sys.path.insert(0,'/opt/linux-exam');import tasks;assert tasks.validate('21');print('OK')\"").strip()=='OK')
    canceled=subprocess.run(['linux-exam','reset'],input='NE\n',text=True,capture_output=True)
    check('D: odmítnutí resetu zachová skóre',canceled.returncode==1 and state()['score']==34)
    c.close();reset();initial();check('D: reset obnovil všechny tři disky a výchozí podmínky')
    # Nový pokus a řízené zrychlení času pouze pro test expirace.
    c=Console();c.collect(2);c.send('\r');c.collect(1);c.send('~/test.sh\r');c.collect(3)
    wait_until(lambda:state()['status']=='running','nový časovač po resetu',c)
    s=state();check('D: nový pokus opět dostal přesně 65 minut',s['deadline']-s['start']==3900 and s['start']!=original_start)
    cmd('''python3 - <<'TEST'
import sys,time
sys.path.insert(0,'/opt/linux-exam');import state
with state.locked():
 s=state.read();s['deadline']=time.time()+2;state.write(s)
TEST''')
    time.sleep(3);check('Časovač: automatická expirace',state()['status']=='expired')
    cmd('groupadd spravci');time.sleep(2);check('Časovač: po termínu nepřibudou body',state()['score']==0)
    check('Časovač: závěrečné hlášení v událostech',any('KONEC ZKOUŠKY' in e['text'] for e in state()['events']))
    c.collect(1);c.close();reset();initial()
    report['passed']=True
except Exception as e:
    report['error']=str(e);traceback.print_exc()
    try:c.close()
    except Exception:pass
    if owned:
        try:reset();report['clean_after_failure']=True
        except Exception as e2:report['reset_error']=str(e2)
finally:
    report['ended']=time.time();(REPORTS/'integration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
if not report['passed']:sys.exit(1)
print('A–D: VŠECHNY INTEGRAČNÍ TESTY PROŠLY; VM JE ČISTÁ.',flush=True)
