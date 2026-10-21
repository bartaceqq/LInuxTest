#!/bin/bash
# Prvotní vytvoření výhradně nové VM; potvrzený reset obstarává samostatný nástroj.
set -euo pipefail
export LC_ALL=C
P=/opt/linux-exam-simulator
D=/var/lib/libvirt/images/linux-exam-simulator
[[ $EUID == 0 ]] || exec sudo /bin/bash "$0" "$@"
cd "$P"
for cmd in virsh qemu-img cloud-localds python3 gpgv sha256sum flock; do
    command -v "$cmd" >/dev/null || { echo "Chybí $cmd" >&2; exit 1; }
done
[[ -c /dev/kvm ]] || { echo 'KVM není dostupné. Emulace by byla výrazně pomalejší; konfigurace není potichu změněna.' >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'Je požadován hostitel x86_64.' >&2; exit 1; }
if [[ -e "$P/build/baseline-ready" ]]; then
    python3 - <<'PY'
import sys
sys.path.insert(0, '/opt/linux-exam-simulator/host')
from reset import validate
validate()
print('Připravené prostředí již existuje. Pokus se nemění; nový začne až po linux-exam reset.')
PY
    exit 0
fi
# Všechny kolize zjistíme dříve, než vytvoříme konfiguraci, zámek nebo disk.
preflight() {
    python3 - <<'PY'
from pathlib import Path
import grp, pwd, subprocess
P=Path('/opt/linux-exam-simulator');D=Path('/var/lib/libvirt/images/linux-exam-simulator');B=P/'build'
for path in (P, B):
    if not path.is_dir() or path.is_symlink() or path.resolve()!=path:
        raise SystemExit('Neplatný adresář projektu: '+str(path))
for path in (D, *D.parents):
    if path.is_symlink():raise SystemExit('Nepovolený symlink v cestě úložiště: '+str(path))
if D.exists() and (not D.is_dir() or any(D.iterdir())):
    raise SystemExit('Úložiště není prázdné; existující soubory zůstaly nedotčené: '+str(D))
allowed={'resources.json','bootstrap.lock','operations.lock'}
for path in B.iterdir():
    if path.name not in allowed or path.is_symlink() or not path.is_file():
        raise SystemExit('Nalezena rozpracovaná nebo cizí konfigurace: '+str(path))
if 'linux-essentials-exam' in subprocess.check_output(['virsh','-c','qemu:///system','list','--all','--name'],stdin=subprocess.DEVNULL,text=True).splitlines():
    raise SystemExit('VM již existuje; nic nepřepisuji ani neresetuji.')
pwd.getpwnam('libvirt-qemu');grp.getgrnam('kvm')
PY
}
preflight
exec 9>"$P/build/bootstrap.lock"
flock -n 9 || { echo 'Instalace již běží.' >&2; exit 1; }
preflight
[[ -f "$P/keys/ubuntu-cloudimage-keyring.gpg" && ! -L "$P/keys/ubuntu-cloudimage-keyring.gpg" ]] || { echo 'Chybí přibalený důvěryhodný klíč Ubuntu Cloud Images.' >&2; exit 1; }
cd "$P/downloads"
gpgv --keyring "$P/keys/ubuntu-cloudimage-keyring.gpg" SHA256SUMS.gpg SHA256SUMS
python3 - <<'PY'
from pathlib import Path
import hashlib
name='jammy-server-cloudimg-amd64.img'
rows=[line.split() for line in Path('SHA256SUMS').read_text().splitlines()]
expected=[row[0] for row in rows if len(row)==2 and row[1].lstrip('*')==name]
if len(expected)!=1:raise SystemExit('Podepsaný seznam nemá jednoznačný kontrolní součet požadovaného obrazu.')
p=Path(name)
if not p.is_file() or p.is_symlink():raise SystemExit('Chybí prostý soubor oficiálního Ubuntu obrazu.')
h=hashlib.sha256()
with p.open('rb') as stream:
    for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
if h.hexdigest()!=expected[0]:raise SystemExit('Kontrolní součet Ubuntu obrazu nesouhlasí.')
print('Podpis seznamu i SHA-256 konkrétního Ubuntu obrazu jsou v pořádku.')
PY
cd "$P"
python3 host/build.py
install -d -m 755 "$D"
install -m 644 /dev/null "$P/build/operations.lock"
qemu-img convert -f qcow2 -O qcow2 downloads/jammy-server-cloudimg-amd64.img "$D/root.qcow2"
qemu-img resize "$D/root.qcow2" 20G
qemu-img create -f qcow2 "$D/practice.qcow2" 1G
qemu-img create -f qcow2 "$D/flash.qcow2" 128M
cloud-localds --network-config=build/network-config "$D/seed.iso" build/user-data build/meta-data
for path in "$D/root.qcow2" "$D/practice.qcow2" "$D/flash.qcow2" "$D/seed.iso"; do
    chown libvirt-qemu:kvm "$path"
    chmod 640 "$path"
done
virsh -c qemu:///system define build/domain.xml </dev/null
virsh -c qemu:///system start linux-essentials-exam </dev/null
echo 'VM spuštěna. Probíhá cloud-init; log je uvnitř /var/log/linux-exam-provision.log.'
