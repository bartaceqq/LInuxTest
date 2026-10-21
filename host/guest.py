#!/usr/bin/env python3
"""Správa přes lokální kanál QEMU Guest Agent, bez síťového SSH portu."""
import subprocess,json,base64,time,sys,argparse
from config import VM
def agent(payload):
    p=subprocess.run(['virsh','-c','qemu:///system','qemu-agent-command',VM,json.dumps(payload),'--timeout','15'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    r=json.loads(p.stdout)
    if 'error' in r:raise RuntimeError(str(r['error']))
    return r['return']
def execute(command,timeout=300):
    r=agent({'execute':'guest-exec','arguments':{'path':'/bin/bash','arg':['-c',command],'capture-output':True}})
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        s=agent({'execute':'guest-exec-status','arguments':{'pid':r['pid']}})
        if s['exited']:
            return s.get('exitcode',128+s.get('signal',0)),base64.b64decode(s.get('out-data','')).decode(errors='replace'),base64.b64decode(s.get('err-data','')).decode(errors='replace')
        time.sleep(.2)
    raise TimeoutError('Vypršel čas příkazu ve VM')
def wait(timeout=180):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        try:agent({'execute':'guest-ping'});return
        except RuntimeError:time.sleep(1)
    raise TimeoutError('Guest Agent ve VM neodpovídá')
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Lokální administrační kanál cvičného VM');p.add_argument('command');p.add_argument('--timeout',type=int,default=300);a=p.parse_args()
    c,o,e=execute(a.command,a.timeout);sys.stdout.write(o);sys.stderr.write(e);sys.exit(c)
