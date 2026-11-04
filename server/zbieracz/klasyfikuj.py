"""Dobór grafiki i kategorii po nazwie oferty. Gemini wybiera tylko numer obrazka i kategorię; nie dotyka cen ani ilości.
Wyniki są zapamiętane, więc każda nazwa kosztuje jedno zapytanie raz. Błąd lub limit niczego nie psuje: aplikacja ma własne reguły."""
import json
import os
import re

import gemini

LABELS = json.load(open(os.path.join(os.path.dirname(__file__), 'produkty.json'), encoding='utf-8'))
CATS = ['ryby', 'wedliny', 'mieso', 'nabial', 'warzywa', 'pieczywo', 'mrozonki', 'napoje', 'kawa', 'alkohol', 'slodycze', 'spizarnia', 'chemia', 'zwierzeta', 'inne']
BATCH = 120


def key_of(name):
    return re.sub(r'\s+', ' ', name.lower()).strip()


def prompt(names):
    return ('Dobierasz obrazek do produktów z polskich gazetek sklepowych. Lista obrazków (numer: opis):\n'
            + '\n'.join(f'{i}: {x}' for i, x in enumerate(LABELS))
            + '\n\nDla każdej nazwy wybierz obrazek przedstawiający ten sam rodzaj produktu i kategorię z listy: ' + ', '.join(CATS) + '.\n'
            'Patrz na to, czym produkt jest, a nie na pojedyncze słowa. Płatki hydrożelowe pod oczy to kosmetyk, a nie płatki śniadaniowe; mrożona mieszanka chińska to mrożonka; prosciutto to wędlina; marka nic nie znaczy. '
            'Gdy nic nie pasuje, wybierz najbliższy rodzaj; ostatni numer to kosz z zakupami, użyj go tylko w ostateczności.\n'
            'Zwróć wyłącznie JSON: {"w":[{"i":numer_nazwy,"g":numer_obrazka,"k":"kategoria"}]}\nNazwy:\n'
            + '\n'.join(f'{i}: {n}' for i, n in enumerate(names)))


def classify(offers, state_dir, key, log=print, reader=None, max_batches=12):
    path = os.path.join(state_dir, 'klasyfikacja.json')
    try:
        known = json.load(open(path, encoding='utf-8'))
    except Exception:  # noqa: BLE001
        known = {}
    todo = sorted({o['name'] for o in offers if key_of(o['name']) not in known})
    if todo and key:
        r = reader or gemini.Reader(key, pause=float(os.environ.get('ZBIERACZ_PAUSE', '13')))
        for b in range(min(max_batches, (len(todo) + BATCH - 1) // BATCH)):
            names = todo[b * BATCH:(b + 1) * BATCH]
            try:
                res = r.read_json([], prompt(names))
            except gemini.GeminiError as e:
                log('Dobór grafik przerwany:', str(e)[:120])
                break
            for x in res.get('w') or []:
                if not isinstance(x, dict):
                    continue
                i, g, k = x.get('i'), x.get('g'), x.get('k')
                if isinstance(i, int) and 0 <= i < len(names) and isinstance(g, int) and 0 <= g < len(LABELS) and k in CATS:
                    known[key_of(names[i])] = [g, k]
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(known, f, ensure_ascii=False)
            os.replace(tmp, path)
    n = 0
    for o in offers:
        v = known.get(key_of(o['name']))
        if v:
            o['thumb'], o['aiCat'] = v
            n += 1
    log('Dobór grafik:', n, 'z', len(offers), 'ofert')
    return n
