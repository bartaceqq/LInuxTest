#!/usr/bin/env python3
"""Sestavení cloud-init a XML; existující konfigurace se nikdy nepřepisuje."""
import base64
import io
import json
import os
from pathlib import Path
import tarfile
import uuid
import xml.etree.ElementTree as ET
import yaml

P = Path('/opt/linux-exam-simulator')
D = Path('/var/lib/libvirt/images/linux-exam-simulator')
VM = 'linux-essentials-exam'
OUTPUTS = ('user-data', 'meta-data', 'network-config', 'manifest.json', 'domain.xml')


def resources(path):
    result = {'vcpus': 2, 'memory_mib': 2048}
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Neplatný soubor s prostředky VM.')
        values = json.loads(path.read_text())
        if not isinstance(values, dict) or set(values) - set(result):
            raise RuntimeError('Prostředky VM mohou obsahovat pouze vcpus a memory_mib.')
        result.update(values)
    for key, low, high in (('vcpus', 1, 64), ('memory_mib', 1024, 65536)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise RuntimeError(f'Neplatná hodnota {key}: povoleno {low} až {high}.')
    return result


def domain_xml(manifest, allocation):
    xml = f'''<domain type='kvm'>
<name>{manifest['name']}</name><uuid>{manifest['uuid']}</uuid><title>Linux Essentials — cvičná zkouška</title>
<memory unit='MiB'>{allocation['memory_mib']}</memory><vcpu>{allocation['vcpus']}</vcpu><os><type arch='x86_64' machine='q35'>hvm</type><boot dev='hd'/></os>
<features><acpi/><apic/></features><cpu mode='host-model'/><clock offset='utc'/>
<on_poweroff>destroy</on_poweroff><on_reboot>restart</on_reboot><on_crash>destroy</on_crash>
<devices><emulator>/usr/bin/qemu-system-x86_64</emulator>
<controller type='sata' index='0'/><controller type='virtio-serial' index='0'/>
<disk type='file' device='disk'><driver name='qemu' type='qcow2' discard='unmap'/><source file='{D}/root.qcow2'/><target dev='vda' bus='virtio'/></disk>
<disk type='file' device='disk'><driver name='qemu' type='qcow2'/><source file='{D}/practice.qcow2'/><target dev='sda' bus='sata'/><address type='drive' controller='0' bus='0' target='0' unit='0'/></disk>
<disk type='file' device='disk'><driver name='qemu' type='qcow2'/><source file='{D}/flash.qcow2'/><target dev='vdb' bus='virtio'/></disk>
<disk type='file' device='cdrom'><driver name='qemu' type='raw'/><source file='{D}/seed.iso'/><target dev='sdb' bus='sata'/><readonly/><address type='drive' controller='0' bus='0' target='0' unit='1'/></disk>
<interface type='user'><mac address='52:54:00:ea:34:01'/><model type='virtio'/></interface>
<interface type='user'><mac address='52:54:00:ea:34:02'/><model type='virtio'/><ip address='10.0.3.1' prefix='24'/></interface>
<serial type='pty'><target type='isa-serial' port='0'/></serial><console type='pty'><target type='serial' port='0'/></console>
<channel type='unix'><target type='virtio' name='org.qemu.guest_agent.0'/></channel>
<rng model='virtio'><backend model='random'>/dev/urandom</backend></rng><memballoon model='virtio'/>
</devices></domain>'''
    ET.fromstring(xml)
    return xml


def main():
    build = P / 'build'
    if not build.is_dir() or build.is_symlink() or build.resolve() != build:
        raise RuntimeError('Chybí skutečný vyhrazený adresář build.')
    for name in OUTPUTS:
        path = build / name
        if path.exists() or path.is_symlink():
            raise RuntimeError('Konfigurace již existuje, nic nepřepisuji: ' + str(path))
    allocation = resources(build / 'resources.json')
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:gz') as archive:
        archive.add(P / 'guest', arcname='opt/linux-exam',
                    filter=lambda item: None if '__pycache__' in item.name else item)
        archive.add(P / 'downloads/nyancat', arcname='opt/nyancat',
                    filter=lambda item: None if '/.git' in item.name else item)
    manifest = dict(uuid=str(uuid.uuid4()), name=VM, directory=str(D),
                    disks=['root', 'practice', 'flash'], resources=allocation)
    cloud = {
        'hostname': 'linux-exam', 'manage_etc_hosts': True, 'timezone': 'Europe/Prague',
        'users': [{'name': 'student', 'shell': '/bin/bash',
                   'sudo': 'ALL=(ALL) NOPASSWD:ALL', 'lock_passwd': True}],
        'ssh_pwauth': False, 'disable_root': True,
        'write_files': [{'path': '/root/linux-exam-payload.tar.gz', 'encoding': 'b64',
                         'permissions': '0600', 'content': base64.b64encode(payload.getvalue()).decode()}],
        'runcmd': [['bash', '-c', 'tar -xzf /root/linux-exam-payload.tar.gz -C / && bash /opt/linux-exam/provision.sh > /var/log/linux-exam-provision.log 2>&1']],
    }
    network = {'version': 2, 'ethernets': {
        'uplink': {'match': {'macaddress': '52:54:00:ea:34:01'}, 'set-name': 'eth0', 'dhcp4': True, 'dhcp6': False},
        'practice': {'match': {'macaddress': '52:54:00:ea:34:02'}, 'set-name': 'eth1', 'dhcp4': False,
                     'dhcp6': False, 'optional': True, 'link-local': []},
    }}
    outputs = {
        'user-data': '#cloud-config\n' + yaml.safe_dump(cloud, allow_unicode=True),
        'meta-data': f"instance-id: {manifest['uuid']}\nlocal-hostname: linux-exam\n",
        'network-config': yaml.safe_dump(network),
        'manifest.json': json.dumps(manifest, indent=2) + '\n',
        'domain.xml': domain_xml(manifest, allocation),
    }
    # O_EXCL chrání i před souběžným vytvořením nebo symlinkem po kontrole.
    for name, data in outputs.items():
        with (build / name).open('x') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), 0o644)
    print(f"Konfigurace sestavena: {allocation['vcpus']} vCPU, {allocation['memory_mib']} MiB RAM.")


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error))
