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
| 17 nedestruktivních regresí instalátoru | PASS |
| 17 regresí kontrol úkolů | PASS |
| 5 regresí auditu původních prostředků | PASS |
| Syntaxe Python, Bash, C a workflow GitHub Actions | PASS |

Přijímací běh na čistém Debianu obsahoval 16 úspěšných kontrol. Nový hostitel byl samostatný virtuální stroj s vlastními disky, odchozím NAT a zpřístupněným KVM. Při testování se nepoužíval uživatelův existující pokus.

Debian 13, další verze Ubuntu a jejich deriváty jsou cílové platformy instalátoru. Tento záznam netvrdí, že na každé z nich proběhla samostatná kompletní instalace.

CI na GitHubu testuje zdrojové kódy a nedestruktivní regrese. Úplné testy APT, automatického hodnocení všech bodů a resetu vyžadují skutečné KVM; postup je v [TESTOVANI.md](TESTOVANI.md). Lokální logy, účty hostitele, QCOW2 obrazy a uložené pokusy se do veřejného repozitáře nepublikují.
