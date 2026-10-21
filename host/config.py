"""Dvě pevně vymezené instance. Testy nikdy nepoužívají uživatelský VM."""
import os
from pathlib import Path
P=Path('/opt/linux-exam-simulator')
INSTANCE=os.environ.get('LINUX_EXAM_INSTANCE','main')
if INSTANCE not in ('main','qa'):
    raise RuntimeError('Neplatná instance cvičného VM.')
VM='linux-essentials-exam'+('-qa' if INSTANCE=='qa' else '')
D=Path('/var/lib/libvirt/images/linux-exam-simulator')
BOOT=P/'build'
REPORTS=P/'reports'
if INSTANCE=='qa':
    D=D/'qa';BOOT=BOOT/'qa';REPORTS=REPORTS/'qa'
MANIFEST=BOOT/'manifest.json'
DISKS=('root','practice','flash')

def baseline(m,name):
    filename=m.get('baselines',{}).get(name,name+'.baseline.qcow2')
    if Path(filename).name!=filename or not filename.startswith(name+'.baseline') or not filename.endswith('.qcow2'):
        raise RuntimeError('Neplatná cesta výchozího disku.')
    return D/filename
