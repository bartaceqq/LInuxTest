#!/usr/bin/env python3
"""Texty a malé příkazy rozhraní; import nemá vedlejší účinky."""
import sys
import state
from progress import short,watch

HELP='''JAK ZKOUŠKU OVLÁDAT

starttest       Zahájí zkoušku nebo obnoví stejný pokus a jeho terminál.
statstest       Vypíše body, žluté chybějící a zelené splněné úkoly.
zadanitest     Otevře celé zadání.
pomoc-test     Zobrazí tuto nápovědu.
vysledektest   Zobrazí průběžný nebo konečný výsledek.

NEJSPOLEHLIVĚJŠÍ PŘEPÍNÁNÍ
Podrž Ctrl, stiskni b, obě klávesy pusť a pak stiskni číslo:
1 = terminál, 2 = úkoly, 3 = zadání, 4 = pomoc, 5 = výsledek.
Nejde o současný stisk Ctrl+b+číslo.

V zadání i přehledech tě q, Enter nebo Esc vrátí do terminálu.
Příkazy piš do panelu označeného TERMINÁL; spodní panel je přehled.
Ctrl+b, pak z zvětší aktivní panel; stejnou zkratkou jej vrátíš.
Ctrl+b, pak [ otevře historii panelu; prohlížení ukončíš q.

F1–F4 jsou jen doplněk v příkazovém řádku a přehledech.
V nano, mc, top a dalších programech patří klávesy samotnému programu.
Pokud tvůj terminál F klávesy neposílá správně, používej Ctrl+b a číslo.

UŽIVATELÉ A ZAVÍRÁNÍ
Po su aneta se vrátíš příkazem exit. Heslo studenta není potřeba.
Když zavřeš i poslední studentův shell, otevře se nový automaticky.
Ctrl+b, pak d odpojí rozhraní; starttest jej znovu připojí.
Ctrl+] odpojí konzoli VM. Z hostitele se vrátíš: linux-exam con.
Nové připojení obnoví terminál; body ani čas se nezahodí.

ČAS A NOVÝ POKUS
Limit 65 minut začne prvním starttest a běží i po odpojení.
statstest čas nespouští. Body se přidělují automaticky a jen jednou.
Změny hotového řešení již přidělené body neodeberou.
Po vypršení času další body nepřibudou.
Nový čistý pokus: na hostiteli linux-exam reset a potvrdit RESET.
Reset je jediná operace, která zahodí současný pokus a jeho změny.
'''

def result(s):
    count=len(s['completed'])
    return '\n'.join(['='*40,'KONEC ZKOUŠKY' if s['status'] in ('expired','finished') else 'PRŮBĚŽNÝ VÝSLEDEK','='*40,
      f'Výsledné skóre: {s["score"]} / 34',f'Úspěšnost: {s["score"]/34*100:.0f} %',f'Splněné úkoly: {count} / 26',f'Nesplněné úkoly: {26-count}',
      'Čas vypršel.' if s['status']=='expired' else 'Gratulujeme ke splnění všech úkolů!' if s['status']=='finished' else short(s),'='*40])

def main():
    mode=sys.argv[1] if len(sys.argv)>1 else 'tasks'
    if mode=='status':print(short(state.read()))
    elif mode=='help':print(HELP)
    elif mode=='result-text':print(result(state.read()))
    elif mode=='events':watch()
    else:
        import os
        os.execv(sys.executable,[sys.executable,'/opt/linux-exam/view.py',mode])
if __name__=='__main__':main()
