#!/usr/bin/env python3
"""Stejný barevný přehled pro statstest i automatický panel tmux."""
import argparse
import shutil
import textwrap
import time
import sys,select,termios,tty,subprocess

import state
from tasks import TASKS

YELLOW = '\033[33m'
GREEN = '\033[32m'
RESET = '\033[0m'


def remaining(s):
    if not s['deadline']:
        return 3900
    end = s.get('finished_at', time.time())
    return max(0, int(s['deadline'] - end + 0.999))


def short(s):
    seconds = remaining(s)
    score = s['score']
    filled = int(score / 34 * 15)
    bar = '█' * filled + '░' * (15 - filled)
    status = {
        'not_started': 'PŘIPRAVENO', 'running': 'BĚŽÍ',
        'expired': 'ČAS VYPRŠEL', 'finished': 'SPLNĚNO',
    }[s['status']]
    return (f'SKÓRE {score}/34 | ZBÝVÁ {seconds // 60:02}:{seconds % 60:02}'
            f' | {bar} {score * 100 // 34}% | {status}')


def paint(text, color, enabled=True):
    return color + text + RESET if enabled else text


def render(s, width=80, color=True):
    completed = s['completed']
    rows = [('LINUX ESSENTIALS — PŘEHLED ZKOUŠKY', YELLOW),
            (f'SPLNĚNÉ ÚKOLY: {len(completed)} / 26', GREEN)]
    for key, points, title in TASKS:
        if key in completed:
            rows.append((f'✓ {key:>3}. {title} (+{points} b.)', GREEN))
    if not completed:
        rows.append(('Zatím nemáš splněný žádný úkol.', YELLOW))
    missing=26-len(completed)
    noun='úkol' if missing==1 else 'úkoly' if 2<=missing<=4 else 'úkolů'
    rows.append((f'ZBÝVÁ SPLNIT: {missing} {noun}', YELLOW))
    for key, points, title in TASKS:
        if key not in completed:
            rows.append((f'□ {key:>3}. {title} (+{points} b.)', YELLOW))
    if s['status'] == 'finished':
        rows.append(('[SYSTEM] GRATULUJEME! Všech 34 bodů je tvoje.', GREEN))
    elif s['status'] == 'expired':
        rows.append(('[SYSTEM] KONEC ZKOUŠKY — čas vypršel.', YELLOW))
    if completed:
        last = max(completed.values(), key=lambda task: task['time'])
        rows.append((f'Poslední splnění: ✓ {last["title"]} (+{last["points"]} b.)', GREEN))
    rows.append(('PŘEHLED • příkazy: Ctrl+b, pak 1 | celý stav: statstest', YELLOW))
    rows.append((short(s)[:max(1, width - 1)], YELLOW))
    lines = []
    for text, tone in rows:
        for line in textwrap.wrap(text, width=max(20, width - 1)) or ['']:
            lines.append(paint(line, tone, color))
    return '\n'.join(lines)


def _watch():
    """Nový celý výpis po každém přidělení; čas se obnovuje na posledním řádku.

    Výpisy zůstávají v historii samostatného panelu. Žádné zápisy do panelu
    s příkazy ani do jeho vstupu, takže ani nano nebo top nejsou rušeny.
    """
    previous = None
    previous_timer = None
    while True:
        s = state.read()
        size = shutil.get_terminal_size((80, 24))
        signature = (tuple(s['completed']), s['status'], size)
        timer = short(s)
        if signature != previous:
            print(('\n' if previous is not None else '') + render(s, size.columns),
                  end='', flush=True)
            previous = signature
        elif timer != previous_timer:
            # Krátký časový řádek patří vždy tomuto panelu, ne shellu studenta.
            print('\r\033[2K' + paint(timer[:max(1, size.columns - 1)], YELLOW),
                  end='', flush=True)
        previous_timer = timer
        try:
            if sys.stdin.isatty() and select.select([sys.stdin],[],[],0.25)[0]:
                key=sys.stdin.read(1)
                if key in ('q','Q','\r','\n','\x1b'):
                    subprocess.run(['python3','/opt/linux-exam/session.py','go','shell'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:time.sleep(0.05)
        except KeyboardInterrupt:
            subprocess.run(['python3','/opt/linux-exam/session.py','go','shell'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def watch():
    original=None
    if sys.stdin.isatty():
        original=termios.tcgetattr(sys.stdin.fileno());tty.setcbreak(sys.stdin.fileno())
        attributes=termios.tcgetattr(sys.stdin.fileno());attributes[0]&=~(termios.IXON|termios.IXOFF);termios.tcsetattr(sys.stdin.fileno(),termios.TCSANOW,attributes)
    try:_watch()
    finally:
        if original is not None:
            try:termios.tcsetattr(sys.stdin.fileno(),termios.TCSANOW,original)
            except termios.error:pass


def main():
    parser = argparse.ArgumentParser(description='Barevné skóre a seznam úkolů zkoušky.')
    parser.add_argument('--watch', action='store_true', help='Automaticky obnovovat přehled v samostatném panelu.')
    parser.add_argument('--no-color', action='store_true', help='Vypsat přehled bez barev.')
    args = parser.parse_args()
    if args.watch:
        watch()
    else:
        print(render(state.read(), shutil.get_terminal_size((80, 24)).columns,
                     color=not args.no_color))


if __name__ == '__main__':
    main()
