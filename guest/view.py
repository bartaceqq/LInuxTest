#!/usr/bin/env python3
"""Čitelné přehledy: q/Enter/Esc vždy vrací skutečný příkazový řádek."""
import curses,sys,subprocess,time,termios
from pathlib import Path
import state
from progress import render,short
from ui import HELP,result
ROLE=sys.argv[1]
TITLES={'assignment':'ZADÁNÍ','tasks':'ÚKOLY A BODY','help':'NÁPOVĚDA','result':'VÝSLEDEK'}
FKEYS={curses.KEY_F1:'help',curses.KEY_F2:'shell',curses.KEY_F3:'tasks',curses.KEY_F4:'assignment'}

def navigate(role):subprocess.run(['python3','/opt/linux-exam/session.py','go',role],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def content():
    s=state.read()
    if ROLE=='assignment':return Path('/home/student/zadani.txt').read_text().splitlines()
    if ROLE=='tasks':return render(s,color=False).splitlines()
    if ROLE=='help':return HELP.splitlines()
    return result(s).splitlines()
def main(screen):
    curses.curs_set(0);screen.timeout(500);screen.keypad(True)
    attrs=termios.tcgetattr(sys.stdin.fileno());attrs[0]&=~(termios.IXON|termios.IXOFF);termios.tcsetattr(sys.stdin.fileno(),termios.TCSANOW,attrs)
    curses.start_color();curses.use_default_colors()
    for index,color in [(1,curses.COLOR_YELLOW),(2,curses.COLOR_GREEN),(3,curses.COLOR_CYAN)]:curses.init_pair(index,color,-1)
    offset=0
    while True:
        h,w=screen.getmaxyx();lines=content();visible=max(1,h-4);offset=max(0,min(offset,max(0,len(lines)-visible)))
        screen.erase()
        def put(y,text,tone=0):
            try:screen.addstr(y,0,text[:max(1,w-1)],curses.color_pair(tone))
            except curses.error:pass
        put(0,TITLES[ROLE]+' — q / Enter / Esc = zpět do příkazového řádku',3)
        put(1,short(state.read()),1)
        for index,line in enumerate(lines[offset:offset+visible],2):
            tone=2 if line.startswith(('✓','SPLNĚNÉ','[SYSTEM] GRATULUJEME')) else 1 if ROLE=='tasks' else 0
            put(index,line,tone)
        put(h-1,f'Řádky {offset+1}–{min(len(lines),offset+visible)}/{len(lines)} | ↑↓ PgUp PgDn | Ctrl+b, 1 = terminál',3)
        screen.refresh()
        try:key=screen.getch()
        except KeyboardInterrupt:navigate('shell');continue
        if key==27:
            # Některé Windows terminály posílají pro F klávesy CSI místo SS3.
            screen.timeout(80);rest=''
            for _ in range(10):
                k=screen.getch()
                if k<0:break
                if k<256:rest+=chr(k)
                if rest.endswith('~') or len(rest)==2 and rest.startswith('O'):break
            screen.timeout(500)
            role={'[11~':'help','[12~':'shell','[13~':'tasks','[14~':'assignment','OP':'help','OQ':'shell','OR':'tasks','OS':'assignment'}.get(rest)
            if role:navigate(role)
            elif not rest:navigate('shell')
        elif key in (ord('q'),ord('Q'),10,13):navigate('shell')
        elif key in FKEYS:navigate(FKEYS[key])
        elif key in (curses.KEY_DOWN,ord('j')):offset+=1
        elif key in (curses.KEY_UP,ord('k')):offset-=1
        elif key in (curses.KEY_NPAGE,ord(' ')):offset+=visible
        elif key==curses.KEY_PPAGE:offset-=visible
        elif key==curses.KEY_HOME:offset=0
        elif key==curses.KEY_END:offset=len(lines)
if __name__=='__main__':curses.wrapper(main)
