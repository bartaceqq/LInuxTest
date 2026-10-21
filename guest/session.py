#!/usr/bin/env python3
"""Obnovitelné rozhraní; operace zde nikdy nezahajují ani neresetují zkoušku."""
import argparse,fcntl,os,shlex,subprocess
from pathlib import Path
SESSION='praktikum';ROOT='/opt/linux-exam';VERSION='4'
ROLES={'shell':(1,'Terminál'),'tasks':(2,'Úkoly'),'assignment':(3,'Zadání'),'help':(4,'Pomoc'),'result':(5,'Výsledek')}

def tm(*args,check=True):
    p=subprocess.run(['tmux',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if check and p.returncode:raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()
def panes(window):
    text=tm('list-panes','-t',window,'-F','#{pane_id}\t#{@linux_exam_role}\t#{pane_dead}\t#{pane_start_command}\t#{@linux_exam_ui_version}',check=False)
    rows=[(line.split('\t',4)+['']*5)[:5] for line in text.splitlines() if line]
    for row in rows:
        try:row[3]=' '.join(shlex.split(row[3]))
        except ValueError:pass
    return rows
def tag(pane,role):
    tm('set-option','-p','-t',pane,'@linux_exam_role',role)
    tm('set-option','-p','-t',pane,'@linux_exam_ui_version',VERSION)
def window_exists(index):
    return tm('list-windows','-t',SESSION,'-F','#{window_index}',check=False).splitlines().count(str(index))>0
def ensure_shell():
    target=SESSION+':1'
    if not window_exists(1):tm('new-window','-d','-t',target,'-n','Terminál','-c','/home/student','bash '+ROOT+'/shell.sh')
    tm('set-window-option','-t',target,'remain-on-exit','on')
    tm('set-window-option','-t',target,'pane-base-index','1')
    rows=panes(target);shell=None;progress=None
    for row in rows:
        pane,role,dead,start,version=row
        if role=='shell' or not role and ('/bin/bash'==start or start.startswith('bash '+ROOT+'/shell.sh')):
            shell=pane
            if dead=='1':tm('respawn-pane','-k','-t',pane,'-c','/home/student','bash '+ROOT+'/shell.sh')
            tag(pane,'shell')
        elif role=='progress' or not role and ('statstest' in start or 'ui.py events' in start):
            progress=pane
            if dead=='1' or version!=VERSION:tm('respawn-pane','-k','-t',pane,'statstest --watch')
            tag(pane,'progress')
    if not shell:
        # Zachováme živé programy neoznačeného staršího shellu (nano, su, make).
        unknown=[row for row in rows if row[1] not in ('progress','shell') and 'statstest' not in row[3] and 'ui.py events' not in row[3]]
        if unknown:
            shell=unknown[0][0]
            if unknown[0][2]=='1':tm('respawn-pane','-k','-t',shell,'-c','/home/student','bash '+ROOT+'/shell.sh')
        else:shell=tm('split-window','-b','-v','-P','-F','#{pane_id}','-t',target,'-c','/home/student','bash '+ROOT+'/shell.sh')
        tag(shell,'shell')
        if progress:tm('resize-pane','-t',progress,'-y','5',check=False)
    if not progress:
        progress=tm('split-window','-d','-v','-l','5','-P','-F','#{pane_id}','-t',shell,'statstest --watch');tag(progress,'progress')
    tm('set-window-option','-t',target,'pane-border-status','top')
    tm('set-window-option','-t',target,'pane-border-format','#{?#{==:#{@linux_exam_role},shell},TERMINÁL – sem piš příkazy,PŘEHLED – příkazy: Ctrl+b pak 1}')
    tm('set-window-option','-t',target,'pane-active-border-style','fg=green')
    tm('set-window-option','-t',target,'pane-border-style','fg=colour244')
    # Nezmenšovat okno nano při obyčejném přepnutí; velikost upraví jen velké přesuny.
    return shell

def ensure_view(role):
    index,title=ROLES[role];target=f'{SESSION}:{index}';command=f'python3 {ROOT}/view.py {role}'
    if window_exists(index):
        rows=panes(target)
        legacy=('ui.py help','ui.py result','list-tasks.py','less -R /home/student/zadani.txt')
        # Živý neočekávaný program nezabijeme. Zachová se v dalším okně.
        if any(row[2]!='1' and row[3]!=command and not any(old in row[3] for old in legacy) for row in rows):
            used={int(n) for n in tm('list-windows','-t',SESSION,'-F','#{window_index}').splitlines()}
            free=6
            while free in used:free+=1
            tm('move-window','-s',target,'-t',f'{SESSION}:{free}')
    if not window_exists(index):tm('new-window','-d','-t',target,'-n',title,command)
    for pane,oldrole,dead,start,version in panes(target):
        if dead=='1' or start!=command or version!=VERSION:tm('respawn-pane','-k','-t',pane,command)
        tag(pane,role)
    tm('set-option','-w','-t',target,'@linux_exam_role',role)
    tm('set-window-option','-t',target,'remain-on-exit','on')

def configure():
    tm('set-option','-t',SESSION,'base-index','1')
    tm('set-option','-t',SESSION,'status','2')
    tm('set-option','-t',SESSION,'status-interval','1')
    tm('set-option','-t',SESSION,'status-style','bg=colour24,fg=white')
    tm('set-option','-t',SESSION,'status-left','')
    tm('set-option','-t',SESSION,'status-right','')
    tm('set-option','-t',SESSION,'status-format[0]','#[fg=yellow]#(python3 /opt/linux-exam/ui.py status)')
    tm('set-option','-t',SESSION,'status-format[1]','#[fg=white]Ctrl+b, pak: 1 příkazy | 2 úkoly | 3 zadání | 4 pomoc | 5 výsledek')
    tm('set-option','-t',SESSION,'history-limit','20000')
    tm('set-option','-t',SESSION,'mouse','off')
    # Ovládání aplikací musí zůstat aplikacím. Zkratky z první verze odstraníme.
    for key in ('F1','F2','F3','F4'):tm('unbind-key','-n',key,check=False)
    for role,(index,_) in ROLES.items():tm('bind-key','-T','prefix',str(index),'run-shell','-b',f'python3 {ROOT}/session.py go {role}')
    for hook in ('pane-died','after-kill-pane','window-unlinked'):
        tm('set-hook','-t',SESSION,hook,'run-shell -b "python3 /opt/linux-exam/session.py repair"')
    tm('set-option','-s','escape-time','100')

def ensure():
    if subprocess.run(['tmux','has-session','-t',SESSION],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        tm('-f',ROOT+'/tmux.conf','new-session','-d','-s',SESSION,'-n','Terminál','-c','/home/student','bash '+ROOT+'/shell.sh')
        indices=tm('list-windows','-t',SESSION,'-F','#{window_index}').splitlines()
        if indices==['0']:tm('move-window','-s',SESSION+':0','-t',SESSION+':1')
    configure();shell=ensure_shell()
    for role in ('tasks','assignment','help','result'):ensure_view(role)
    return shell

def main():
    p=argparse.ArgumentParser(description='Obnovení a přepínání rozhraní zkoušky.')
    p.add_argument('command',choices=['ensure','repair','go']);p.add_argument('role',nargs='?',choices=ROLES,default='shell');a=p.parse_args()
    with open(Path.home()/'.linux-exam-ui.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        before=tm('display-message','-p','-t',SESSION,'#{pane_id}',check=False)
        before_window=tm('display-message','-p','-t',SESSION,'#{window_id}',check=False)
        had_shell=any(row[1]=='shell' and row[2]=='0' for row in panes(SESSION+':1'))
        shell=ensure()
        if a.command=='repair':
            target=before if had_shell and before and tm('display-message','-p','-t',before,'#{pane_dead}',check=False)=='0' else shell
            tm('select-window','-t',before_window if target==before and before_window else SESSION+':1',check=False)
            tm('select-pane','-t',target,check=False)
        if a.command!='repair':
            tm('select-window','-t',f'{SESSION}:{ROLES[a.role][0]}')
            if a.role=='shell':tm('select-pane','-t',shell)
            tm('refresh-client',check=False)
if __name__=='__main__':
    try:main()
    except (RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('Rozhraní se nepodařilo obnovit: '+str(e))
