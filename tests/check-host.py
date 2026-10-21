#!/usr/bin/env python3
"""Porovnání čtecích snímků; nikdy neopravuje ani nerestartuje hostitelské služby."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

PROJECT=Path('/opt/linux-exam-simulator')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
import audit


def normalized_addresses(rows):
    rows=copy.deepcopy(rows)
    for interface in rows:
        for address in interface.get('addr_info',[]):
            address.pop('valid_life_time',None);address.pop('preferred_life_time',None)
    return rows


def unchanged(before,after,name,normalize=lambda value:value,subset=False):
    previous=before[name];current=after[name]
    if not previous['ok']:return None
    if not current['ok']:return False
    previous=normalize(previous['value']);current=normalize(current['value'])
    return set(previous)<=set(current) if subset else previous==current


def original_accounts_unchanged(before,after):
    # Nový servisní účet může přidat správce balíčků. Existující účty,
    # jejich hesla/UID/GID a členství původních uživatelů se měnit nesmějí.
    new_users=set(after['/etc/passwd']['entries'])-set(before['/etc/passwd']['entries'])
    for path,previous in before.items():
        current=after[path]
        for name,digest in previous['entries'].items():
            if current['entries'].get(name)==digest:continue
            old=previous.get('groups',{}).get(name);new=current.get('groups',{}).get(name)
            if not old or not new or old['identity_sha256']!=new['identity_sha256']:return False
            for field in ('members','admins'):
                old_names=set(old[field]);new_names=set(new[field])
                if not old_names<=new_names or not new_names-old_names<=new_users:return False
    return True


def original_networks_unchanged(before,after):
    previous=before['networks'];current=after['networks']
    if not previous['ok']:return None
    return current['ok'] and all(current['value'].get(name)==value for name,value in previous['value'].items())


def no_extra_active_network(before,after):
    previous=before['networks'];current=after['networks']
    if not previous['ok']:return None
    return current['ok'] and all(value.get('active')=='no' for name,value in current['value'].items()
                                 if name not in previous['value'])


def compare(before,after):
    if before.get('schema_version')!=2 or after.get('schema_version')!=2:
        raise ValueError('Je potřeba nový snímek host/audit.py se schema_version=2.')
    return {
        'Původní účty, hesla a členství původních uživatelů beze změn':original_accounts_unchanged(before['accounts'],after['accounts']),
        'Hostitelské mounty beze změn':unchanged(before,after,'mounts'),
        'Hostitelské směrování beze změn':unchanged(before,after,'routes'),
        'Hostitelská rozhraní a adresy beze změn':unchanged(before,after,'addresses',normalized_addresses),
        'Nesouvisející VM a jejich konfigurace beze změn':unchanged(before,after,'vms'),
        'Původní sítě libvirt beze změn':original_networks_unchanged(before,after),
        'Nevznikla další aktivní síť libvirt':no_extra_active_network(before,after),
        'Původní běžící služby zůstávají spuštěné':unchanged(before,after,'services',subset=True),
        'Původní příkaz virt nebo jeho nepřítomnost beze změn':before['virt_command']==after['virt_command'],
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,default=PROJECT/'reports/host-before.json')
    parser.add_argument('--after',type=Path,default=PROJECT/'reports/host-after.json')
    parser.add_argument('--report',type=Path,default=PROJECT/'reports/host-isolation.json')
    args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Kontrola hostitele vyžaduje sudo.')
    before=json.loads(args.before.read_text());after=audit.capture();checks=compare(before,after)
    args.after.parent.mkdir(parents=True,exist_ok=True)
    args.after.write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n')
    for name,result in checks.items():
        print(('SKIP' if result is None else 'PASS' if result else 'FAIL')+': '+name)
    passed=all(result is not False for result in checks.values())
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({'passed':passed,'checks':checks,
        'skipped_reason':'SKIP: odpovídající zdroj nebyl dostupný již ve vstupním snímku.',
        'added_account_entries':{path:sorted(set(value['entries'])-set(before['accounts'][path]['entries']))
                                 for path,value in after['accounts'].items()},
        'added_network_definitions':sorted(set(after['networks'].get('value',{}))-set(before['networks'].get('value',{}))),
        'excluded_owned_vms':after['excluded_owned_vms']},ensure_ascii=False,indent=2)+'\n')
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
