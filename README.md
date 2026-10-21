# LInuxTest — Linux Essentials na skutečném Ubuntu Serveru

Praktická zkouška v izolované KVM virtuálce: **65 minut, 26 automatických kontrol a přesně 34 bodů**. Příkazy spouštíš ve skutečném Ubuntu Serveru 22.04 LTS. Body přibývají automaticky, postup se ukládá a nový pokus obnoví připravené virtuální disky.

## Instalace na server

Na serveru musí být Linux se systemd, architektura x86_64 a dostupné KVM. Pokud chybí `git`, nejprve jej nainstaluj balíčkovým správcem serveru.

```bash
git clone https://github.com/bartaceqq/LInuxTest.git
cd LInuxTest
sudo ./install.sh
```

Instalátor zkontroluje hostitele, vypíše prostředky a vyžádá potvrzení instalace chybějících závislostí. Stáhne oficiální Ubuntu cloud image, ověří podepsaný seznam SHA-256 a připraví VM přes cloud-init. Projekt uloží do `/opt/linux-exam-simulator`; zkouška se tím ještě nespustí.

Pouze kontrola předpokladů, bez instalace a změn systému:

```bash
sudo ./install.sh --check
```

Pro automatizovanou instalaci použij `sudo ./install.sh --yes`. Tento přepínač potvrzuje pouze instalační závislosti; reset pokusu nadále vyžaduje vlastní potvrzení.

Cílové hostitelské platformy jsou **Debian 12/13 a Ubuntu 22.04/24.04/26.04** na x86_64. Kompatibilní deriváty, například Linux Mint, mohou fungovat při odpovídajících balíčcích a systemd; všechny deriváty nejsou zaručené. ARM a prostředí bez `/dev/kvm`, včetně WSL bez zpřístupněného KVM, podporované nejsou. Podrobnosti jsou v [instalačním návodu](docs/INSTALACE.md).

## Spuštění a ovládání

Na hostitelském serveru:

```bash
linux-exam con
```

Uvnitř virtuálky:

```bash
starttest
```

Student se přihlásí automaticky a `sudo` uvnitř VM nevyžaduje heslo. První `starttest` spustí časovač a otevře zadání; další připojí stejný pokus. Do příkazového řádku se ze zadání vrátíš **q**, **Enter** nebo **Esc**.

| Příkaz uvnitř VM | Význam |
|---|---|
| `starttest` | Začít nebo pokračovat ve stejném pokusu |
| `statstest` | Žluté skóre a chybějící úkoly, zelené splněné úkoly |
| `zadanitest` | Celé zadání |
| `pomoc-test` | Nápověda a ovládání |
| `vysledektest` | Průběžný nebo konečný výsledek |

Po splnění úkolu se barevný přehled automaticky vypíše ve spodním panelu. Příkazy zadávej do horního panelu **TERMINÁL**. Přepínání funguje přes **Ctrl+b, pustit obě klávesy, potom číslo**: `1` terminál, `2` úkoly, `3` zadání, `4` nápověda, `5` výsledek. Klávesy F1–F4 jsou doplňkové; v `nano`, `mc` a dalších aplikacích zůstává jejich vlastní ovládání.

Z konzole VM se odpojíš **Ctrl+]**. Po opětovném přihlášení na server zadej znovu `linux-exam con` a případně `starttest`. Skóre zůstává uložené; čas běží i při odpojení nebo vypnuté VM. [Podrobný návod pro studenta](docs/STUDENT.md) řeší také `su`, zavření shellu a prázdnou obrazovku.

## Nový pokus

Na hostiteli spusť:

```bash
linux-exam reset
```

Potvrď slovem `RESET`. Obnoví se systém, cvičný disk i flashka včetně uživatelů, balíčků a skóre. Potom použij `linux-exam con` a `starttest`; nový limit začne až spuštěním zkoušky. Reset zahodí všechny změny uvnitř této VM.

Další hostitelské příkazy: `linux-exam status`, `linux-exam start`, `linux-exam stop` a `linux-exam help`. Příkaz funguje z libovolného adresáře v Bash i Zsh, pokud je `/usr/local/bin` v `PATH`.

## Co se vytvoří

Výchozí VM `linux-essentials-exam` používá 2 vCPU, 2048 MiB RAM a souborové disky QCOW2: systém 20 GiB, cvičný disk 1 GiB a flashku 128 MiB. Připravené baseline a zapisovatelné overlaye umožňují rychlé opakování. Skutečné prostředky vypíše instalátor.

Síť používá uživatelský NAT QEMU. VM nemá hostitelské disky, zapisovatelné sdílené adresáře ani veřejné příchozí porty. Instalátor nepřepisuje existující příkaz `virt`, nesouvisející VM ani obsazené diskové cesty. Neprovádí upgrade hostitele a sám nepřidává uživatele do skupin ani neupravuje sudoers. Instalace chybějících distro balíčků však spouští jejich standardní instalační skripty, které mohou vytvořit servisní účty a spustit služby libvirt. Nově vytvořená výchozí síť při úplně nové instalaci libvirt se deaktivuje; již existující sítě se nemění. [Podrobnosti a hranice instalace](docs/INSTALACE.md).

Hodnotič běží jako systemd služba uvnitř VM, přiděluje každý bod jen jednou a atomicky ukládá výsledek. Student má ve VM sudo a může hodnotič úmyslně pozměnit; prostředí slouží k procvičování. U archivu se kontroluje obsah a vlastník, nikoli identita procesu `tar`.

## Ověřování a údržba

Základní regrese validátorů používají pouze dočasné adresáře:

```bash
python3 tests/validators-regression.py
```

Použij Python 3.10–3.12; vlastní hodnotič běží na Pythonu z Ubuntu 22.04 uvnitř VM. CI kontroluje Python, Bash, C pomocník, tyto regrese a balení instalátoru. CI bez KVM neověřuje boot celé VM. Reálné integrační testy patří do samostatné QA instance; hlavní pokus testovací skripty odmítají změnit. [Postup testování](docs/TESTOVANI.md).

Ověřena byla také kompletní instalace na čistém **Debianu 12 s KVM**, včetně stažení a ověření Ubuntu, skutečné konzole, nulového počátečního skóre a opakování instalátoru bez ztráty dat. Ostatní uvedené distribuce jsou cílové platformy; samostatný úplný test každé z nich se netvrdí. [Výsledky ověření](docs/OVERENI.md).

Log hodnotiče uvnitř VM:

```bash
sudo journalctl -u linux-exam-grader -n 80 --no-pager
```

[Řešení potíží](docs/POTIZE.md) · [Licence a součásti třetích stran](docs/LICENCE.md) · [MIT licence zdrojového kódu](LICENSE)
