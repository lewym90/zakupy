"""Lidl: gazetki z publicznego JSON platformy gazetek + odczyt obrazów stron przez Gemini (z weryfikacją kodem)."""
import hashlib
import json
import os
import re

import gemini
from gemini import Reader
from normalize import make_offer, money, parse_base_price, parse_pack, verify

LIST_URL = 'https://www.lidl.pl/c/nasze-gazetki/s10008614'
API = 'https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={slug}&region_id=0&region_code=0'
# domyślnie tylko gazetki spożywcze (katalogi, zabawki, alkohole mocne pomijamy)
DEFAULT_ONLY = r'^gazetka'

PROMPT = """Odczytaj ze zdjęcia strony gazetki Lidl WSZYSTKIE oferty spożywcze i drogeryjne. Zwróć wyłącznie JSON:
{"oferty":[{"nazwa":string,"marka":string|null,"opakowanie":string|null,"cena":number,"cena_przed":number|null,"cena_jednostkowa":string|null,"komplet_ilosc":number|null,"komplet_cena":number|null,"kolejna_taniej_proc":number|null,"warunek":string|null}]}
Zasady: przepisuj tylko to, co jest WYDRUKOWANE; nie zgaduj i nie licz. "cena" = cena promocyjna jednego opakowania w zł (liczba z kropką). "opakowanie" = gramatura lub pojemność dokładnie jak na stronie (np. "2 x 1,5 l", "500 g"). "cena_jednostkowa" = tekst ceny za kg/l/szt jak wydrukowano (np. "1 kg = 9,98"). Gdy jest promocja "N za X zł" wpisz komplet_ilosc=N i komplet_cena=X. Gdy "drugi/trzeci produkt X% taniej" wpisz kolejna_taniej_proc=X. "warunek" = np. "z aplikacją Lidl Plus", "limit 6 szt.". Pomiń ceny rabatu bez nazwy produktu, artykuły nie-spożywcze i nie-drogeryjne oraz reklamy. Gdy na stronie nie ma ofert zwróć {"oferty":[]}."""


def list_flyers(page, only=DEFAULT_ONLY):
    page.goto(LIST_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(4000)
    links = page.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')||'')")
    slugs = []
    for h in links:
        m = re.search(r'/l/pl/gazetki/([^/]+)/ar/0', h)
        if m and m.group(1) not in slugs and re.search(only, m.group(1)):
            slugs.append(m.group(1))
    return slugs


def get_flyer(ctx, slug):
    r = ctx.request.get(API.format(slug=slug), headers={'Referer': 'https://www.lidl.pl/', 'Origin': 'https://www.lidl.pl'}, timeout=60000)
    if not r.ok:
        raise RuntimeError(f'Lidl: API gazetki {slug} zwróciło {r.status}')
    return r.json()['flyer']


def map_item(it, valid_from, valid_to, section=''):
    """Jedna pozycja z odczytu -> oferta (albo None). Cała arytmetyka i kontrola jest tutaj, nie w modelu."""
    price = money(it.get('cena'))
    name = ' '.join(x for x in [(it.get('marka') or '').strip(), (it.get('nazwa') or '').strip()] if x)
    if not name or not price or price <= 0:
        return None
    pack = parse_pack(it.get('opakowanie') or '') or parse_pack(name)
    note = ''
    mode, need, pct = 'unit', 1, 0
    cond = (it.get('warunek') or '').strip()
    kn, kc = it.get('komplet_ilosc'), money(it.get('komplet_cena'))
    if isinstance(kn, (int, float)) and kn >= 2 and kc:
        mode, need, price = 'bundle', int(kn), kc
    elif isinstance(it.get('kolejna_taniej_proc'), (int, float)) and 0 < it['kolejna_taniej_proc'] <= 100:
        mode, need, pct = 'nth', 2, float(it['kolejna_taniej_proc'])
    if not pack:
        pack = dict(amount=1.0, unit='szt', conf='check', note='')
    raw = (it.get('cena_jednostkowa') or '').lower().replace('zł', '').replace('pln', '').strip()
    raw = re.sub(r'^(\d+(?:[.,]\d+)?)?\s*(kg|g|ml|l|szt)\.?\s*=\s*', lambda m: f"{m.group(1) or 1} {m.group(2)} ", raw)
    if mode != 'unit':
        conf, note = 'check', 'promocja wielosztukowa: sprawdź w gazetce'
    elif not parse_base_price(raw):
        conf, note = 'check', 'brak ceny jednostkowej, by potwierdzić odczyt'
    else:
        conf, note = verify(price, pack, raw)
    old = money(it.get('cena_przed')) or 0
    o = make_offer('Lidl', name, pack, price, old if old > price else 0, valid_from, valid_to, cond=cond, section=section, src='leaflet',
                   conf=conf, note=note, brand=(it.get('marka') or '').strip())
    o['mode'], o['need'], o['pct'] = mode, need, pct
    return o


def collect(page, ctx, key, cache_dir, max_pages=140, only=DEFAULT_ONLY, log=print):
    reader = Reader(key)
    offers, warns = [], []
    pages_read = 0
    fails = 0
    for slug in list_flyers(page, only):
        fl = get_flyer(ctx, slug)
        vf, vt = (fl.get('offerStartDate') or fl.get('startDate') or '')[:10], (fl.get('offerEndDate') or fl.get('endDate') or '')[:10]
        if not vt:
            warns.append(f'Lidl {slug}: brak dat ważności')
            continue
        for p in fl.get('pages', []):
            img = p.get('image')
            if not img:
                continue
            ck = os.path.join(cache_dir, hashlib.sha1((slug + '|' + img).encode()).hexdigest() + '.json')
            if os.path.exists(ck):
                items = json.load(open(ck))
            else:
                if pages_read >= max_pages:
                    warns.append(f'Lidl {slug}: limit stron na jedno uruchomienie ({max_pages}); reszta przy następnym')
                    break
                r = ctx.request.get(img, headers={'Referer': 'https://www.lidl.pl/'}, timeout=60000)
                if not r.ok:
                    warns.append(f'Lidl {slug} str. {p.get("number")}: obraz {r.status}')
                    continue
                try:
                    items = reader.read_json(r.body(), PROMPT).get('oferty', [])
                except gemini.GeminiError as e:
                    if e.status in (400, 401, 403, 404):
                        raise  # problem z kluczem/modelem: dalsze strony też się nie uda
                    fails += 1
                    warns.append(f'Lidl {slug} str. {p.get("number")}: {e}')
                    log(f'Lidl {slug} str. {p.get("number")}: BŁĄD {e}')
                    if fails >= 5:
                        raise
                    continue
                json.dump(items, open(ck, 'w'), ensure_ascii=False)
                pages_read += 1
                log(f'Lidl {slug} str. {p.get("number")}: {len(items)} ofert')
            for it in items:
                o = map_item(it, vf or vt, vt, section=slug)
                if o:
                    offers.append(o)
    return offers, warns
