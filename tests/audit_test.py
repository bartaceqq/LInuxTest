#!/usr/bin/env python3
"""Regrese auditu pouze nad syntetickými daty a dočasným manifestem."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
import audit
spec=importlib.util.spec_from_file_location('check_host',ROOT/'tests/check-host.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)


class AuditTests(unittest.TestCase):
    def accounts(self):
        return {'/etc/passwd':{'entries':{'root':'root-hash','old':'old-hash'},'groups':{}},
                '/etc/shadow':{'entries':{'root':'password-hash'},'groups':{}},
                '/etc/group':{'entries':{'kvm':'old-group-hash'},'groups':{
                    'kvm':{'identity_sha256':'identity','members':['old'],'admins':[]}}},
                '/etc/gshadow':{'entries':{},'groups':{}}}

    def test_service_account_addition_allowed_existing_changes_rejected(self):
        before=self.accounts();after=copy.deepcopy(before)
        after['/etc/passwd']['entries']['qemu-service']='new-service'
        after['/etc/group']['entries']['kvm']='new-group-hash'
        after['/etc/group']['groups']['kvm']['members'].append('qemu-service')
        self.assertTrue(checker.original_accounts_unchanged(before,after))
        after['/etc/passwd']['entries']['old']='changed-uid-or-home'
        self.assertFalse(checker.original_accounts_unchanged(before,after))

    def test_old_user_group_change_rejected(self):
        before=self.accounts();after=copy.deepcopy(before)
        after['/etc/group']['entries']['kvm']='changed'
        after['/etc/group']['groups']['kvm']['members'].append('root')
        self.assertFalse(checker.original_accounts_unchanged(before,after))

    def test_manifest_and_uuid_required_to_exclude_domain(self):
        with tempfile.TemporaryDirectory(prefix='linux-exam-audit-') as temporary:
            project=Path(temporary)/'project';build=project/'build';build.mkdir(parents=True)
            image=Path(temporary)/'images'
            identity='ed317f99-88b1-4d15-a6a8-b573254f780f';name='linux-essentials-exam'
            xml=ET.fromstring(f'<domain><name>{name}</name><uuid>{identity}</uuid><devices/></domain>')
            for filename in ('root.qcow2','practice.qcow2','flash.qcow2','seed.iso'):
                disk=ET.SubElement(xml.find('devices'),'disk',{'type':'file'})
                ET.SubElement(disk,'source',{'file':str(image/filename)})
            manifest={'uuid':identity,'name':name,'directory':str(image),'disks':['root','practice','flash']}
            with patch.object(audit,'PROJECT',project),patch.object(audit,'IMAGE_ROOT',image):
                self.assertFalse(audit.owned_domain(name,xml))
                path=build/'manifest.json';path.write_text(json.dumps(manifest))
                self.assertTrue(audit.owned_domain(name,xml))
                xml.find('uuid').text='a-different-uuid'
                self.assertFalse(audit.owned_domain(name,xml))

    def test_missing_probe_is_skipped_and_address_lifetimes_ignored(self):
        self.assertIsNone(checker.unchanged({'vms':{'ok':False}},{'vms':{'ok':True,'value':{}}},'vms'))
        before=[{'addr_info':[{'local':'192.0.2.1','valid_life_time':100,'preferred_life_time':80}]}]
        after=copy.deepcopy(before);after[0]['addr_info'][0]['valid_life_time']=99
        self.assertEqual(checker.normalized_addresses(before),checker.normalized_addresses(after))
        self.assertIn('valid_life_time',before[0]['addr_info'][0])

    def test_fresh_inactive_network_visible_without_active_network(self):
        before={'networks':{'ok':True,'value':{}}}
        after={'networks':{'ok':True,'value':{'default':{'active':'no'}}}}
        self.assertTrue(checker.original_networks_unchanged(before,after))
        self.assertTrue(checker.no_extra_active_network(before,after))
        after['networks']['value']['default']['active']='yes'
        self.assertFalse(checker.no_extra_active_network(before,after))


if __name__=='__main__':unittest.main(verbosity=2)
