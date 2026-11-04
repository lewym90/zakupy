"""Biedronka: publiczne gazetki. Strony to obrazy z leaflet-api, więc jak w Lidlu Gemini tylko przepisuje tekst,
a liczy i sprawdza normalize.interpret. Przy blokadzie lub CAPTCHA kończymy z komunikatem i niczego nie omijamy."""
import datetime as dt
import hashlib
import json
import os
import re

import gemini
from gemini import Reader
from lidl import FIELDS, PROMPT, drop_dupes, map_item

LIST_URL = 'https://www.biedronka.pl/pl/gazetki'
ONLY = r'codziennie|festiwal'  # gazetki spożywcze; home, zabawki, wyprzedaż i Good To Go pomijamy
FIELDS_B = FIELDS.replace('"warunek":string|null}', '"warunek":string|null,"wazne":string|null}')
EXTRA = '\n"wazne" = napis o okresie obowiązywania oferty, np. "Oferta od czwartku 29.10 do środy 04.11", jeśli jest na stronie.'


def batch_prompt():
    rules = 'Zasady:' + PROMPT.split('Zasady:', 1)[1].replace('gazetki Lidl', 'gazetki Biedronki')
    return ('Jesteś czytnikiem tekstu (OCR). Przepisz ze zdjęć kolejnych stron gazetki Biedronki (obrazy są w kolejności 1, 2, 3...) WSZYSTKIE oferty spożywcze i drogeryjne. Zwróć wyłącznie JSON:\n'
            '{"strony":[{"numer":1,"oferty":[...]},{"numer":2,"oferty":[...]}]}\n'
            'gdzie "numer" to kolejność obrazu w tej wiadomości, a każda oferta ma pola:\n' + FIELDS_B + '\n' + rules + EXTRA)


def list_flyers(page, only=ONLY):
    page.goto(LIST_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(4000)
    if re.search(r'just a moment|captcha|attention required|access denied', page.title(), re.I):
        raise RuntimeError('Biedronka: blokada strony; niczego nie omijam.')
    links = page.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.href)")
    out = []
    for h in links:
        h = h.split('#')[0]
        if '/pl/press,' in h and h not in out and re.search(only, h.rsplit('title,', 1)[-1]):
            out.append(h)
    return out


def valid_from_slug(url, today):
    """'...oferta-od-3-11' -> data początku. Rok z bieżącej daty; koniec: 6 dni później, o ile strona nie mówi inaczej."""
    m = re.search(r'od-(\d{1,2})-(\d{1,2})(?:\D|$)', url)
    if not m:
        return None
    try:
        d = dt.date(today.year, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return d.replace(year=d.year + 1) if (today - d).days > 300 else d


def pages_of(page, url):
    """Otwiera gazetkę jak przeglądarka i zwraca listę (numer, adres obrazu) z danych leaflet-api."""
    got = []

    def resp(r):
        if 'leaflet-api' in r.url and '/leaflets/' in r.url:
            try:
                got.append(r.json())
            except Exception:  # noqa: BLE001
                pass
    page.on('response', resp)
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(6000)
    page.remove_listener('response', resp)
    for j in got:
        imgs = [(int(p.get('page', i)) + 1, p.get('image')) for i, p in enumerate(j.get('images_mobile') or []) if p.get('image')]
        if imgs:
            return imgs
    return []


def collect(page, ctx, key, cache_dir, max_pages=140, log=print, batch=None, today=None):
    batch = batch or int(os.environ.get('LIDL_BATCH', '3'))
    today = today or dt.date.today()
    reader = Reader(key)
    offers, warns = [], []
    read, fails, stop = 0, 0, False
    for url in list_flyers(page):
        slug = url.rsplit('title,', 1)[-1]
        start = valid_from_slug(url, today)
        if not start:
            warns.append(f'Biedronka {slug}: brak daty w adresie')
            continue
        pages = pages_of(page, url)
        if not pages:
            warns.append(f'Biedronka {slug}: brak stron')
            continue
        items, todo = {}, []
        for num, img in pages:
            ck = os.path.join(cache_dir, hashlib.sha1(f'biedronka|{slug}|{num}|v1'.encode()).hexdigest() + '.json')
            if os.path.exists(ck):
                with open(ck, encoding='utf-8') as f:
                    items[num] = json.load(f)
            else:
                todo.append((num, img, ck))
        for i in range(0, 0 if stop else len(todo), batch):
            if read >= max_pages or stop:
                break
            chunk, imgs = [], []
            for num, img, ck in todo[i:i + batch]:
                r = ctx.request.get(img, headers={'Referer': 'https://www.biedronka.pl/'}, timeout=60000)
                if r.ok:
                    chunk.append((num, ck)); imgs.append(r.body())
                else:
                    warns.append(f'Biedronka {slug} str. {num}: obraz {r.status}')
            if not imgs:
                continue
            try:
                res = reader.read_json(imgs, batch_prompt())
            except gemini.DailyQuota:
                warns.append('Biedronka: dzienne limity Gemini wyczerpane; reszta przy następnym uruchomieniu')
                stop = True
                break
            except gemini.GeminiError as e:
                if e.status in (400, 401, 403, 404):
                    raise
                fails += 1
                warns.append(f'Biedronka {slug} str. {[c[0] for c in chunk]}: {e}')
                log(f'Biedronka {slug} str. {[c[0] for c in chunk]}: BŁĄD {e}')
                stop = fails >= 5
                continue
            got = {int(x.get('numer')): x.get('oferty') or [] for x in (res.get('strony') or []) if isinstance(x, dict) and str(x.get('numer', '')).isdigit()}
            for idx, (num, ck) in enumerate(chunk, 1):
                if idx in got:
                    items[num] = got[idx]
                    with open(ck, 'w', encoding='utf-8') as f:
                        json.dump(got[idx], f, ensure_ascii=False)
                    read += 1
                    log(f'Biedronka {slug} str. {num}: {len(got[idx])} ofert')
        for num in sorted(items):
            for it in items[num]:
                if not isinstance(it, dict):
                    continue
                vf, vt = valid(it.get('wazne'), start, today)
                if vt < today.isoformat():
                    continue
                o = map_item(it, vf, vt, section=slug, store='Biedronka')
                if o:
                    o['page'] = num
                    o['link'] = f'{url}#page={num}'
                    offers.append(o)
    return drop_dupes(offers), warns


def valid(text, start, today):
    from normalize import parse_valid
    a, b = parse_valid(re.sub(r'(\d{1,2}\.\d{1,2})(?![.\d])', r'\1.', text or ''), today)
    return (a, b) if b else (start.isoformat(), (start + dt.timedelta(days=6)).isoformat())
