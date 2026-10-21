#!/usr/bin/env python3
"""Pouze mock tmux; žádný kontakt s hostitelským ani guest tmux/VM."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE=Path(__file__).resolve().parents[1]/'guest/session.py'
spec=importlib.util.spec_from_file_location('exam_session_fast_test',SOURCE)
session=importlib.util.module_from_spec(spec);spec.loader.exec_module(session)


def rows():
    result=[]
    for index,role,pane,start in (
        (1,'shell','%0','bash /opt/linux-exam/shell.sh'),
        (1,'progress','%1','statstest --watch'),
        (2,'tasks','%2','python3 /opt/linux-exam/view.py tasks'),
        (3,'assignment','%3','python3 /opt/linux-exam/view.py assignment'),
        (4,'help','%4','python3 /opt/linux-exam/view.py help'),
        (5,'result','%5','python3 /opt/linux-exam/view.py result'),
    ):
        result.append([str(index),pane,role,'0',start,'4','4'])
    return result


def render(data):return '\n'.join('\t'.join(row) for row in data)


class Navigation(unittest.TestCase):
    def ready(self,data):
        with mock.patch.object(session,'tm',return_value=render(data)) as tm:
            result=session.ready_shell()
        self.assertEqual(tm.call_count,1)
        self.assertEqual(tm.call_args.args[:4],('list-panes','-s','-t','praktikum'))
        return result

    def test_current_all_roles(self):self.assertEqual(self.ready(rows()),'%0')

    def test_quoted_start_commands(self):
        data=rows()
        data[1][4]="'statstest --watch'"  # tmux může formátovat příkaz jako jeden argument.
        self.assertEqual(self.ready(data),'%0')

    def test_preserved_legacy_bash_is_safe(self):
        data=rows();data[0][4]='/bin/bash'
        self.assertEqual(self.ready(data),'%0')

    def test_extra_user_windows_untouched(self):
        data=rows();data.append(['6','%7','','0','nano /tmp/user-file','',''])
        data.append(['8','%8','shell','1','some old command','3',''])
        self.assertEqual(self.ready(data),'%0')

    def test_each_missing_role_requires_repair(self):
        for index in range(6):
            with self.subTest(index=index):
                data=rows();data.pop(index)
                self.assertIsNone(self.ready(data))

    def test_missing_metadata_dead_wrong_version_start_or_role_require_repair(self):
        for row in range(6):
            for column,value in ((2,'unknown'),(3,'1'),(4,'nano /tmp/work'),(5,'3'),(6,'')):
                with self.subTest(row=row,column=column):
                    data=rows();data[row][column]=value
                    self.assertIsNone(self.ready(data))

    def test_duplicate_or_misplaced_role_requires_repair(self):
        data=rows();data.append(data[0][:]);data[-1][1]='%90'
        self.assertIsNone(self.ready(data))
        data=rows();data[2][0]='4'
        self.assertIsNone(self.ready(data))

    def test_shell_go_uses_four_calls_no_ensure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(session.Path,'home',return_value=Path(tmp)), \
                 mock.patch.object(session,'tm',side_effect=lambda *args,**kwargs:render(rows()) if args[0]=='list-panes' else '') as tm, \
                 mock.patch.object(session,'ensure',side_effect=AssertionError('fast path did full repair')), \
                 mock.patch('sys.argv',['session.py','go','shell']):
                session.main()
        self.assertEqual([c.args[0] for c in tm.call_args_list],['list-panes','select-window','select-pane','refresh-client'])
        self.assertEqual(tm.call_args_list[2].args,('select-pane','-t','%0'))

    def test_view_go_uses_three_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(session.Path,'home',return_value=Path(tmp)), \
                 mock.patch.object(session,'tm',side_effect=lambda *args,**kwargs:render(rows()) if args[0]=='list-panes' else '') as tm, \
                 mock.patch.object(session,'ensure',side_effect=AssertionError('fast path did full repair')), \
                 mock.patch('sys.argv',['session.py','go','assignment']):
                session.main()
        self.assertEqual([c.args[0] for c in tm.call_args_list],['list-panes','select-window','refresh-client'])
        self.assertEqual(tm.call_args_list[1].args,('select-window','-t','praktikum:3'))

    def test_go_checks_missing_other_window_not_only_requested_shell(self):
        data=rows();data.pop(4)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(session.Path,'home',return_value=Path(tmp)), \
                 mock.patch.object(session,'tm',side_effect=lambda *args,**kwargs:render(data) if args[0]=='list-panes' and '-s' in args else '') as tm, \
                 mock.patch.object(session,'panes',return_value=[]), \
                 mock.patch.object(session,'ensure',return_value='%0') as ensure, \
                 mock.patch('sys.argv',['session.py','go','shell']):
                session.main()
        ensure.assert_called_once_with()

    def test_repair_always_uses_full_ensure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(session.Path,'home',return_value=Path(tmp)), \
                 mock.patch.object(session,'tm',return_value=''), \
                 mock.patch.object(session,'panes',return_value=[]), \
                 mock.patch.object(session,'ready_shell',side_effect=AssertionError('repair must not fast path')), \
                 mock.patch.object(session,'ensure',return_value='%0') as ensure, \
                 mock.patch('sys.argv',['session.py','repair']):
                session.main()
        ensure.assert_called_once_with()

if __name__=='__main__':unittest.main(verbosity=2)
