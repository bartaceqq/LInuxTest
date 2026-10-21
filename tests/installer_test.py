#!/usr/bin/env python3
"""Nedestruktivní kontroly přenositelné instalace v dočasných adresářích."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('exam_install',PROJECT/'host/install.py')
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
spec=importlib.util.spec_from_file_location('exam_build',PROJECT/'host/build.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

class Installer(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.target=self.root/'opt/project';self.disks=self.root/'images/exam';self.command=self.root/'bin/linux-exam'
 def check(self):return install.collision_check(self.target,self.disks,self.command)
 def test_empty_is_safe(self):self.assertFalse(self.check())
 def test_other_command_untouched(self):
  self.command.parent.mkdir();self.command.write_text('existing')
  with self.assertRaises(RuntimeError):self.check()
  self.assertEqual(self.command.read_text(),'existing');self.assertFalse(self.target.exists())
 def test_foreign_symlink_untouched(self):
  self.command.parent.mkdir();self.command.symlink_to('/somebody/else')
  with self.assertRaises(RuntimeError):self.check()
  self.assertEqual(str(self.command.readlink()),'/somebody/else')
 def test_target_never_overwritten(self):
  self.target.mkdir(parents=True);sentinel=self.target/'keep';sentinel.write_text('score')
  with self.assertRaises(RuntimeError):self.check()
  self.assertEqual(sentinel.read_text(),'score')
 def test_disk_never_overwritten(self):
  self.disks.mkdir(parents=True);disk=self.disks/'existing.qcow2';disk.write_text('disk')
  with self.assertRaises(RuntimeError):self.check()
  self.assertEqual(disk.read_text(),'disk')
 def test_parent_symlink_rejected(self):
  (self.root/'opt').symlink_to(self.root/'real')
  with self.assertRaises(RuntimeError):self.check()
 def test_completed_install_is_only_detected(self):
  (self.target/'build').mkdir(parents=True);(self.target/'host').mkdir()
  (self.target/'build/baseline-ready').touch();(self.target/'build/manifest.json').write_text('{}');(self.target/'host/reset.py').touch()
  self.assertTrue(self.check())
  self.assertEqual((self.target/'build/manifest.json').read_text(),'{}')
 def test_missing_manifest_is_not_completed(self):
  (self.target/'build').mkdir(parents=True);(self.target/'build/baseline-ready').touch()
  with self.assertRaises(RuntimeError):self.check()
 def test_resource_conservation(self):
  self.assertEqual(install.choose_resources(4000,3100,4),{'vcpus':2,'memory_mib':2048})
  self.assertEqual(install.choose_resources(3500,2400,1),{'vcpus':1,'memory_mib':1536})
  with self.assertRaises(RuntimeError):install.choose_resources(2000,1900,8)
 def test_build_resources_validation(self):
  file=self.root/'resources.json';self.assertEqual(build.resources(file),{'vcpus':2,'memory_mib':2048})
  for values in ({'vcpus':0},{'memory_mib':-1},{'vcpus':True},{'memory_mib':'2048'},{'disk':'/dev/sda'}):
   file.write_text(json.dumps(values))
   with self.assertRaises(RuntimeError):build.resources(file)
 def test_domain_uses_files_only_and_selected_resources(self):
  import xml.etree.ElementTree as ET
  tree=ET.fromstring(build.domain_xml({'name':'linux-essentials-exam','uuid':'12345678-1234-1234-1234-123456789abc'},{'vcpus':1,'memory_mib':1536}))
  self.assertEqual(tree.findtext('memory'),'1536');self.assertEqual(tree.findtext('vcpu'),'1')
  self.assertEqual(len(tree.findall('devices/disk')),4)
  self.assertTrue(all(d.get('type')=='file' for d in tree.findall('devices/disk')))
  self.assertIsNone(tree.find('devices/hostdev'));self.assertIsNone(tree.find('devices/filesystem'))
  self.assertTrue(all(i.get('type')=='user' for i in tree.findall('devices/interface')))
 def test_copy_excludes_runtime_private_data(self):
  source=self.root/'source';source.mkdir()
  (source/'host').mkdir();(source/'host/secret.pyc').write_text('cache');(source/'host/ok.py').write_text('code')
  for name in ('reports','build','downloads'):
   (source/name).mkdir();(source/name/'private').write_text('PRIVATE')
  self.target.parent.mkdir(parents=True)
  install.copy_source(source,self.target)
  self.assertEqual((self.target/'host/ok.py').read_text(),'code')
  self.assertFalse((self.target/'host/secret.pyc').exists())
  self.assertFalse(list(self.target.rglob('private')))
 def test_copy_works_with_restrictive_umask(self):
  import os
  source=self.root/'source';source.mkdir();(source/'host').mkdir();(source/'host/ok.py').write_text('code')
  self.target.parent.mkdir(parents=True)
  old=os.umask(0o077)
  try:install.copy_source(source,self.target)
  finally:os.umask(old)
  for path in (self.target,self.target/'host',self.target/'build',self.target/'downloads',self.target/'reports'):
   self.assertEqual(path.stat().st_mode&0o777,0o755)
 def test_storage_inspects_actual_disk_directory(self):
  self.target.parent.mkdir(parents=True);self.disks.parent.mkdir(parents=True)
  with patch.object(install.shutil,'disk_usage',return_value=type('Usage',(),{'free':11*1024**3})()):
   with self.assertRaises(RuntimeError):install.storage_check(self.target,self.disks)
  with patch.object(install.shutil,'disk_usage',return_value=type('Usage',(),{'free':12*1024**3})()):
   install.storage_check(self.target,self.disks)
 def repair_fixture(self):
  (self.target/'host').mkdir(parents=True);(self.target/'host/linux-exam').write_text('command')
  state=self.target/'state.json';state.write_text('preserved')
  return state
 def test_completed_install_repairs_only_missing_command(self):
  import io,contextlib
  state=self.repair_fixture()
  with patch.object(install,'preflight',return_value={'already':True,'release':{}}),patch.object(install,'COMMAND',self.command),patch.object(install,'TARGET',self.target),patch.object(install.os,'geteuid',return_value=0),patch.object(install.sys,'argv',['install.py','--yes']),contextlib.redirect_stdout(io.StringIO()):
   install.main()
  self.assertEqual(self.command.resolve(),self.target/'host/linux-exam');self.assertEqual(state.read_text(),'preserved')
 def test_readonly_check_does_not_repair_command(self):
  import io,contextlib
  state=self.repair_fixture()
  with patch.object(install,'preflight',return_value={'already':True,'release':{}}),patch.object(install,'COMMAND',self.command),patch.object(install,'TARGET',self.target),patch.object(install.sys,'argv',['install.py','--check']),contextlib.redirect_stdout(io.StringIO()):
   install.main()
  self.assertFalse(self.command.exists());self.assertEqual(state.read_text(),'preserved')
 def test_source_rejects_symlink(self):
  source=self.root/'source';source.mkdir()
  for name in ('guest/provision.sh','host/build.py','host/bootstrap.sh','tests/initial.py','keys/ubuntu-cloudimage-keyring.gpg'):
   p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
  (source/'guest/link').symlink_to('/etc/passwd')
  with self.assertRaises(RuntimeError):install.source_check(source)

if __name__=='__main__':unittest.main(verbosity=2)
