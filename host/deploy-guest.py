#!/usr/bin/env python3
import pathlib,tarfile,io,base64,sys
sys.path.insert(0,'/opt/linux-exam-simulator/host');import guest
p=pathlib.Path('/opt/linux-exam-simulator');data=io.BytesIO()
with tarfile.open(fileobj=data,mode='w:gz') as tf:tf.add(p/'guest',arcname='opt/linux-exam',filter=lambda t:None if '__pycache__' in t.name else t)
command="printf '%s' '"+base64.b64encode(data.getvalue()).decode()+"' | base64 -d | tar xz --warning=no-timestamp -C / && cp /opt/linux-exam/test.sh /home/student/test.sh && cp /opt/linux-exam/zadani.txt /home/student/zadani.txt && chmod 755 /home/student/test.sh && chown student:student /home/student/test.sh /home/student/zadani.txt && install -o root -g root -m 755 /opt/linux-exam/starttest /opt/linux-exam/statstest /opt/linux-exam/zadanitest /opt/linux-exam/pomoc-test /opt/linux-exam/vysledektest /usr/local/bin/ && cp /opt/linux-exam/linux-exam-*.service /etc/systemd/system/ && systemctl daemon-reload"
command+=" && python3 - <<'UPGRADE'\nfrom pathlib import Path\np=Path('/home/student/.bashrc');s=p.read_text();s=s.replace('export TERM=xterm-256color','stty -ixon -ixoff 2>/dev/null || true');p.write_text(s)\nimport json\ns=json.loads(Path('/var/lib/linux-exam/state.json').read_text())\nif s['start'] is not None:Path('/home/student/.linux-exam-instructions-shown').touch()\np=Path('/etc/motd');p.write_text('LINUX ESSENTIALS — cvičný Ubuntu Server\\nZahájení / pokračování: starttest | body: statstest | pomoc: pomoc-test\\nZadání: zadanitest | konzoli opustíš Ctrl+]\\n')\nUPGRADE"
guest.wait(120)
c,o,e=guest.execute(command);print(o,e);sys.exit(c)
