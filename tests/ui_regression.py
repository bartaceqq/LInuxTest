#!/usr/bin/env python3
"""Regrese konzole/UI pouze v odděleném QA VM; nikdy neresetuje stav zkoušky.

LINUX_EXAM_INSTANCE=qa python3 /tmp/linux-exam-reliability-tests/ui_regression.py
Požaduje připravený QA VM a aktuální guest/session.py. Úmyslně zavírá jeho
testovací okna/panely a konzoli, proto má před každým přístupem pevnou pojistku QA.
"""
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import shlex
import struct
import subprocess
import sys
import termios
import time
import traceback
import uuid

assert os.environ.get('LINUX_EXAM_INSTANCE') == 'qa', 'Test smí běžet pouze s LINUX_EXAM_INSTANCE=qa.'
PROJECT = Path('/opt/linux-exam-simulator')
sys.path.insert(0, str(PROJECT / 'host'))
import guest
assert guest.VM == 'linux-essentials-exam-qa', f'NEBEZPEČNÝ CÍL {guest.VM!r}: zastavuji bez zásahu.'
from config import REPORTS
qa_uuid=subprocess.check_output(['virsh','-c','qemu:///system','domuuid',guest.VM],text=True).strip()
assert subprocess.check_output(['virsh','-c','qemu:///system','domname',qa_uuid],text=True).strip()==guest.VM

RUN = uuid.uuid4().hex[:10]
BASE = f'/tmp/linux-exam-ui-regression-{RUN}'
REPORT = REPORTS/'ui-regression.json'
report = {'vm': guest.VM, 'started': time.time(), 'passed': False, 'checks': []}
console = None
baseline = None


def command(text, timeout=30, allowed=(0,)):
    assert os.environ.get('LINUX_EXAM_INSTANCE') == 'qa' and guest.VM == 'linux-essentials-exam-qa'
    code, out, err = guest.execute(text, timeout)
    if code not in allowed:
        raise AssertionError(f'Příkaz QA selhal ({code}): {text}\n{out}\n{err}')
    return out


def tmux(*args):
    return command('runuser -u student -- tmux ' + shlex.join(args))


def read_state():
    return json.loads(command('cat /var/lib/linux-exam/state.json'))


def stable(s):
    return {k: s.get(k) for k in ('start', 'deadline', 'score', 'completed', 'status', 'finished_at')}


def check(name, condition=True):
    assert condition, name
    report['checks'].append(name)
    print('PASS:', name, flush=True)


def wait_until(function, description, timeout=15):
    until = time.monotonic() + timeout
    last = None
    while time.monotonic() < until:
        try:
            value = function()
            if value:
                return value
        except (RuntimeError, AssertionError) as error:
            last = error
        time.sleep(.15)
    raise AssertionError(f'Čekání selhalo: {description}; poslední chyba: {last}')


def role_pane(role):
    output = tmux('list-panes', '-a', '-F', '#{session_name}\t#{pane_id}\t#{@linux_exam_role}')
    matches = [r.split('\t')[1] for r in output.splitlines()
               if r.startswith('praktikum\t') and r.endswith('\t' + role)]
    assert len(matches) == 1, f'Role {role}: očekávám jediný panel, nalezeno {matches}; {output}'
    return matches[0]


def active_pane():
    return tmux('display-message', '-p', '-t', 'praktikum', '#{pane_id}').strip()


def expect_shell():
    return wait_until(lambda: active_pane() == role_pane('shell'), 'aktivní shellový panel')


def go(role):
    command('runuser -u student -- python3 /opt/linux-exam/session.py go ' + shlex.quote(role))


class Console:
    def __init__(self, rows=24, columns=80):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))
        self.proc = subprocess.Popen(['linux-exam', 'con'], stdin=slave, stdout=slave,
                                     stderr=slave, cwd='/tmp', start_new_session=True,
                                     env=dict(os.environ, TERM='xterm-256color'))
        os.close(slave)
        self.output = bytearray()
        self.closed = False
        text = self.collect(1)
        until=time.monotonic()+35
        while "Connected to domain '" not in text and time.monotonic()<until:
            text=self.collect(.2)
        assert "Connected to domain 'linux-essentials-exam-qa'" in text,text
        # Přítomný název domény nesmí odkazovat na hlavní VM.
        if "Connected to domain '" in text:
            assert "Connected to domain 'linux-essentials-exam-qa'" in text, text

    def send(self, data):
        os.write(self.master, data.encode() if isinstance(data, str) else data)

    def prefix(self, key):
        self.send(b'\x02')
        time.sleep(.06)
        self.send(key)

    def collect(self, seconds=.4):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if select.select([self.master], [], [], min(.1, max(.001, end - time.monotonic())))[0]:
                try:
                    data = os.read(self.master, 65536)
                    if not data:
                        break
                    self.output.extend(data)
                except OSError:
                    break
        return self.output.decode(errors='replace')

    def close(self, abrupt=False):
        if self.closed:
            return
        if not abrupt:
            try:
                self.send(b'\x1d')
                self.collect(.2)
            except OSError:
                pass
        os.close(self.master)
        self.closed = True
        try:
            self.proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=4)


def marker(label):
    path = f'{BASE}-{label}'
    text = f'UI_OK_{RUN}_{label}'
    console.send(f"printf '%s\\n' {shlex.quote(text)} > {shlex.quote(path)}\r")
    console.collect(.25)
    wait_until(lambda: command(f'cat {shlex.quote(path)}', allowed=(0, 1)).strip() == text,
               'skutečný Bash vykonal marker ' + label)


def prefix_shell():
    console.prefix('1')
    console.collect(.2)
    expect_shell()


def reconnect(abrupt=False, columns=80):
    global console
    before = stable(read_state())
    console.close(abrupt=abrupt)
    time.sleep(.4)
    console = Console(columns=columns)
    console.send('\r')
    console.collect(.5)
    # Konzole může zůstat ve stále připojeném tmux nebo v přihlašovacím Bashi.
    clients = tmux('list-clients', '-F', '#{client_session}').splitlines()
    if 'praktikum' not in clients:
        console.send('starttest\r')
        console.collect(1)
    prefix_shell()
    marker('reconnect-abrupt' if abrupt else 'reconnect-normal')
    check(('Tvrdé zavření PTY' if abrupt else 'Ctrl+] a nové připojení') + ': zachovaný stav a psaní',
          stable(read_state()) == before)


RAW_READER = r'''
import json,os,re,select,sys,termios,time,tty
from pathlib import Path
output=Path(sys.argv[1]);fd=sys.stdin.fileno();old=termios.tcgetattr(fd);data=b''
pattern=re.compile(rb'\x1b(?:O[QS]|\[(?:12|14)~)')
try:
 tty.setraw(fd)
 output.with_suffix('.ready').write_text('ready')
 deadline=time.monotonic()+12
 while time.monotonic()<deadline:
  if select.select([fd],[],[],.25)[0]:
   data+=os.read(fd,4096)
   if len(pattern.findall(data))>=4:break
finally:
 termios.tcsetattr(fd,termios.TCSADRAIN,old)
keys=[]
for match in pattern.findall(data):keys.append('F2' if match in (b'\x1bOQ',b'\x1b[12~') else 'F4')
output.write_text(json.dumps({'hex':data.hex(),'keys':keys}))
'''


try:
    guest.wait(60)
    before = read_state()
    assert before['status'] in ('not_started', 'running'), 'QA test vyžaduje čerstvý nebo běžící pokus.'
    assert before['score'] == 0 and not before['completed'], 'QA test vyžaduje neřešený pokus 0/34.'
    console = Console()
    # Je-li test opakován nad živým QA, nejprve vyber již existující shell.
    sessions = command('runuser -u student -- tmux list-sessions -F "#{session_name}"', allowed=(0, 1))
    if 'praktikum' in sessions.splitlines():
        go('shell')
    else:
        console.send('\r')
        text=console.collect(.5)
        until=time.monotonic()+35
        while 'student@linux-exam' not in text and time.monotonic()<until:
            console.send('\r');text=console.collect(.3)
        assert 'student@linux-exam' in text,'Přihlašovací shell není připravený.'
    console.send('starttest\r')
    console.collect(1.5)
    wait_until(lambda: read_state()['status'] == 'running', 'zkouška spuštěna')
    baseline = stable(read_state())
    check('Starttest: jednou spuštěný přesný časovač 3900 sekund',
          baseline['deadline'] - baseline['start'] == 3900)
    prefix_shell()
    marker('initial')
    check('80×24: skutečný interaktivní Bash')

    # F-klávesy zůstanou aplikaci; různé terminály posílají SS3 nebo CSI.
    keys = tmux('list-keys', '-T', 'root')
    check('F1–F4 nejsou globální přepínače oken', not re.search(r'\sF[1-4]\s+.*select-window', keys))
    reader_path = f'{BASE}-raw.py'
    import base64
    data = base64.b64encode(RAW_READER.encode()).decode()
    command(f"printf '%s' {shlex.quote(data)} | base64 -d > {shlex.quote(reader_path)}; chmod 644 {shlex.quote(reader_path)}")
    raw_output = f'{BASE}-raw.json'
    console.send(f'python3 {shlex.quote(reader_path)} {shlex.quote(raw_output)}\r')
    ready = str(Path(raw_output).with_suffix('.ready'))
    wait_until(lambda: command(f'test -f {shlex.quote(ready)} && echo ready', allowed=(0, 1)).strip() == 'ready',
               'aplikace přepnula terminál do raw režimu')
    console.send(b'\x1bOQ\x1bOS\x1b[12~\x1b[14~')
    raw = wait_until(lambda: command(f'cat {shlex.quote(raw_output)}', allowed=(0, 1)), 'F-klávesy zachycené aplikací')
    payload = json.loads(raw)
    check('F2/F4 přes SS3 i CSI dorazí aplikaci bez změny okna',
          payload['keys'] == ['F2', 'F4', 'F2', 'F4'] and active_pane() == role_pane('shell'))
    marker('after-functions')

    # Stejná dvojice, kterou uživatel hlásil: Bash F4 otevře zadání a F2 vrátí vstup.
    for label, show, back in (('SS3', b'\x1bOS', b'\x1bOQ'),
                              ('CSI', b'\x1b[14~', b'\x1b[12~')):
        console.send(show)
        wait_until(lambda: active_pane() == role_pane('assignment'), 'F4 otevře zadání '+label)
        console.collect(.2)
        console.send(back)
        expect_shell()
        marker('f4-f2-'+label)
        check('F4 → F2: zadání a zpět bez vloženého textu '+label)

    for number, role in (('2', 'tasks'), ('3', 'assignment'), ('4', 'help'), ('5', 'result')):
        console.prefix(number)
        wait_until(lambda: tmux('display-message', '-p', '-t', 'praktikum', '#{window_index}').strip() == number,
                   f'Ctrl+b {number} otevře {role}')
        console.send('q')
        expect_shell()
        marker('back-from-' + role)
        check(f'Ctrl+b {number}: {role}; q vrací skutečný shell')

    tmux('select-pane', '-t', role_pane('progress'))
    prefix_shell()
    marker('from-progress')
    check('Ctrl+b 1 přepne z přehledu přímo do vstupu příkazů')

    console.send('exit\r')
    console.collect(.8)
    marker('after-exit')
    console.send(b'\x04')
    console.collect(.8)
    marker('after-eof')
    check('Exit i Ctrl+D automaticky obnoví použitelný shell')

    tmux('kill-window', '-t', 'praktikum:2')
    console.send('starttest\r')
    console.collect(1)
    prefix_shell()
    wait_until(lambda: len(tmux('list-windows', '-t', 'praktikum').splitlines()) == 5, 'opravené chybějící okno')
    marker('repaired-window')
    check('Opakované starttest opraví chybějící okno a nevytváří další pokus')

    tmux('kill-pane', '-t', role_pane('progress'))
    console.send('starttest\r')
    console.collect(1)
    prefix_shell()
    wait_until(lambda:role_pane('progress'),'opravený a označený panel přehledu')
    check('Starttest opraví chybějící panel přehledu')
    tmux('kill-pane', '-t', role_pane('shell'))
    go('shell')
    expect_shell()
    marker('repaired-shell')
    check('Session go shell opraví chybějící shell i při přeživším panelu přehledu')

    console.prefix('d')
    console.collect(.5)
    console.send('starttest\r')
    console.collect(1)
    prefix_shell()
    marker('reattach')
    check('Tmux detach a starttest naváže jedinou relaci',
          tmux('list-sessions', '-F', '#{session_name}').splitlines() == ['praktikum'])
    reconnect()
    reconnect(abrupt=True, columns=120)

    console.send('stty rows 35 cols 120\r')
    console.collect(.3)
    console.send('starttest\r')
    console.collect(.8)
    prefix_shell()
    marker('wide-terminal')
    check('120×35: širší terminál zachová ovládání')

    colors = command('runuser -u student -- statstest')
    check('Statstest: skóre i chybějící úkoly jsou žluté',
          '\x1b[33m' in colors and 'SKÓRE 0/34' in colors and 'ZBÝVÁ SPLNIT' in colors)
    # Čistý pokus nemá zelený splněný úkol: testuje pouze render, nikoli stav VM.
    render = command("python3 - <<'PY'\nimport sys;sys.path.insert(0,'/opt/linux-exam');import progress,state\ns=state.read();s['completed']={'1':{'time':1,'points':1,'title':'Test barvy'}};s['score']=1\nprint(progress.render(s))\nPY")
    check('Statstest: splněné úkoly jsou zelené bez zásahu do stavu', '\x1b[32m' in render and 'Midnight' in render)
    check('Celá UI regrese zachovala skóre, úkoly, začátek i deadline', stable(read_state()) == baseline)
    report['passed'] = True
except Exception as error:
    report['error'] = str(error)
    traceback.print_exc()
finally:
    if console:
        try:
            console.collect(.2)
            (REPORTS/'ui-console.txt').write_bytes(console.output)
            console.close()
        except Exception as error:
            report['cleanup_error'] = str(error)
    report['ended'] = time.time()
    if baseline is not None:
        try:
            report['state_preserved'] = stable(read_state()) == baseline
            report['final_state'] = stable(read_state())
        except Exception as error:
            report['state_read_error'] = str(error)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
if not report['passed']:
    raise SystemExit(1)
print('UI: VŠECHNY REGRESNÍ TESTY PROŠLY; STAV QA ZKOUŠKY ZŮSTAL ZACHOVÁN.', flush=True)
