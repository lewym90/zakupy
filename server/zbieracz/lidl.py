"""Lidl: gazetki z publicznego JSON platformy gazetek. Gemini tylko PRZEPISUJE tekst ze stron; wszystkie liczby liczy i sprawdza normalize.interpret."""
import hashlib
import json
import os
import re

import gemini
from gemini import Reader
from normalize import interpret, make_offer, money

LIST_URL = 'https://www.lidl.pl/c/nasze-gazetki/s10008614'
API = 'https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={slug}&region_id=0&region_code=0'
# domyślnie tylko gazetki spożywcze (katalogi, zabawki, alkohole mocne pomijamy)
DEFAULT_ONLY = r'^gazetka(?!.*katalog)'

FIELDS = '{"nazwa":string,"marka":string|null,"opakowanie":string|null,"cena":string,"cena_dodatkowa":string|null,"cena_przed":string|null,"cena_jednostkowa":string|null,"kaucja":string|null,"promocja":string|null,"warunek":string|null}'
PROMPT = """Jesteś czytnikiem tekstu (OCR). Przepisz ze zdjęcia strony gazetki Lidl WSZYSTKIE oferty spożywcze i drogeryjne. Zwróć wyłącznie JSON:
{"oferty":[""" + FIELDS + """]}
Zasady: przepisuj znak w znak to, co jest WYDRUKOWANE. Niczego nie licz, nie mnóż, nie przeliczaj, nie zgaduj i nie poprawiaj. Czego nie ma na stronie, to null. Każde pole to tekst z danego bloku oferty:
"opakowanie" = napis o ilości w całości, razem ze słowem takim jak Dwusztuk, np. "Dwusztuk 2 x 1 L", "500 g".
"cena" = największa wydrukowana cena oferty, np. "9,98".
"cena_dodatkowa" = pozostałe wydrukowane ceny bloku, np. "2 x 4,99 zł za butelkę", "cena poza promocją 10,15 zł/but.".
"cena_przed" = cena przekreślona lub sprzed obniżki.
"cena_jednostkowa" = napis ceny za kg/l/szt bez kaucji, np. "1 L = 4,99".
"kaucja" = napis o kaucji, np. "kaucja 1,00 zł".
"promocja" = napis promocji dokładnie jak wydrukowano, np. "2 + 1 gratis", "3 za 2", "3 za 9,99 zł", "drugi produkt -50%".
"warunek" = warunki, np. "aktywuj kupon w aplikacji Lidl Plus", "limit 6 szt.", "miksuj dowolnie".
Pomiń ceny rabatu bez nazwy produktu, artykuły nie-spożywcze i nie-drogeryjne oraz reklamy. Gdy na stronie nie ma ofert zwróć {"oferty":[]}."""


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
    """Jedna pozycja dosłownego odczytu -> oferta (albo None). Cała arytmetyka i kontrola jest w normalize.interpret."""
    brand, nazwa = (it.get('marka') or '').strip(), (it.get('nazwa') or '').strip()
    name = nazwa if brand and nazwa.lower().startswith(brand.lower()) else ' '.join(x for x in [brand, nazwa] if x)
    if not name:
        return None
    pack_t, extra, unit_t = [str(it.get(k) or '').strip() for k in ('opakowanie', 'cena_dodatkowa', 'cena_jednostkowa')]
    r = interpret(name, pack_t, it.get('cena'), extra, unit_t, it.get('kaucja') or '', it.get('promocja') or '')
    if not r:
        return None
    old = money(it.get('cena_przed')) or 0
    pack = dict(amount=r['amount'], unit=r['unit'])
    o = make_offer('Lidl', name, pack, r['price'], old if old > r['price'] and r['need'] == 1 else 0, valid_from, valid_to,
                   cond=(it.get('warunek') or '').strip(), section=section, src='leaflet', conf=r['conf'], note=r['note'], brand=(it.get('marka') or '').strip())
    o['mode'], o['need'] = r['mode'], r['need']
    for k in ('pay', 'pct'):
        if k in r:
            o[k] = r[k]
    if r['promo']:
        o['promo'] = r['promo']
    if r['deposit']:
        o['deposit'] = r['deposit']
    o['printed'] = ' · '.join(x for x in [pack_t, extra, unit_t] if x)[:140]
    return o


def _batch_prompt():
    rules = 'Zasady:' + PROMPT.split('Zasady:', 1)[1]
    return ('Jesteś czytnikiem tekstu (OCR). Przepisz ze zdjęć kolejnych stron gazetki Lidl (obrazy są w kolejności 1, 2, 3...) WSZYSTKIE oferty spożywcze i drogeryjne. Zwróć wyłącznie JSON:\n'
            '{"strony":[{"numer":1,"oferty":[...]},{"numer":2,"oferty":[...]}]}\n'
            'gdzie "numer" to kolejność obrazu w tej wiadomości, a każda oferta ma pola:\n'
            + FIELDS + '\n' + rules)


def collect(page, ctx, key, cache_dir, max_pages=140, only=DEFAULT_ONLY, log=print, batch=None):
    batch = batch or int(os.environ.get('LIDL_BATCH', '3'))
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
        items_by_page, todo = {}, []
        for p in fl.get('pages', []):
            img = p.get('image')
            if not img:
                continue
            # bez adresu obrazu: ten sam adres strony potrafi się zmienić i wtedy całą gazetkę czytalibyśmy od nowa
            ck = os.path.join(cache_dir, hashlib.sha1(f"{slug}|{p.get('number')}|v3".encode()).hexdigest() + '.json')
            old = os.path.join(cache_dir, hashlib.sha1((slug + '|' + img + '|v3').encode()).hexdigest() + '.json')  # wcześniejszy klucz
            if not os.path.exists(ck) and os.path.exists(old):
                ck = old
            if os.path.exists(ck):
                with open(ck, encoding='utf-8') as f:
                    items_by_page[p.get('number')] = json.load(f)
            else:
                todo.append((p.get('number'), img, ck))
        if len(todo) > max_pages - pages_read:
            warns.append(f'Lidl {slug}: limit stron na jedno uruchomienie ({max_pages}); reszta przy następnym')
            todo = todo[:max(0, max_pages - pages_read)]
        for i in range(0, len(todo), batch):
            chunk, imgs = [], []
            for num, img, ck in todo[i:i + batch]:
                r = ctx.request.get(img, headers={'Referer': 'https://www.lidl.pl/'}, timeout=60000)
                if not r.ok:
                    warns.append(f'Lidl {slug} str. {num}: obraz {r.status}')
                    continue
                chunk.append((num, ck)); imgs.append(r.body())
            if not imgs:
                continue
            try:
                res = reader.read_json(imgs, _batch_prompt())
            except gemini.DailyQuota:
                warns.append('Lidl: dzienne limity Gemini wyczerpane; reszta stron zostanie doczytana przy następnym uruchomieniu')
                log('Lidl: dzienne limity Gemini wyczerpane, kończę na tym uruchomieniu')
                break
            except gemini.GeminiError as e:
                if e.status in (400, 401, 403, 404):
                    raise
                fails += 1
                warns.append(f'Lidl {slug} str. {[c[0] for c in chunk]}: {e}')
                log(f'Lidl {slug} str. {[c[0] for c in chunk]}: BŁĄD {e}')
                if fails >= 5:  # przeciążenie po stronie Google: kończymy tę turę, zachowując to, co już przeczytane
                    warns.append('Lidl: za dużo błędów Gemini; reszta stron zostanie doczytana przy następnym uruchomieniu')
                    break
                continue
            got = {int(x.get('numer')): x.get('oferty') or [] for x in (res.get('strony') or []) if isinstance(x, dict) and str(x.get('numer', '')).isdigit()}
            for idx, (num, ck) in enumerate(chunk, 1):
                if idx not in got:
                    warns.append(f'Lidl {slug} str. {num}: brak w odpowiedzi modelu')
                    continue
                items_by_page[num] = got[idx]
                with open(ck, 'w', encoding='utf-8') as f:
                    json.dump(got[idx], f, ensure_ascii=False)
                pages_read += 1
                log(f'Lidl {slug} str. {num}: {len(got[idx])} ofert')
        for num in sorted(k for k in items_by_page if k is not None):
            for it in items_by_page[num]:
                o = map_item(it, vf or vt, vt, section=slug)
                if o:
                    o['page'] = num
                    offers.append(o)
    # ta sama oferta bywa w gazetce dwa razy: gdy jedno miejsce jest potwierdzone, niepewny duplikat nie jest potrzebny
    sure = {o['name'] for o in offers if o['conf'] == 'ok'}
    return [o for o in offers if o['conf'] != 'check' or o['name'] not in sure], warns
