# Skutečné ověření

Ověřeno 21. října 2026. Výsledky níže pocházejí ze spuštěných testů, nikoli pouze z kontroly syntaxe.

| Oblast | Výsledek |
|---|---|
| Čistý Debian 12, systemd, x86_64 a vnořené KVM | Instalace dokončena |
| Chybějící závislosti přes APT bez systémového upgradu | PASS |
| Stažení oficiálního Ubuntu 22.04, podpis GPG a SHA-256 | PASS |
| Cloud-init, skutečná VM, všechny výchozí podmínky a 0/34 bez spuštěného časovače | PASS |
| Příkazy a konzole pod běžným administrátorským uživatelem přes sudo | PASS |
| Opakovaná instalace a oprava chybějícího vlastního příkazu bez změny pokusu a testovacího souboru ve VM | PASS |
| Uživatelský NAT, žádné sdílené adresáře ani fyzické disky, nová default síť libvirt neaktivní bez autostartu | PASS |
| 22 kontrol skutečného rozhraní na novém Debianu: F4/F2, návrat do shellu, opravy panelů, normální i tvrdé odpojení, zachování bodů a času | PASS |
| Skutečné zápisy na cvičný disk i flashku odstraněné resetem, neměnné hashe baseline, nulové hodnocení před zahájením | PASS |
| 11 nedestruktivních regresí rychlého přepínání a automatické opravy | PASS |
| 17 nedestruktivních regresí instalátoru | PASS |
| Úplný integrační běh: 53 kontrol, všech 26 úloh a 34/34, správné váhy bodů, duplicitní hodnocení, nový přesný 3900sekundový pokus a expirace bez dalších bodů | PASS |
| 17 regresí kontrol úkolů | PASS |
| 5 regresí auditu původních prostředků | PASS |
| Syntaxe Python, Bash, C a workflow GitHub Actions | PASS |

Přijímací běh na čistém Debianu obsahoval 15 úspěšných kontrol. Následovalo 22 kontrol skutečné sériové konzole a tmux, 53 integračních kontrol skutečných Linuxových operací a samostatný test obnovy obou pomocných disků. Po všech testech zůstal testovací pokus čistý na 0/34 bez spuštěného času. Po zrychlení přepínání bylo v deseti přechodech na vnořeném KVM naměřeno 0,254 s medián a 0,459 s maximum; čas i skóre zůstaly stejné. Jde o naměřené hodnoty testovacího prostředí, nikoli zaručenou odezvu na každém počítači. Nový hostitel byl samostatný virtuální stroj s vlastními disky, odchozím NAT a zpřístupněným KVM. Při testování se nepoužíval uživatelův existující pokus.

Debian 13, další verze Ubuntu a jejich deriváty jsou cílové platformy instalátoru. Tento záznam netvrdí, že na každé z nich proběhla samostatná kompletní instalace.

CI na GitHubu testuje zdrojové kódy a nedestruktivní regrese. Úplné testy APT, automatického hodnocení všech bodů a resetu vyžadují skutečné KVM; postup je v [TESTOVANI.md](TESTOVANI.md). Lokální logy, účty hostitele, QCOW2 obrazy a uložené pokusy se do veřejného repozitáře nepublikují.
