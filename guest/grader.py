#!/usr/bin/env python3
import time,logging,sys,os,subprocess,fcntl
from pathlib import Path
import state,tasks
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')

def tick():
    with state.locked():
        s=state.read()
        if s['status']!='running':return
        if time.time()>=s['deadline']:
            s['status']='expired';state.event(s,'[SYSTEM] KONEC ZKOUŠKY — čas vypršel.');state.write(s);return
        for task,points,title in tasks.TASKS:
            if task in s['completed']:continue
            try:ok=tasks.validate(task)
            except (FileNotFoundError,KeyError,PermissionError,ValueError,os.error):ok=False
            except Exception:
                logging.exception('Chyba kontroly úkolu %s',task);ok=False
            # Kontrola mohla trvat déle; žádné body po termínu.
            now=time.time()
            if now>=s['deadline']:
                s['status']='expired';state.event(s,'[SYSTEM] KONEC ZKOUŠKY — čas vypršel.');state.write(s);break
            if ok:
                s['completed'][task]=dict(points=points,time=now,title=title)
                s['score']=sum(c['points'] for c in s['completed'].values())
                state.event(s,f'[SYSTEM] ÚKOL SPLNĚN! ✓ {title}  +{points} b.  SKÓRE: {s["score"]} / 34')
                if s['score']==34:
                    s['status']='finished';s['finished_at']=now
                    state.event(s,'[SYSTEM] GRATULUJEME! Všech 26 kontrol splněno, získáváte 34 / 34 bodů.')
                state.write(s);logging.info('Úkol %s +%s, skóre %s/34',task,points,s['score'])

def main():
    mode=sys.argv[1] if len(sys.argv)>1 else 'monitor'
    if mode=='start':
        state.start();Path('/var/lib/linux-exam/started').touch(mode=0o600);subprocess.run(['systemctl','start','linux-exam-grader.service'],check=True)
        print('Zkouška připravena; čas a skóre se ukládají automaticky.');return
    if mode=='status':print(__import__('json').dumps(state.read(),ensure_ascii=False));return
    if mode!='monitor':raise SystemExit('Neznámý příkaz.')
    Path('/run/linux-exam').mkdir(exist_ok=True)
    with open('/run/linux-exam/grader.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            start=time.monotonic();tick();time.sleep(max(0.05,1-(time.monotonic()-start)))
if __name__=='__main__':main()
