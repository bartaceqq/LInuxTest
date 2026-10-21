#!/usr/bin/env python3
"""Obnovení serial konzole bez zápisu kláves do rozpracovaných příkazů."""
import os,sys,subprocess,threading,signal,termios,fcntl
from config import VM,BOOT
from reset import validate,virsh
import guest

def start():
    with open(BOOT/'operations.lock','r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (BOOT/'reset-in-progress').exists():raise RuntimeError('Přerušený reset dokončíš příkazem linux-exam reset.')
        validate(require_baseline=False)
        status=virsh('domstate',VM)
        if status=='paused':subprocess.run(['virsh','-c','qemu:///system','resume',VM],check=True,stdin=subprocess.DEVNULL)
        elif status!='running':subprocess.run(['virsh','-c','qemu:///system','start',VM],check=True,stdin=subprocess.DEVNULL)

def request_stop():
    with open(BOOT/'operations.lock','r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        validate(require_baseline=False)
        if virsh('domstate',VM)=='shut off':print('VM je vypnutý.')
        else:subprocess.run(['virsh','-c','qemu:///system','shutdown',VM],check=True,stdin=subprocess.DEVNULL)

def prepare():
    guest.wait(60)
    c,o,e=guest.execute("python3 - <<'PREPARE'\nimport json,subprocess,time\nfrom pathlib import Path\ns=json.loads(Path('/var/lib/linux-exam/state.json').read_text())\nfor _ in range(80):\n if subprocess.run(['pgrep','-u','student','-t','ttyS0'],stdout=subprocess.DEVNULL).returncode==0:break\n time.sleep(.25)\nif s['status']!='not_started' and Path('/opt/linux-exam/session.py').exists():\n subprocess.run(['runuser','-u','student','--','python3','/opt/linux-exam/session.py','go','shell'],check=True)\nPREPARE",timeout=20)
    if c:raise RuntimeError(e or o)

def connect():
    if not sys.stdin.isatty():raise RuntimeError('Konzole vyžaduje interaktivní terminál.')
    start();print('Připojuji VM. Existující konzole se bezpečně odpojí; body zůstanou uložené.\nVe VM: starttest | statstest | pomoc-test. Odpojení konzole: Ctrl+]. Při prázdné obrazovce stiskni Enter.',flush=True)
    try:prepare()
    except (RuntimeError,TimeoutError):print('VM startuje. Pokud zatím vidíš prázdnou konzoli, stiskni Enter.',flush=True)
    old=termios.tcgetattr(sys.stdin.fileno());stop=threading.Event();resize=threading.Event();resize.set()
    def dimensions():
        try:return os.get_terminal_size(sys.stdin.fileno())
        except OSError:return os.terminal_size((80,24))
    def monitor():
        # Virsh nejprve převezme terminál, potom serveru tmux vyžádáme nový obraz.
        stop.wait(.6)
        while not stop.is_set():
            if resize.is_set():
                resize.clear();size=dimensions()
                try:
                    guest.execute(f"""stty -F /dev/ttyS0 rows {size.lines} cols {size.columns}
python3 - <<'REDRAW'
import os,signal
try:
 fd=os.open('/dev/ttyS0',os.O_RDONLY|os.O_NONBLOCK|os.O_NOCTTY)
 group=os.tcgetpgrp(fd)
 if group>1:os.killpg(group,signal.SIGWINCH)
 os.close(fd)
except OSError:pass
REDRAW
runuser -u student -- tmux refresh-client -t /dev/ttyS0 2>/dev/null || true
""",timeout=10)
                except (RuntimeError,TimeoutError):pass
            stop.wait(.2)
    previous=signal.signal(signal.SIGWINCH,lambda *_:resize.set())
    proc=subprocess.Popen(['virsh','-c','qemu:///system','console',VM,'--safe','--force'])
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:return proc.wait()
    finally:
        stop.set();signal.signal(signal.SIGWINCH,previous)
        try:termios.tcsetattr(sys.stdin.fileno(),termios.TCSANOW,old)
        except (OSError,termios.error):pass
if __name__=='__main__':
    try:
        if sys.argv[1:]==['start']:start()
        elif sys.argv[1:]==['stop']:request_stop()
        else:raise SystemExit(connect())
    except (RuntimeError,TimeoutError) as e:raise SystemExit(str(e))
