#!/bin/bash
# Stažený zdroj se pouze čte; instalace používá vlastní adresář v /opt.
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
check_only=0
show_help=0
for arg in "$@"; do
    case "$arg" in --check) check_only=1;; --yes) :;; --help|-h) show_help=1;; *) echo "Neznámý přepínač: $arg" >&2; exit 2;; esac
done
if [[ $show_help == 1 ]]; then cat <<'HELP'
Instalace Linux Essentials pro Debian / Ubuntu (x86_64, systemd, KVM).
sudo ./install.sh          Kontrola, potvrzení závislostí a instalace.
sudo ./install.sh --yes    Stejná instalace bez potvrzovací otázky.
./install.sh --check       Pouze kontrola, nic neinstaluje ani nepřepisuje.
HELP
exit 0
fi
if ! command -v python3 >/dev/null; then
    if [[ $check_only == 1 ]]; then echo 'Chybí python3. Kontrola nemůže pokračovat.' >&2; exit 1; fi
    [[ $(uname -m) == x86_64 && -c /dev/kvm && -d /run/systemd/system ]] || { echo 'Vyžadováno x86_64, systemd a /dev/kvm.' >&2; exit 1; }
    [[ $EUID == 0 ]] || exec sudo -- /bin/bash "$source_dir/install.sh" "$@"
    command -v apt-get >/dev/null || { echo 'Vyžadován Debian nebo Ubuntu s APT.' >&2; exit 1; }
    apt-get update
    apt-get install --no-install-recommends --no-upgrade --no-remove -y python3
fi
if [[ $EUID != 0 && $check_only != 1 ]]; then exec sudo -- /bin/bash "$source_dir/install.sh" "$@"; fi
exec python3 "$source_dir/host/install.py" "$@"
