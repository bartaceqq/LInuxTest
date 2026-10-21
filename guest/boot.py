#!/usr/bin/env python3
"""Příprava živých cvičných procesů při bootu; bez automatického restartu."""
import subprocess,json,time
from pathlib import Path
Path('/run/linux-exam').mkdir(mode=0o755,exist_ok=True)
processes={}
for name in ('nginx','apache'):
    command=['/usr/sbin/nginx','-c','/opt/linux-exam/nginx.conf','-g','daemon off; master_process off;'] if name=='nginx' else ['/opt/linux-exam/process','apache']
    p=subprocess.Popen(command,start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(.05)
    ticks=Path(f'/proc/{p.pid}/stat').read_text().rsplit(')',1)[1].split()[19]
    processes[name]=dict(pid=p.pid,ticks=ticks)
Path('/run/linux-exam/processes.json').write_text(json.dumps(processes))
