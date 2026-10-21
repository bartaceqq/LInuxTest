# Testování a výsledky

## Kontroly bez virtuálky

V pracovní kopii s Pythonem 3.10–3.12 spusť:

```bash
python3 -m compileall -q guest host tests
python3 tests/validators-regression.py
python3 tests/audit_test.py
python3 tests/navigation_test.py
python3 tests/installer_test.py
```

Regrese validátorů mají 17 testovacích metod. Pracují pouze v dočasných adresářích a přes mocky; nepoužívají skutečné `/etc`, domovy, disky ani skóre. Ověřují kopírování stromu, obsah a časové snímky archivů, neplatné hardlinky a redundantní vlastnické ACL. Hodnotič používá moduly `crypt` a `spwd` z Pythonu Ubuntu 22.04; na novějším hostiteli nejsou potřeba pro běh instalátoru a konzole. Pro samotné tyto regrese použij uvedenou verzi Pythonu.

CI navíc kontroluje Bash syntaxi a C pomocník. Nepředstírá skutečný boot KVM na runneru. Úspěšné CI tedy nedokládá dokončenou instalaci na všech distribucích.

## Oddělená QA virtuálka

Po úspěšné instalaci vytvoř samostatnou kopii připraveného prostředí:

```bash
sudo python3 /opt/linux-exam-simulator/host/qa.py
```

Testy, které mění Linuxový stav, přijímají pouze `LINUX_EXAM_INSTANCE=qa`. Hlavní VM tím nesmí být resetovaná ani vyřešená testem. Příkazy následujícího bloku spouštěj v nainstalovaném projektu:

```bash
cd /opt/linux-exam-simulator
sudo env LINUX_EXAM_INSTANCE=qa python3 tests/ui_regression.py
LINUX_EXAM_INSTANCE=qa linux-exam reset
sudo env LINUX_EXAM_INSTANCE=qa python3 tests/integration.py
sudo env LINUX_EXAM_INSTANCE=qa python3 tests/disks.py
```

QA reset potvrď `RESET`. `ui_regression.py` vyžaduje čistý či běžící neřešený pokus; kontroluje skutečné klávesy, návraty z přehledů, obnovu shellu, odpojení, opětovné připojení a zachování časových značek. Úplný `integration.py` vyžaduje čistý QA, provede všech 26 skutečných úloh a ověří 34 bodů, chybná řešení, duplicity, reconnect, expiraci i reset. Pro test expirace změní pouze termín QA pokusu. Na konci obnoví čisté QA. `disks.py` kontroluje odstranění zápisů z obou pomocných disků a neměnnost baseline.

QA vyžaduje další úložiště a při běhu další RAM. Na menším hostiteli nejprve bezpečně zastav hlavní VM příkazem `linux-exam stop`; pokus se zachová, ale jeho čas se nezastaví. Po testu jej znovu spustíš `linux-exam con`. Příkazy Python testů používají sudo, aby fungovaly i bez členství ve skupině libvirt. Výsledky vznikají pouze lokálně v `reports/qa/`; repozitář je neobsahuje. Podrobnosti jednotlivých skriptů jsou v [tests/README.cs.md](../tests/README.cs.md).

## Audit hostitele

Před testem vytvoř snímek. Veřejné zdrojové soubory neobsahují osobní hash existujícího příkazu `virt`; zaznamená se skutečný příkaz přítomný na daném serveru, případně jeho nepřítomnost.

```bash
cd /opt/linux-exam-simulator
sudo python3 host/audit.py | sudo tee reports/host-before.json >/dev/null
```

Po testech:

```bash
sudo python3 tests/check-host.py
```

Kontrolují se původní účty a hesla pomocí hashů, členství původních uživatelů, mounty, IP adresy, směrování, původní sítě, ostatní VM, běžící služby a příkaz `virt`. Nové servisní účty a jejich členství vzniklé při instalaci distro balíčků se vypíšou odděleně; úprava původního uživatele či jeho hesla neprojde. Nově aktivní síť libvirt se vyhodnotí jako chyba, nová neaktivní definice zůstane v reportu viditelná.

Vlastní main a QA VM se vynechají pouze po shodě jména, UUID z projektového manifestu a všech vyhrazených disků. Samotné jméno VM k vynechání nestačí. Pokud nástroj již před testem nebyl dostupný, příslušná kontrola vypíše `SKIP`, ne ověřený výsledek. Snímky mohou zachytit změny provedené jinou správou serveru během testu; kontrola je sama neopravuje.

Snímky a reporty zůstávají soukromé. Nezahrnuj je do Git commitu.

## Příprava aktualizované baseline

Jde o údržbový postup pro změny hodnotiče nebo rozhraní. V čistém QA po úspěšných integračních, UI a diskových testech vytvoř `sudo env LINUX_EXAM_INSTANCE=qa python3 tests/prepared.py`. Report váže výsledek testu na UUID a SHA-256 konkrétní baseline. QA bezpečně vypni a publikuj:

```bash
sudo python3 host/publish.py publish --qa-report /opt/linux-exam-simulator/reports/qa/publish-ready.json
```

Publikace vytváří nový systémový výchozí obraz pro příští potvrzený reset. Nezastaví hlavní VM a nepřepisuje její starý backing file. Po ověření publikace lze vypnuté QA odstranit přes `sudo python3 host/publish.py --cleanup-qa`; reporty zůstanou zachované. Neprováděj tento postup jako náhradu běžného připojení nebo resetu.
