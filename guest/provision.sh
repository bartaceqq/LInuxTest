#!/bin/bash
# Tento soubor je určen VÝHRADNĚ pro cloud-init uvnitř VM.
set -euo pipefail
[[ $(hostname) == linux-exam ]] && [[ -b /dev/vda ]] && [[ -b /dev/sda ]] || { echo 'Odmítám přípravu mimo cvičný VM.'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx-light tmux nano curl build-essential python3 acl parted qemu-guest-agent locales less procps iproute2 psmisc tar gzip util-linux
systemctl disable --now nginx.service 2>/dev/null || true
systemctl mask nginx.service
locale-gen cs_CZ.UTF-8 en_US.UTF-8
update-locale LANG=cs_CZ.UTF-8
apt-get purge -y mc mc-data || true
for name in student lubos jan pepa karel jouda webapp webapp2; do
    id "$name" &>/dev/null || useradd -m -s /bin/bash "$name"
done
getent group apps >/dev/null || groupadd apps
getent group nogroup >/dev/null || groupadd --system nogroup
usermod -aG apps webapp2
usermod -aG sudo student
# Jen uvnitř VM; hostitelská sudoers se nikdy neupravují.
printf 'student ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/90-linux-exam-student
chmod 440 /etc/sudoers.d/90-linux-exam-student
visudo -cf /etc/sudoers.d/90-linux-exam-student
mkdir -p /var/www/html /var/log/nginx/archiv /var/log/nginx/prazdny /home/karel/zaloha/dokumenty /var/tajny
cat > /var/www/html/index.nginx-debian.html <<'HTML'
<!DOCTYPE html><html><head><title>Welcome to nginx!</title></head>
<body><h1>Welcome to nginx!</h1><p>If you see this page, the nginx web server is successfully installed and working.</p></body></html>
HTML
printf '127.0.0.1 - - [20/Oct/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 184\n' > /var/log/nginx/access.log
printf '2026/10/20 10:00:00 [notice] cvičný nginx byl spuštěn\n' > /var/log/nginx/error.log
printf '192.0.2.10 - - [19/Oct/2026:09:01:00 +0000] "GET /index.html HTTP/1.1" 200 184\n' > /var/log/nginx/archiv/access.log.1
printf 'Původní dokument pro zkoušku: alfa 1937, beta 5821.\n' > /home/jan/hesla.doc
chown -R jan:jan /home/jan
printf 'Výroční zpráva\n' > /home/karel/zaloha/dokumenty/zprava.txt
printf 'Seznam souborů zálohy\n' > /home/karel/zaloha/seznam.txt
chown -R karel:karel /home/karel
chown root:root /var/tajny
chown root:root /home/webapp /home/webapp2
chmod 777 /home/webapp /home/webapp2
cp /opt/linux-exam/test.sh /home/student/test.sh
cp /opt/linux-exam/zadani.txt /home/student/zadani.txt
chmod 755 /home/student/test.sh
chown student:student /home/student/test.sh /home/student/zadani.txt
install -o root -g root -m 755 /opt/linux-exam/starttest /opt/linux-exam/statstest /opt/linux-exam/zadanitest /opt/linux-exam/pomoc-test /opt/linux-exam/vysledektest /usr/local/bin/
printf '\nexport LANG=cs_CZ.UTF-8\nstty -ixon -ixoff 2>/dev/null || true\nPS1="\\u@\\h:\\w\\$ "\n' >> /home/student/.bashrc
cat > /etc/motd <<'TXT'
LINUX ESSENTIALS — cvičný Ubuntu Server
Zkoušku spustíš: starttest  |  Barevný přehled: statstest
Odpojení konzole: Ctrl+]  |  Nový pokus: linux-exam reset na hostiteli.
TXT
rm -f /etc/update-motd.d/*
mkdir -p /etc/systemd/system/serial-getty@ttyS0.service.d
cat > /etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf <<'UNIT'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin student --noclear --keep-baud 115200,38400,9600 %I xterm-256color
UNIT
# Opravdový oddíl existuje výhradně na dedikovaném virtuálním disku.
parted -s /dev/sda mklabel gpt mkpart primary ext4 1MiB 100%
udevadm settle
mkfs.ext4 -F -L EXAM-DISK /dev/sda1
# Další samostatný virtuální disk představuje flashku.
mkfs.ext4 -F -L EXAM-FLASH /dev/vdb
mkdir -p /mnt/flashka
printf 'LABEL=EXAM-FLASH /mnt/flashka ext4 defaults,nofail 0 2\n' >> /etc/fstab
mount /mnt/flashka
printf 'Cvičná flashka — pouze data uvnitř virtuálního stroje.\n' > /mnt/flashka/cti-me.txt
cc -O2 -Wall -o /opt/linux-exam/process /opt/linux-exam/process.c
chmod -R a+rX /opt/nyancat
chown -R student:student /opt/nyancat
rm -f /opt/nyancat/src/nyancat
install -m 644 /opt/linux-exam/linux-exam-{fixtures,grader}.service /etc/systemd/system/
mkdir -p /var/lib/linux-exam
chmod 755 /var/lib/linux-exam
python3 - <<'PY'
import sys,json,hashlib,os
from pathlib import Path
sys.path.insert(0,'/opt/linux-exam')
import state
state.write(state.empty())
hosts={}
for line in Path('/etc/hosts').read_text().splitlines():
    fields=line.split('#')[0].split()
    if len(fields)>1:
        for name in fields[1:]:hosts.setdefault(name,[]).append(fields[0])
etc=['etc/'+str(p.relative_to('/etc')) for p in Path('/etc').rglob('*')]
Path('/opt/linux-exam/fixture-manifest.json').write_text(json.dumps(dict(hosts=hosts,etc=etc,hesla=hashlib.sha256(Path('/home/jan/hesla.doc').read_bytes()).hexdigest())))
PY
systemctl daemon-reload
systemctl enable linux-exam-fixtures linux-exam-grader qemu-guest-agent serial-getty@ttyS0
systemctl start qemu-guest-agent linux-exam-fixtures
systemctl disable --now ssh.service ssh.socket 2>/dev/null || true
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service 2>/dev/null || true
# Samostatný log přípravy a jednoznačná značka dokončení.
touch /var/lib/linux-exam/provisioned
systemctl restart serial-getty@ttyS0
