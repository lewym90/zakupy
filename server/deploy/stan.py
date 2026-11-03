#!/usr/bin/env python3
"""Krótki raport o ostatnim odczycie. Nie wypisuje tokenu ani adresu. Uruchomienie: patrz KONTYNUACJA.md."""
import collections
import json
import re
import subprocess

P = re.compile(r'cola|pepsi|żywiec|zywiec|mirinda|7up', re.I)
run = lambda *a: subprocess.run(a, capture_output=True, text=True).stdout
print('stan:', run('systemctl', 'is-active', 'zakupy-zbieracz').strip())
log = run('journalctl', '-u', 'zakupy-zbieracz', '--since', 'today', '--no-pager').splitlines()
print('przeczytane strony dziś:', sum(1 for x in log if re.search(r' str\. \d+: \d+ ofert$', x)))
for x in [x for x in log if re.search(r'ofert:|zapisano|BŁĄD|limit|JSON', x)][-8:]:
    print(' ', x.split(': ', 1)[-1][:110])
d = json.load(open('/var/www/zakupy-data/oferty.json'))
print('sklepy:', {k: (v.get('count'), v.get('check')) for k, v in d['stores'].items()})
L = [o for o in d['offers'] if o['store'] == 'Lidl']
print('Lidl:', len(L), 'nowy odczyt:', sum('printed' in o for o in L), dict(collections.Counter(o['conf'] for o in L)))
for n, v in collections.Counter(re.sub(r'[0-9.,]+', '#', o.get('note', ''))[:60] for o in L if o['conf'] == 'check').most_common(6):
    print(f'  {v} {n}')
for o in [o for o in L if P.search(o['name'])][:12]:
    print(o['conf'], o['name'][:30], f"{o['need']}x{o['amount']}{o['unit']}", o['price'], o.get('promo', ''), 'str', o.get('page'), '|', o.get('printed', '')[:50])
print('przykłady niepewnych:')
for o in [o for o in L if o['conf'] == 'check'][:10]:
    print(' ', o['name'][:26], o['price'], 'str', o.get('page'), '|', o.get('printed', '')[:62])
