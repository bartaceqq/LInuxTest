#!/usr/bin/env python3
"""Nedestruktivní regrese hodnotiče: vše vzniká pouze v TemporaryDirectory.

Spuštění: python3 tests/validators-regression.py [cesta/ke/tasks.py]
Bez argumentu použije ../guest/tasks.py; v QA lze předat /opt/linux-exam/tasks.py.
Nepotřebuje roota, nemění /etc, skutečné domovy, zařízení ani zkoušku.
"""
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import types
import unittest
from unittest.mock import patch

module_path=Path(sys.argv.pop(1)) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'guest/tasks.py'
spec=importlib.util.spec_from_file_location('exam_tasks',module_path)
tasks=importlib.util.module_from_spec(spec);spec.loader.exec_module(tasks)


class Validators(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='linux-exam-validators-')
        self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def tree(self):
        source=self.root/'source';source.mkdir()
        (source/'empty').mkdir();(source/'nested').mkdir()
        (source/'nested/log').write_text('real log\n')
        dest=self.root/'dest'
        import shutil
        shutil.copytree(source,dest)
        return source,dest

    def home(self):
        home=self.root/'aneta';home.mkdir()
        (home/'.profile').write_text('profile\n')
        (home/'.bashrc').write_text('bashrc\n')
        (home/'empty').mkdir()
        (home/'link').symlink_to('.profile')
        for f in home.rglob('*'):
            stamp=time.time()-60
            os.utime(f,(stamp,stamp),follow_symlinks=False)
        return home

    def make_home(self,home,exclude=(),wrong=None):
        archive=home/'zaloha.tar.gz'
        with tarfile.open(archive,'w:gz') as tf:
            for f in home.rglob('*'):
                if f==archive or str(f.relative_to(home)) in exclude:continue
                name='aneta/'+str(f.relative_to(home))
                if wrong==str(f.relative_to(home)):
                    info=tarfile.TarInfo(name);info.size=5
                    tf.addfile(info,io.BytesIO(b'wrong'))
                else:tf.add(f,arcname=name,recursive=False)
        return archive

    def valid_home(self,home,path):
        with patch.object(tasks,'user',return_value=types.SimpleNamespace(pw_uid=os.getuid())):
            return tasks.archive(str(path),True,source_root=home)

    def etc(self):
        source=self.root/'etc';source.mkdir()
        for name in ('passwd','group','hosts','fstab'):(source/name).write_text(name+'\n')
        (source/'release').write_text('Ubuntu\n');(source/'os-release').symlink_to('release')
        manifest=self.root/'manifest.json'
        manifest.write_text(json.dumps({'etc':['etc/'+p.name for p in source.iterdir()]}))
        return source,manifest

    def make_etc(self,source):
        archive=self.root/'zaloha-etc.tar'
        with tarfile.open(archive,'w') as tf:tf.add(source,arcname='etc')
        return archive

    def valid_etc(self,source,manifest,path):
        return tasks.archive(str(path),source_root=source,fixture_manifest=manifest)

    def test_tree_valid_and_missing_source(self):
        source,dest=self.tree()
        self.assertTrue(tasks.tree_matches(source,dest))
        source.rename(self.root/'moved')
        self.assertFalse(tasks.tree_matches(source,dest))

    def test_tree_empty_directory_and_contents_required(self):
        source,dest=self.tree();(dest/'empty').rmdir()
        self.assertFalse(tasks.tree_matches(source,dest))
        (dest/'empty').mkdir();(dest/'nested/log').write_text('wrong')
        self.assertFalse(tasks.tree_matches(source,dest))

    def test_tree_symlink_directory_required(self):
        source,dest=self.tree();(source/'logs').symlink_to('nested',target_is_directory=True)
        self.assertFalse(tasks.tree_matches(source,dest))
        (dest/'logs').symlink_to('nested',target_is_directory=True)
        self.assertTrue(tasks.tree_matches(source,dest))

    def test_tree_walk_error_is_failure(self):
        source,dest=self.tree()
        def unreadable(*args,**kwargs):
            kwargs['onerror'](PermissionError('nečitelný zdroj'))
            return iter(())
        with patch.object(tasks.os,'walk',side_effect=unreadable):
            self.assertFalse(tasks.tree_matches(source,dest))

    def permission_case(self,task,named,perms):
        rows={('user',''):set('rwx'),('group',''):set('rx') if task==17 else set(),
              ('other',''):set(),('user',named):set(perms)}
        with patch.object(tasks,'directory',return_value=True), \
             patch.object(tasks.os,'stat',return_value=types.SimpleNamespace(st_uid=1000,st_gid=2000)), \
             patch.object(tasks.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=1000)), \
             patch.object(tasks.grp,'getgrnam',return_value=types.SimpleNamespace(gr_gid=2000)), \
             patch.object(tasks,'acl',return_value=rows):
            return tasks.permissions('/unused/mock-path',task)

    def test_acl_redundant_owner_name_accepted(self):
        for task,owner in ((16,'webapp'),(17,'webapp2')):
            for perms in ('','rwx'):
                with self.subTest(task=task,perms=perms):
                    self.assertTrue(self.permission_case(task,owner,perms))

    def test_acl_redundant_owner_uid_accepted(self):
        for task in (16,17):
            for perms in ('','rwx'):
                with self.subTest(task=task,perms=perms):
                    self.assertTrue(self.permission_case(task,'1000',perms))

    def test_acl_other_user_execute_rejected(self):
        for task in (16,17):
            for name in ('outsider','1001'):
                with self.subTest(task=task,name=name):
                    self.assertFalse(self.permission_case(task,name,'x'))

    def test_home_valid_complete(self):
        home=self.home();self.assertTrue(self.valid_home(home,self.make_home(home)))

    def test_home_stable_missing_and_wrong_file_rejected(self):
        home=self.home()
        self.assertFalse(self.valid_home(home,self.make_home(home,exclude=('.profile',))))
        self.assertFalse(self.valid_home(home,self.make_home(home,wrong='.profile')))

    def test_home_stable_directory_and_symlink_required(self):
        home=self.home()
        self.assertFalse(self.valid_home(home,self.make_home(home,exclude=('empty',))))
        self.assertFalse(self.valid_home(home,self.make_home(home,exclude=('link',))))

    def test_home_snapshot_survives_later_history_and_edit(self):
        home=self.home();archive=self.make_home(home)
        stamp=archive.stat().st_mtime+2
        history=home/'.bash_history';history.write_text('exit\n');os.utime(history,(stamp,stamp))
        profile=home/'.profile';profile.write_text('new profile\n');os.utime(profile,(stamp,stamp))
        self.assertTrue(self.valid_home(home,archive))

    def test_home_empty_imitation_rejected(self):
        home=self.home();archive=home/'zaloha.tar.gz'
        with tarfile.open(archive,'w:gz') as tf:
            info=tarfile.TarInfo('aneta');info.type=tarfile.DIRTYPE;tf.addfile(info)
        self.assertFalse(self.valid_home(home,archive))

    def test_home_bad_gzip_crc_rejected(self):
        home=self.home();archive=self.make_home(home)
        data=bytearray(archive.read_bytes());data[-8]^=0xff;archive.write_bytes(data)
        with self.assertRaises((gzip.BadGzipFile,tarfile.ReadError,EOFError)):
            self.valid_home(home,archive)

    def test_etc_valid_and_later_account_change(self):
        source,manifest=self.etc();archive=self.make_etc(source)
        self.assertTrue(self.valid_etc(source,manifest,archive))
        passwd=source/'passwd';passwd.write_text('later-account\n')
        stamp=archive.stat().st_mtime+2;os.utime(passwd,(stamp,stamp))
        self.assertTrue(self.valid_etc(source,manifest,archive))

    def test_etc_old_wrong_content_rejected(self):
        source,manifest=self.etc();archive=self.make_etc(source)
        old=archive.stat().st_mtime-10
        (source/'passwd').write_text('not in archive\n');os.utime(source/'passwd',(old,old))
        self.assertFalse(self.valid_etc(source,manifest,archive))

    def test_etc_dangling_and_cyclic_hardlink_rejected(self):
        source,manifest=self.etc()
        for targets in [('missing',),('etc/cycle','etc/passwd')]:
            archive=self.root/'fake.tar'
            with tarfile.open(archive,'w') as tf:
                tf.add(source,arcname='etc',filter=lambda m:None if m.name=='etc/passwd' else m)
                info=tarfile.TarInfo('etc/passwd');info.type=tarfile.LNKTYPE;info.linkname=targets[0];tf.addfile(info)
                if len(targets)==2:
                    info=tarfile.TarInfo('etc/cycle');info.type=tarfile.LNKTYPE;info.linkname=targets[1];tf.addfile(info)
            self.assertFalse(self.valid_etc(source,manifest,archive))

    def test_etc_real_hardlink_accepted(self):
        source,manifest=self.etc();archive=self.root/'hardlink.tar'
        with tarfile.open(archive,'w') as tf:
            tf.add(source,arcname='etc',filter=lambda m:None if m.name=='etc/passwd' else m)
            tf.add(source/'passwd',arcname='etc/passwd-data')
            info=tarfile.TarInfo('etc/passwd');info.type=tarfile.LNKTYPE;info.linkname='etc/passwd-data';tf.addfile(info)
        self.assertTrue(self.valid_etc(source,manifest,archive))


if __name__=='__main__':unittest.main(verbosity=2)
