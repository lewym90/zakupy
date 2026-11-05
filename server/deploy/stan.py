#!/usr/bin/env python3
"""Krótki raport o ostatnim odczycie. Nie wypisuje tokenu ani adresu. Uruchomienie: patrz KONTYNUACJA.md."""
import collections
import json
import os
import re
import subprocess

P = re.compile(r'cola|pepsi|żywiec|zywiec|mirinda|7up', re.I)
run = lambda *a: subprocess.run(a, capture_output=True, text=True).stdout
_k = re.search(r"KOD = '([^']+)'", open('/opt/zakupy-zbieracz/zbieracz/normalize.py', encoding='utf-8').read())
print('wersja kodu na serwerze:', _k.group(1) if _k else 'STARA')
print('stan:', run('systemctl', 'is-active', 'zakupy-zbieracz').strip(), '| kod z Biedronką:', 'tak' if os.path.exists('/opt/zakupy-zbieracz/zbieracz/biedronka.py') else 'NIE')
log = run('journalctl', '-u', 'zakupy-zbieracz', '--since', 'today', '--no-pager').splitlines()
print('przeczytane strony dziś:', sum(1 for x in log if re.search(r' str\. \d+: \d+ ofert$', x)))
for x in [x for x in log if re.search(r'ofert:|zapisano|BŁĄD|limit|JSON|duplikat|Dobór', x)][-8:]:
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
for o in [o for o in L if o['conf'] == 'check' and 'wg sklepu' in o.get('note', '')][:7] + [o for o in L if o['conf'] == 'check' and 'brak' in o.get('note', '')][:5]:
    print(' ', o['name'][:24], o['price'], '|', ' '.join(o.get('printed', '').split())[:64])
K = [o for o in d['offers'] if o['store'] == 'Kaufland']
print('Kaufland:', len(K), dict(collections.Counter(o['conf'] for o in K)))
print('działy:', dict(collections.Counter(o['section'] for o in K).most_common(30)))
print('notatki Pepsi:', [o.get('note', '')[:70] for o in L if o['conf'] == 'check' and P.search(o['name'])][:3])
B = [o for o in d['offers'] if o['store'] == 'Biedronka']
print('Biedronka:', len(B), dict(collections.Counter(o['conf'] for o in B)), 'gazetki:', dict(collections.Counter(o['section'][:30] for o in B)))
for o in [o for o in B if o['conf'] == 'ok'][:8]:
    print(' ', o['name'][:30], f"{o['need']}x{o['amount']}{o['unit']}", o['price'], o.get('promo', ''), 'do', o['until'], 'str', o.get('page'))
print('dobrane grafiki:', sum('thumb' in o for o in d['offers']), 'z', len(d['offers']))
print('kosz z zakupami:', [o['name'][:30] for o in d['offers'] if o.get('thumb') == 383][:12])
for n, v in collections.Counter(re.sub(r'[0-9.,]+', '#', o.get('note', ''))[:60] for o in B if o['conf'] == 'check').most_common(6):
    print(f'  {v} {n}')
for o in [o for o in B if o['conf'] == 'check'][:14]:
    print(' ', o['name'][:24], o['price'], '|', ' '.join(o.get('printed', '').split())[:64])
print('ceny od 100 zł:', [(o['name'][:26], o['price'], o['conf']) for o in d['offers'] if o['price'] >= 10000][:10])
