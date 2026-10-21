# Řešení potíží

## Nejde psát nebo se nezobrazuje příkazový řádek

V zadání a přehledech stiskni q, Enter nebo Esc. Jinak použij Ctrl+b, pusť obě klávesy, potom 1. Příkazy patří do horního panelu TERMINÁL. Pokud běží nyancat či jiný program, zkus Ctrl+C.

Při zaseknutém výpisu po omylem stisknutém Ctrl+S může pomoci Ctrl+Q. Prostředí zkoušky řízení toku standardně vypíná, ale některý samostatně otevřený program jej může změnit.

Pokud nic nepomáhá, odpoj konzoli Ctrl+] a na hostiteli znovu spusť `linux-exam con`. Ztracené SSH připojení řeš stejným způsobem z nového terminálu. Skóre se ukládá nezávisle na připojeném okně. Reset k obnovení konzole nepotřebuješ.

## F klávesy vkládají text nebo dělají něco jiného

Používej Ctrl+b, potom číslo. Různé Windows terminály a rozložení klávesnice posílají odlišné sekvence; není potřeba jim přizpůsobovat příkazy zkoušky. Ve spuštěných aplikacích jako `nano` a `mc` F klávesy záměrně ovládají aplikaci.

## Hostitel nemá příkaz linux-exam nebo nemá oprávnění libvirt

Ověř dokončení instalace. Výchozí příkaz je `/usr/local/bin/linux-exam`; tento adresář musí být v `PATH`. Příkaz `virt` z jiného programu se nepřepisuje.

Pro přístup k systémovému libvirt je potřeba již existující oprávnění hostitele. Vyzkoušej `sudo linux-exam status` a případně `sudo linux-exam con`. Instalátor nepřidává uživateli sudo bez hesla. Ve VM je sudo bez hesla pouze pro účet student.

## Kontrola hlásí chybějící KVM

Na hostiteli zkontroluj:

```bash
ls -l /dev/kvm
lsmod | grep kvm
```

Pokud KVM zařízení chybí, ověř virtualizaci ve firmwaru nebo podporu vnořené virtualizace u poskytovatele serveru. V prostředí WSL musí být skutečně dostupné KVM; samotná přítomnost Linuxového shellu nestačí. Instalátor nepřechází automaticky na kontejnery či emulaci.

## Instalace nebo první start nedoběhl

Na hostiteli:

```bash
linux-exam status
sudo virsh -c qemu:///system dominfo linux-essentials-exam
sudo tail -n 80 /var/log/libvirt/qemu/linux-essentials-exam.log
```

Připoj se `linux-exam con`. Uvnitř VM zobraz:

```bash
sudo cloud-init status --long
sudo tail -n 100 /var/log/linux-exam-provision.log
sudo journalctl -u linux-exam-fixtures -n 60 --no-pager
```

Příprava potřebuje funkční přístup k APT repozitářům. Po prvním startu či resetu může QEMU Guest Agent chvíli startovat; později zopakuj `linux-exam status`. Chyba podpisu image není důvodem vynechat kontrolu integrity. Ověř správný čas hostitele a zdroj obrazu.

## Body se nepřičítají

Ověř, že pokus skutečně začal přes `starttest`, neskončil čas a úloha odpovídá přesným cestám a hodnotám zadání. Hodnotič jednou přidělené body neodebírá. Příkaz `statstest` pouze čte stav; sám zadání neopravuje.

Uvnitř VM:

```bash
sudo systemctl status linux-exam-grader --no-pager
sudo journalctl -u linux-exam-grader -n 100 --no-pager
cat /var/lib/linux-exam/state.json
```

Po předchozím zahájení můžeš službu hodnotiče restartovat příkazem `sudo systemctl restart linux-exam-grader`; uložený termín se tím nezmění. Neměň ručně JSON ani čas počítače kvůli bodům. U archivu počkej na ukončení zapisujícího programu, aby mohla proběhnout kontrola úplnosti.

## Reset byl přerušen nebo se hlásí kolize

`build/reset-in-progress` blokuje spuštění neúplně obnovené VM. Když chceš zahodit pokus a reset dokončit, spusť na hostiteli znovu `linux-exam reset` a potvrď `RESET`.

Při kolizi existující VM, příkazu nebo diskového souboru nejprve zjisti jeho vlastníka a účel. Nemaž kvůli instalaci obecné adresáře libvirt, jeho pooly, cizí VM ani hostitelské oddíly. Výchozí obraz QCOW2 může být používán aktivním overlayem; jeho přepsání nebo smazání může tento overlay poškodit.

## Před hlášením chyby

Uveď distribuci hostitele, verzi repozitáře, výstup `linux-exam status`, použitý terminál a stručný postup vyvolání problému. Zkontroluj soukromé údaje v logu před jeho zveřejněním. Do veřejného issue nepřikládej virtuální disky, skutečný state.json, cloud-init user-data, databáze hesel ani celý soukromý audit hostitele.
