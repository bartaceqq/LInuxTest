#!/usr/bin/env python3
"""Přehled s posunem i na terminálu 80 × 24."""
import curses,state
from tasks import TASKS

def main(screen):
    curses.curs_set(0);screen.timeout(1000);offset=0
    curses.start_color();curses.use_default_colors()
    curses.init_pair(1,curses.COLOR_YELLOW,-1)
    curses.init_pair(2,curses.COLOR_GREEN,-1)
    while True:
        s=state.read();h,w=screen.getmaxyx();visible=max(1,h-4)
        offset=max(0,min(offset,max(0,len(TASKS)-visible)))
        screen.erase()
        def line(y,text,tone=1):
            try:screen.addstr(y,0,text[:max(1,w-1)],curses.color_pair(tone))
            except curses.error:pass
        line(0,f'PŘEHLED ÚKOLŮ — SKÓRE {s["score"]} / 34')
        for y,(key,p,title) in enumerate(TASKS[offset:offset+visible],2):line(y,f'{"✓" if key in s["completed"] else "□"} {key:>3}. {title} (+{p})',2 if key in s['completed'] else 1)
        line(h-1,'↑↓ / PgUp PgDn: posun | F2: terminál | F4: zadání | F1: pomoc')
        screen.refresh();key=screen.getch()
        if key==curses.KEY_DOWN:offset+=1
        elif key==curses.KEY_UP:offset-=1
        elif key==curses.KEY_NPAGE:offset+=visible
        elif key==curses.KEY_PPAGE:offset-=visible
curses.wrapper(main)
