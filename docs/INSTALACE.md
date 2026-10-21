# Instalace a podmínky

## Předpoklady

Hostitel musí používat x86_64, systemd a zpřístupněné `/dev/kvm`. U fyzického stroje musí být virtualizace povolená ve firmwaru. U již virtualizovaného serveru musí poskytovatel zpřístupnit vnořenou virtualizaci. Pokud KVM není dostupné, instalátor skončí s vysvětlením; nezamění VM za kontejner ani potichu nezapne pomalou softwarovou emulaci.

Cílové distribuce instalátoru:

| Hostitel | Rozsah podpory |
|---|---|
| Debian 12 a 13 | x86_64, systemd, oficiální APT repozitáře |
| Ubuntu 22.04, 24.04 a 26.04 | x86_64, systemd, oficiální APT repozitáře |
| Kompatibilní deriváty, např. Linux Mint | Možné při odpovídajícím základu Debian/Ubuntu; ověří je předběžná kontrola, neplatí záruka pro všechny deriváty |
| ARM, nesystémová kontejnerová prostředí, WSL bez KVM | Nepodporováno |

Hostitelská distribuce nemění systém uvnitř VM: VM používá **Ubuntu Server 22.04 LTS** z oficiálního cloud image. Instalátor ověřuje podpis seznamu SHA-256 přibaleným veřejným klíčem Ubuntu Cloud Images a kontrolní součet obrazu. Přibalený klíč není soukromým klíčem ani povolením přístupu na server.

Pro výchozí VM počítej se 2 vCPU a 2 GiB RAM navíc k prostředkům ostatních služeb. Virtuální kapacity disků jsou 20 GiB + 1 GiB + 128 MiB. Souborové QCOW2 obrazy rostou podle skutečných zápisů; stahování, samostatné baseline a QA kopie vyžadují další volné místo. Doporučeno je alespoň 4 GiB RAM a 25 GiB volného místa. Minimální kontrola vyžaduje 12 GiB volného místa; při oddělených filesystémech alespoň 2 GiB pro projekt a stažený obraz v /opt a 10 GiB pro disky v /var. Instalátor kontroluje skutečné filesystémy a aktuální volnou paměť; může zvolit 1536 MiB RAM nebo 1 vCPU místo výchozích hodnot. Vzdálená instalace potřebuje odchozí HTTPS pro obraz Ubuntu, zdroj nyancat a balíčky; také guest potřebuje APT přístup přes NAT.

## Postup

```bash
git clone https://github.com/bartaceqq/LInuxTest.git
cd LInuxTest
sudo ./install.sh --check
sudo ./install.sh
```

`--check` pouze zjišťuje dostupnost prostředků, nástrojů a kolize. Běžná instalace si vyžádá potvrzení instalace chybějících závislostí. Pro předem schválené automatizované nasazení použij `sudo ./install.sh --yes`.

Instalace může několik minut stahovat balíčky a připravovat cloud-init. Čas zkoušky v tuto chvíli neběží. Po dokončení:

```bash
linux-exam status
linux-exam con
```

Uvnitř VM zadej `starttest`. Nepoužívej na hostiteli příkazy ze zadání zkoušky; například `/dev/sda1` z úlohy existuje na vyhrazeném virtuálním disku uvnitř VM.

## Rozsah změn hostitele

Projekt se instaluje do `/opt/linux-exam-simulator`, obrazy do `/var/lib/libvirt/images/linux-exam-simulator` a příkaz do `/usr/local/bin/linux-exam`. Instaluje pouze chybějící závislosti. Nespouští systémový upgrade ani neodstraňuje nesouvisející balíčky. Needituje sudoers a přímo nevytváří hostitelského studenta ani nepřidává přihlášeného uživatele do skupin.

APT spouští standardní skripty distribučních balíčků. Ty mohou vytvořit například servisní účet QEMU, upravit servisní skupiny a spustit libvirt. Na některých distribucích mají instalační skripty libvirt i vlastní správu členství ve skupinách. Předběžná kontrola tento dopad balíčků nenahrazuje. Existující závislosti se nepřeinstalovávají jen kvůli simulátoru.

VM používá uživatelský NAT QEMU a nevyžaduje hostitelský bridge, IP forwarding, přesměrování příchozích portů ani změnu firewallu. Pokud při úplně nové instalaci libvirt vytvoří balíček vlastní výchozí NAT síť, instalátor vypne pouze tuto novou výchozí síť a její autostart. Sítě a VM existující před instalací se kvůli tomu nemění.

Při obsazeném názvu VM, cizím příkazu `linux-exam` nebo neznámých souborech v cílové cestě instalátor skončí. Neodstraňuj nalezené prostředky naslepo. Opakované spuštění připravenou zkoušku neresetuje; nový pokus vytváří až potvrzený `linux-exam reset`.

## Oprávnění a přístup

Hostitelské operace vyžadují stávající oprávnění libvirt a případně `sudo`. Instalátor nevytváří hostitelskou výjimku pro sudo bez hesla. Pokud účet nemá přístup k systémovému libvirt, použij na hostiteli například `sudo linux-exam con`; standardní `sudo` může požádat o tvoje hostitelské heslo.

Uvnitř VM je účet `student` přihlašovaný automaticky přes sériovou konzoli a má sudo bez hesla. Guest SSH a veřejné příchozí porty nejsou nutné. Neexistuje sdílený zapisovatelný adresář hostitele ani předání jeho disků.

## Aktualizace a odstranění

Instalátor rozlišuje instalaci a opakování pokusu; není obecným nástrojem pro aktualizaci rozpracované VM. Před změnou hodnotiče nebo baseline si uschovej výsledek a použij QA postup. Staré baseline se nesmějí přepsat či smazat, dokud na ně odkazuje některý overlay. Samotné `git pull` v pracovní kopii nepřepíše běžící guest.

Projekt zatím nemá automatický odinstalační příkaz. Ruční odstranění vyžaduje ověření UUID, diskových vazeb a toho, že žádné jiné VM soubory nepoužívají. Kvůli odinstalaci simulátoru nemaž libvirt storage pool, hostitelské oddíly ani obecné adresáře libvirt.
