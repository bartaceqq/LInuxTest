# Ověřování

`initial.py` běží uvnitř VM jako root. Kontroluje systém, výchozí soubory, účty, balíčky, skutečné procesy, disky, síť a 26 nesplněných kontrol.

Testy, které mění prostředí, vyžadují výslovně `LINUX_EXAM_INSTANCE=qa` a odmítnou hlavní VM. Nejdřív vytvoř QA příkazem `sudo python3 /opt/linux-exam-simulator/host/qa.py`. Příkazy spouštěj z adresáře projektu:

```bash
sudo env LINUX_EXAM_INSTANCE=qa python3 tests/ui_regression.py
LINUX_EXAM_INSTANCE=qa linux-exam reset
sudo env LINUX_EXAM_INSTANCE=qa python3 tests/integration.py
sudo env LINUX_EXAM_INSTANCE=qa python3 tests/disks.py
```

Reset QA potvrď slovem `RESET`. `ui_regression.py` vyžaduje čistý nebo běžící neřešený pokus. Ověřuje skutečné klávesy F2/F4 v aplikaci i F4→F2 v rozhraní, návrat ze všech přehledů, exit/Ctrl+D, obnovu chybějících panelů a oken, normální i tvrdé odpojení, různou velikost terminálu, barvy a neměnné body/časové značky. QA pokus nerozřeší a jeho čas neobnovuje.

`integration.py` vyžaduje čistý QA. Provede reálné operace všech 26 kontrol, ověří 34 bodů, nesprávné vstupy, duplicity, časovač a reconnect. Pouze pro test expirace zkrátí termín QA pokusu. Na konci obnoví čisté QA, pokud sám začal testovací pokus. `disks.py` ověří reset zápisů na obou pomocných discích, neměnnost baseline a nulové hodnocení před zahájením.

`validators-regression.py` ověřuje 17 kontrolních scénářů v dočasných adresářích bez zásahů do zkoušky. Spouští se z pracovní kopie na Pythonu 3.10–3.12. `installer_test.py` ověřuje předběžnou kontrolu a balení bez instalace skutečného hostitele.

`check-host.py` vyžaduje sudo kvůli čtení hashů databází účtů. Před testem vytvoř lokální snímek `sudo python3 host/audit.py | sudo tee reports/host-before.json >/dev/null`, po něm spusť `sudo python3 tests/check-host.py`. Porovnává původní účty, mounty, síť, původní VM, služby a skutečný původní příkaz `virt`, pokud existuje. Vlastní main a QA VM vynechá až při shodě projektového UUID a vyhrazených disků; samotné jméno nestačí. Nové servisní účty hlásí odděleně. Nedostupné vstupní kontroly označí SKIP.

Výsledky skutečných běhů vznikají lokálně v `reports/qa/`; soukromé snímky ani reporty nejsou součástí repozitáře. Testovací VM se po finálním ověření může bezpečně odstranit nástrojem `host/publish.py --cleanup-qa`; nástroj vyžaduje vypnuté QA a ověří vazby všech VM. Další postupy jsou v [docs/TESTOVANI.md](../docs/TESTOVANI.md).
