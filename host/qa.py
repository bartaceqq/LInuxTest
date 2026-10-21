#!/usr/bin/env python3
"""Samostatná QA VM; existující uživatelské ani QA prostředky nepřepisuje."""
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET

os.environ['LINUX_EXAM_INSTANCE'] = 'qa'
from config import P, D, BOOT, VM, MANIFEST, DISKS, REPORTS
from reset import validate


def run(*arguments):
    return subprocess.check_output(arguments, stdin=subprocess.DEVNULL, text=True).strip()


def plain_file(path):
    if not path.is_file() or path.is_symlink() or path.resolve() != path:
        raise RuntimeError('Neplatný prostý soubor: ' + str(path))


def verify_path(path):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise RuntimeError('Symlink v cestě vyhrazeného projektu: ' + str(parent))


def report_owner():
    # Přes sudo náleží nové reporty volajícímu; jinak zachováme vlastníka reports.
    user = os.environ.get('SUDO_USER')
    if user and user != 'root':
        return pwd.getpwnam(user).pw_uid, pwd.getpwnam(user).pw_gid
    parent = P / 'reports'
    if parent.is_dir() and not parent.is_symlink():
        details = parent.stat()
        return details.st_uid, details.st_gid
    return 0, 0


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Vytvoření QA vyžaduje sudo.')
    if os.environ.get('LINUX_EXAM_INSTANCE') != 'qa' or VM != 'linux-essentials-exam-qa':
        raise RuntimeError('Nesouhlasí pevně vymezená QA instance.')
    for path in (D, BOOT, REPORTS):
        verify_path(path)
    if MANIFEST.exists():
        validate()
        print('Vyhrazená QA VM již existuje; její stav se nemění.')
        return
    # Jméno i všechny zapisované cesty ověříme před vytvořením jediného souboru.
    if VM in run('virsh', '-c', 'qemu:///system', 'list', '--all', '--name').splitlines():
        raise RuntimeError('Jméno QA je obsazené bez vlastního manifestu; nic nepřepisuji.')
    for path in (D, BOOT):
        if path.exists():
            raise RuntimeError('Cílový QA adresář již existuje; nic nepřepisuji: ' + str(path))
    if REPORTS.exists() and not REPORTS.is_dir():
        raise RuntimeError('Cílová cesta reportů není adresář.')
    qemu_uid = pwd.getpwnam('libvirt-qemu').pw_uid
    kvm_gid = grp.getgrnam('kvm').gr_gid
    owner_uid, owner_gid = report_owner()
    lock_path = P / 'build/operations.lock'
    plain_file(lock_path)
    # Publikace nesmí během kopírování vyměnit mapu výchozích obrazů.
    with lock_path.open('r') as main_lock:
        fcntl.flock(main_lock, fcntl.LOCK_SH)
        main_manifest = P / 'build/manifest.json'
        plain_file(main_manifest)
        original = json.loads(main_manifest.read_text())
        main_dir = Path('/var/lib/libvirt/images/linux-exam-simulator')
        if (original.get('name') != 'linux-essentials-exam'
                or original.get('directory') != str(main_dir)
                or tuple(original.get('disks', ())) != DISKS):
            raise RuntimeError('Neplatný manifest uživatelského VM.')
        uuid.UUID(original['uuid'])
        root = ET.fromstring(run('virsh', '-c', 'qemu:///system', 'dumpxml', original['name'], '--inactive'))
        expected = {str(main_dir / (name + '.qcow2')) for name in DISKS} | {str(main_dir / 'seed.iso')}
        disks = root.findall('devices/disk')
        if (root.findtext('uuid') != original['uuid'] or root.find('devices/hostdev') is not None
                or root.find('devices/filesystem') is not None or len(disks) != 4
                or any(disk.get('type') != 'file' for disk in disks)
                or {disk.find('source').get('file') for disk in disks} != expected):
            raise RuntimeError('Uživatelský VM neodpovídá vyhrazeným prostředkům.')
        sources = {}
        for name in DISKS:
            filename = original.get('baselines', {}).get(name, name + '.baseline.qcow2')
            if (Path(filename).name != filename or not filename.startswith(name + '.baseline')
                    or not filename.endswith('.qcow2')):
                raise RuntimeError('Neplatná cesta výchozího obrazu.')
            source = main_dir / filename
            plain_file(source)
            info = json.loads(run('qemu-img', 'info', '--output=json', str(source)))
            if info.get('format') != 'qcow2' or info.get('backing-filename') or info.get('full-backing-filename'):
                raise RuntimeError('QA požaduje samostatný výchozí QCOW2 obraz: ' + str(source))
            sources[name] = source
        seed = main_dir / 'seed.iso'
        plain_file(seed)
        # mkdir bez exist_ok odmítne i souběžné vytvoření po předběžné kontrole.
        D.mkdir(mode=0o755)
        os.chmod(D, 0o755)
        BOOT.mkdir(mode=0o755)
        os.chmod(BOOT, 0o755)
        new_reports = not REPORTS.exists()
        REPORTS.mkdir(mode=0o755, exist_ok=True)
        if new_reports:
            os.chmod(REPORTS, 0o755)
        if owner_uid != 0 and REPORTS.stat().st_uid == 0:
            os.chown(REPORTS, owner_uid, owner_gid)
        for name in DISKS:
            target = D / (name + '.baseline.qcow2')
            subprocess.run(['qemu-img', 'convert', '-O', 'qcow2', str(sources[name]), str(target)],
                           stdin=subprocess.DEVNULL, check=True)
            os.chown(target, 0, kvm_gid)
            os.chmod(target, 0o440)
            active = D / (name + '.qcow2')
            subprocess.run(['qemu-img', 'create', '-q', '-f', 'qcow2', '-F', 'qcow2', '-b', str(target), str(active)],
                           stdin=subprocess.DEVNULL, check=True)
            os.chown(active, qemu_uid, kvm_gid)
            os.chmod(active, 0o640)
        with seed.open('rb') as source, (D / 'seed.iso').open('xb') as target:
            shutil.copyfileobj(source, target)
        os.chmod(D / 'seed.iso', 0o644)
    new_uuid = str(uuid.uuid4())
    root.find('name').text = VM
    root.find('uuid').text = new_uuid
    if root.find('title') is not None:
        root.find('title').text = 'Linux Essentials — oddělené testování'
    for label in root.findall('seclabel'):
        root.remove(label)
    for disk in root.findall('devices/disk'):
        disk.find('source').set('file', str(D / Path(disk.find('source').get('file')).name))
        for backing in disk.findall('backingStore'):
            disk.remove(backing)
    for channel in root.findall('devices/channel'):
        for source in channel.findall('source'):
            channel.remove(source)
    xml = BOOT / 'domain.xml'
    with xml.open('x') as stream:
        stream.write(ET.tostring(root, encoding='unicode'))
        os.fchmod(stream.fileno(), 0o644)
    manifest = dict(uuid=new_uuid, name=VM, directory=str(D), disks=list(DISKS))
    with MANIFEST.open('x') as stream:
        json.dump(manifest, stream, indent=2)
        os.fchmod(stream.fileno(), 0o644)
    with (BOOT / 'operations.lock').open('x'):
        pass
    os.chmod(BOOT / 'operations.lock', 0o644)
    subprocess.run(['virsh', '-c', 'qemu:///system', 'define', str(xml)], stdin=subprocess.DEVNULL, check=True)
    subprocess.run(['virsh', '-c', 'qemu:///system', 'start', VM], stdin=subprocess.DEVNULL, check=True)
    (BOOT / 'baseline-ready').touch()
    print('QA VM vytvořena. Uživatelský VM a jeho výsledky zůstaly zachované.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
