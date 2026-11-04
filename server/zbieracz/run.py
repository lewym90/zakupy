"""Uruchamiane przez systemd (zakupy-zbieracz.service). Zbiera oferty ze sklepów i zapisuje JEDEN plik oferty.json.
Zasady: źródła są niezależne (awaria jednego nie psuje drugiego); gdy źródło zawiedzie, zostają jego poprzednie oferty
z ostrzeżeniem; nie omijamy blokad ani CAPTCHA; zapis atomowy; codzienne archiwum (do analizy cykli promocji)."""
import datetime as dt
import gzip
import json
import os
import shutil
import sys
import tempfile
import traceback

OUT = os.environ.get('ZBIERACZ_OUT', '/var/www/zakupy-data')
STATE = os.environ.get('ZBIERACZ_STATE', '/var/lib/zakupy-zbieracz')
sys.path.insert(0, os.path.dirname(__file__))


def log(*a):
    print(dt.datetime.now().strftime('%H:%M:%S'), *a, flush=True)


def load_prev():
    try:
        return json.load(open(os.path.join(OUT, 'oferty.json')))
    except Exception:
        return {'offers': [], 'stores': {}}


def main():
    from playwright.sync_api import sync_playwright
    import kaufland
    import lidl
    import biedronka
    today = dt.date.today()
    prev = load_prev()
    stores, all_offers = {}, []
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    cache_dir = os.path.join(STATE, 'cache'); os.makedirs(cache_dir, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(locale='pl-PL', viewport={'width': 1366, 'height': 900})
        page = ctx.new_page()
        jobs = [('Kaufland', lambda: kaufland_all(kaufland, page, today))]
        if key:
            jobs.append(('Lidl', lambda: lidl.collect(page, ctx, key, cache_dir, max_pages=int(os.environ.get('LIDL_MAX_PAGES', '140')), log=log)))
            jobs.append(('Biedronka', lambda: biedronka.collect(page, ctx, key, cache_dir, max_pages=int(os.environ.get('LIDL_MAX_PAGES', '140')), log=log)))
        else:
            stores['Lidl'] = {'ok': False, 'at': now, 'msg': 'Brak klucza Gemini (GEMINI_API_KEY w /etc/zakupy-zbieracz.env), więc gazetki Lidla nie są czytane.'}
        for name, fn in jobs:
            try:
                offers, warns = fn()
                if not offers:
                    raise RuntimeError('zero ofert')
                if name in ('Lidl', 'Biedronka'):  # niedoczytane strony zostają z poprzedniego odczytu, zamiast znikać
                    read = {(o['section'], o.get('page')) for o in offers}
                    offers += [o for o in prev.get('offers', []) if o['store'] == name and 'printed' in o and o['until'] >= today.isoformat() and (o['section'], o.get('page')) not in read]
                stores[name] = {'ok': True, 'at': now, 'count': len(offers), 'check': sum(1 for o in offers if o['conf'] == 'check'), 'msg': '; '.join(warns[:5])}
                all_offers += offers
                log(name, 'ofert:', len(offers), 'do sprawdzenia:', stores[name]['check'])
            except Exception as e:  # noqa: BLE001
                log(name, 'BŁĄD:', e)
                traceback.print_exc()
                old = [o for o in prev.get('offers', []) if o['store'] == name and o['until'] >= today.isoformat()]
                stores[name] = {'ok': False, 'at': prev.get('stores', {}).get(name, {}).get('at', now), 'count': len(old), 'msg': f'{e}'[:300] + (' (zostały poprzednie oferty)' if old else '')}
                all_offers += old
        browser.close()

    if 'Lidl' in stores and not stores['Lidl']['ok'] and not key:
        old = [o for o in prev.get('offers', []) if o['store'] == 'Lidl' and o['until'] >= today.isoformat()]
        all_offers += old
        stores['Lidl']['count'] = len(old)

    uniq = {}
    for o in all_offers:
        uniq[o['id']] = o
    data = {'v': 1, 'updated': now, 'stores': stores, 'offers': sorted(uniq.values(), key=lambda o: (o['store'], o['section'], o['name']))}
    os.makedirs(OUT, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=OUT, suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(OUT, 'oferty.json'))
    arch = os.path.join(STATE, 'archiwum'); os.makedirs(arch, exist_ok=True)
    with gzip.open(os.path.join(arch, today.isoformat() + '.json.gz'), 'wt', encoding='utf-8') as g:
        json.dump(data, g, ensure_ascii=False)
    log('zapisano', len(data['offers']), 'ofert')
    return 0 if any(s['ok'] for s in stores.values()) else 1


def kaufland_all(kaufland, page, today):
    offers, warns = kaufland.collect(page, kaufland.URL_CURRENT, today)
    try:  # oferta na następny tydzień (jeśli już jest); brak to nie błąd
        o2, w2 = kaufland.collect(page, kaufland.URL_NEXT, today)
        offers += o2; warns += w2
    except Exception as e:  # noqa: BLE001
        warns.append('następny tydzień: ' + str(e)[:100])
    return offers, warns


if __name__ == '__main__':
    sys.exit(main())
