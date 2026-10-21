# Návod pro studenta

## Začátek nebo pokračování

Přihlas se SSH na server, kde je simulátor nainstalovaný, a zadej:

```bash
linux-exam con
```

Po připojení uvidíš prostředí `student@linux-exam`. Zkoušku spustíš:

```bash
starttest
```

První spuštění otevře zadání a začne přesných 65 minut. Ze zadání se vrať **q**, **Enter** nebo **Esc**. Zadání najdeš také v `~/zadani.txt`. Body se přičítají automaticky za skutečné výsledky příkazů; po každé úloze nemusíš spouštět ruční kontrolu.

## Kde psát a jak se vrátit

Příkazy patří do panelu **TERMINÁL – sem piš příkazy**. Dolní panel automaticky ukazuje přehled a nové body. Skóre a chybějící úkoly jsou žluté, hotové úkoly zelené.

**Podrž Ctrl a stiskni b, obě klávesy pusť, potom stiskni číslo.**

| Číslo | Okno |
|---|---|
| `1` | Příkazový řádek; vybere přímo panel pro psaní |
| `2` | Splněné a chybějící úkoly |
| `3` | Zadání |
| `4` | Nápověda |
| `5` | Výsledek |

V přehledech fungují šipky a PageUp/PageDown. Klávesy q, Enter a Esc vracejí příkazový řádek. F1–F4 jsou doplňkové zkratky v příkazovém řádku a přehledech. Uvnitř `nano`, `mc` a dalších programů používá F klávesy daný program. Při potížích s klávesnicí používej Ctrl+b a číslo.

Z příkazového řádku můžeš kdykoli napsat `statstest`, `zadanitest`, `pomoc-test` nebo `vysledektest`. `statstest` před začátkem zkoušky časovač nespustí. Pro zvětšení aktivního panelu použij Ctrl+b, potom z; stejnou zkratkou se vrátíš. Historie panelu je dostupná přes Ctrl+b, potom `[`, ukončení prohlížení je q.

## Přepnutí uživatele a zavření shellu

Pokud ses přepnul přes `su` nebo `sudo -iu` na jiného uživatele, příkaz `exit` tě vrátí do předchozího shellu. `starttest` spouštěj jako `student`. Když zavřeš i poslední studentův shell přes exit nebo Ctrl+D, rozhraní otevře nový. Body tím nezmizí a čas se neobnovuje.

Pokud je spuštěný interaktivní program, například nyancat, návrat k příkazům obvykle provede Ctrl+C. Na prázdné heslové výzvě se zadávané znaky nezobrazují; to je běžné chování Linuxu. Nezadávej heslo k hostiteli do příkazů zkoušky.

## Odpojení a nové připojení

Konzoli VM opustíš přes **Ctrl+]**; na české klávesnici může být potřeba Ctrl+AltGr+]. Tím se VM nevypne. Rozhraní tmux lze odpojit přes Ctrl+b, potom d.

Pokud zavřeš SSH okno nebo ztratíš spojení, otevři nové SSH připojení na hostitele a zadej znovu `linux-exam con`. Příkaz převezme staré konzolové připojení. Při prázdném obrazu zkus Enter. Potom případně spusť `starttest`; v otevřeném rozhraní přejdi do příkazů přes Ctrl+b, potom 1.

**Čas běží i při odpojení a vypnutí VM.** Opakované připojení nevytváří nový pokus. Po vypršení limitu můžeš stále prohlížet výsledek, další body už nepřibývají.

## Další pokus

Opusť VM a na hostiteli spusť:

```bash
linux-exam reset
```

Potvrď přesně `RESET`. Smažou se změny a postup pouze v této zkušební VM. Po `linux-exam con` a následném `starttest` začne nový pokus s 0/34 a 65 minutami. Reset používej, když opravdu chceš začít od začátku; při problému s obrazem nejdřív zkus nové připojení.
