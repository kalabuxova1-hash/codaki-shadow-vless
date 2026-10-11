#!/usr/bin/env python3
"""Direct physical-network routing for installed Russian Android applications.

Never infer an application's nationality from IPs. Bind known Russian package
names to their currently assigned Android UIDs. Leave foreign apps on the TUN.
"""
import re
import subprocess

IP = '/system/bin/ip'
PM = '/system/bin/pm'
PRIO = '8997'
EXTRA_PREFIXES = (
    'com.yandex.', 'com.vkontakte.', 'com.mailru.',
    'com.mail.ru.', 'com.idamob.tinkoff.', 'com.gnivts.',
    'com.zvooq.', 'com.taxsee.',
)
EXTRA_NAMES = {'to.boosty.android'}


def app_uids():
    result = subprocess.run([PM, 'list', 'packages', '-U'], capture_output=True,
                            text=True, timeout=15)
    if result.returncode:
        raise RuntimeError('Cannot read Android installed package UIDs')
    found = {}
    for line in result.stdout.splitlines():
        match = re.fullmatch(r'package:([^ ]+) uid:(\d+)', line.strip())
        if not match:
            continue
        package, uid_string = match.groups()
        if package.startswith('ru.') or package.startswith(EXTRA_PREFIXES) or package in EXTRA_NAMES:
            uid = int(uid_string)
            if 10000 <= uid <= 999999:
                found[package] = uid
    return found


def excluded_uids():
    return sorted({0, *app_uids().values()})


def patch_tun(config):
    uids = excluded_uids()
    for inbound in config.get('inbounds', []):
        if inbound.get('type') == 'tun':
            inbound['exclude_uid'] = uids
    return uids


def _output(command):
    return subprocess.check_output(command, timeout=10, stderr=subprocess.DEVNULL).decode()


def _physical_interface():
    output = _output([IP, '-4', 'route', 'get', '1.1.1.1', 'uid', '0'])
    match = re.search(r'\bdev\s+(wlan\d+|rmnet_data\d+)\b', output)
    if not match:
        return None
    iface = match.group(1)
    default = _output([IP, '-4', 'route', 'show', 'table', iface])
    return iface if re.search(r'^default\s', default, re.M) else None


def _owned_rules(family):
    output = _output([IP, family, 'rule', 'show'])
    owned = set()
    for line in output.splitlines():
        if not line.startswith(PRIO + ':'):
            continue
        match = re.fullmatch(
            PRIO + r':\s+from all iif lo uidrange (\d+)-(\d+) (?:lookup (wlan\d+|rmnet_data\d+)|unreachable)',
            line.strip())
        if not match or match.group(1) != match.group(2):
            raise RuntimeError('Rule priority 8997 is already owned or malformed')
        owned.add((int(match.group(1)), match.group(3) or 'unreachable'))
    return owned


def _update_rules(family, uids, iface):
    old = _owned_rules(family)
    default = False
    if iface:
        default = bool(re.search(r'^default\s',
            _output([IP, family, 'route', 'show', 'table', iface]), re.M))
    target = iface if default else 'unreachable'
    desired = {(uid, target) for uid in uids}
    if old == desired:
        return 0
    for uid, old_interface in sorted(old - desired):
        command = [IP, family, 'rule', 'del', 'pref', PRIO,
                   'iif', 'lo', 'uidrange', f'{uid}-{uid}']
        command += ['unreachable'] if old_interface == 'unreachable' else ['lookup', old_interface]
        subprocess.run(command, check=True, capture_output=True, timeout=8)
    for uid, new_interface in sorted(desired - old):
        command = [IP, family, 'rule', 'add', 'pref', PRIO,
                   'iif', 'lo', 'uidrange', f'{uid}-{uid}']
        command += ['unreachable'] if new_interface == 'unreachable' else ['lookup', new_interface]
        subprocess.run(command, check=True, capture_output=True, timeout=8)
    if _owned_rules(family) != desired:
        raise RuntimeError('Russian application direct rules failed verification')
    return len(old ^ desired)


def _remove_legacy_vk(vk_uid):
    if not vk_uid:
        return
    for family in ('-4', '-6'):
        for line in _output([IP, family, 'rule', 'show']).splitlines():
            if not line.startswith('8998:'):
                continue
            if not re.search(r'\buidrange ' + str(vk_uid) + '-' + str(vk_uid) + r'\b', line):
                raise RuntimeError('Unrecognized legacy priority 8998: not touching it')
            subprocess.run([IP, family, 'rule', 'del', 'pref', '8998'],
                           check=True, capture_output=True, timeout=8)


def sync():
    packages = app_uids()
    uids = sorted(set(packages.values()))
    iface = _physical_interface()
    if iface is None:
        raise RuntimeError('No confirmed physical network route; preserving existing rules')
    changed = sum(_update_rules(fam, uids, iface) for fam in ('-4', '-6'))
    _remove_legacy_vk(packages.get('com.vkontakte.android'))
    return {'interface': iface, 'apps': len(packages), 'uids': len(uids), 'changed': changed}
