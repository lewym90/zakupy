"""Lidl: gazetki z publicznego JSON platformy gazetek + odczyt obrazów stron przez Gemini (z weryfikacją kodem)."""
import hashlib
import json
import os
import re

import gemini
from gemini import Reader
from normalize import apply_multibuy, make_offer, money, parse_base_price, parse_multibuy, parse_pack, verify, verify_any

LIST_URL = 'https://www.lidl.pl/c/nasze-gazetki/s10008614'
API = 'https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={slug}&region_id=0&region_code=0'
# domyślnie tylko gazetki spożywcze (katalogi, zabawki, alkohole mocne pomijamy)
DEFAULT_ONLY = r'^gazetka(?!.*katalog)'

PROMPT = """Odczytaj ze zdjęcia strony gazetki Lidl WSZYSTKIE oferty spożywcze i drogeryjne. Zwróć wyłącznie JSON:
{"oferty":[{"nazwa":string,"marka":string|null,"opakowanie":string|null,"cena":number,"cena_przed":number|null,"cena_jednostkowa":string|null,"komplet_ilosc":number|null,"komplet_platnych":number|null,"komplet_cena":number|null,"kolejna_taniej_proc":number|null,"promocja":string|null,"warunek":string|null}]}
Zasady: przepisuj tylko to, co jest WYDRUKOWANE; nie zgaduj i nie licz. "cena" = cena promocyjna jednego opakowania w zł (liczba z kropką). "opakowanie" = gramatura lub pojemność dokładnie jak na stronie (np. "2 x 1,5 l", "500 g"). "cena_jednostkowa" = tekst ceny za kg/l/szt jak wydrukowano (np. "1 kg = 9,98"). Promocje wielosztukowe: "N za X zł" -> komplet_ilosc=N, komplet_cena=X; "3 w cenie 2" / "3 za 2" / "2+1 gratis" / "kup 2, trzecia gratis" -> komplet_ilosc=3 (ile sztuk dostajesz), komplet_platnych=2 (za ile płacisz), a "cena" to cena JEDNEJ sztuki. "promocja" = napis promocji dokładnie jak wydrukowano (np. "3 za 2", "2+1 gratis"), albo null. Gdy "drugi/trzeci produkt X% taniej" wpisz kolejna_taniej_proc=X. "warunek" = np. "z aplikacją Lidl Plus", "limit 6 szt.". Pomiń ceny rabatu bez nazwy produktu, artykuły nie-spożywcze i nie-drogeryjne oraz reklamy. Gdy na stronie nie ma ofert zwróć {"oferty":[]}."""


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
    cond = (it.get('warunek') or '').strip()
    kn, kp, kc = it.get('komplet_ilosc'), it.get('komplet_platnych'), money(it.get('komplet_cena'))
    mb = None
    if isinstance(kn, (int, float)) and kn >= 2 and isinstance(kp, (int, float)) and 1 <= kp < kn:
        mb = {'need': int(kn), 'pay': int(kp)}
    elif isinstance(kn, (int, float)) and kn >= 2 and kc:
        mb = {'need': int(kn), 'total': kc}
    elif isinstance(it.get('kolejna_taniej_proc'), (int, float)) and 0 < it['kolejna_taniej_proc'] <= 100:
        mb = {'need': 2, 'pct': float(it['kolejna_taniej_proc'])}
    else:
        mb = parse_multibuy(it.get('promocja') or '')
    if not pack:
        pack = dict(amount=1.0, unit='szt', conf='check', note='')
    raw = (it.get('cena_jednostkowa') or '').lower().replace('zł', '').replace('pln', '').strip()
    raw = re.sub(r'^(\d+(?:[.,]\d+)?)?\s*(kg|g|ml|l|szt)\.?\s*=\s*', lambda m: f"{m.group(1) or 1} {m.group(2)} ", raw)
    old = money(it.get('cena_przed')) or 0
    if mb:
        # możliwe ceny jednej sztuki: zwykła (cena) albo promocyjna; wystarczy, że jedna zgadza się z ceną jednostkową ze strony
        cands = [price]
        if 'total' in mb:
            cands.append(round(mb['total'] / mb['need']))
        if 'pay' in mb:
            cands.append(round(price * mb['pay'] / mb['need']))
        if 'pct' in mb:
            cands.append(round(price * (1 - mb['pct'] / 100)))
        conf, note = verify_any(cands, pack, raw)
    elif not parse_base_price(raw):
        conf, note = 'check', 'brak ceny jednostkowej, by potwierdzić odczyt'
    else:
        conf, note = verify(price, pack, raw)
    o = make_offer('Lidl', name, pack, price, old if old > price and not mb else 0, valid_from, valid_to, cond=cond, section=section, src='leaflet',
                   conf=conf, note=note, brand=(it.get('marka') or '').strip())
    if mb:
        apply_multibuy(o, mb, price)
        o['promo'] = (it.get('promocja') or '').strip()[:40]
    return o



def _batch_prompt():
    rules = 'Zasady:' + PROMPT.split('Zasady:', 1)[1]
    return ('Odczytaj ze zdjęć kolejnych stron gazetki Lidl (obrazy są w kolejności 1, 2, 3...) WSZYSTKIE oferty spożywcze i drogeryjne. Zwróć wyłącznie JSON:\n'
            '{"strony":[{"numer":1,"oferty":[...]},{"numer":2,"oferty":[...]}]}\n'
            'gdzie "numer" to kolejność obrazu w tej wiadomości, a każda oferta ma pola:\n'
            '{"nazwa":string,"marka":string|null,"opakowanie":string|null,"cena":number,"cena_przed":number|null,"cena_jednostkowa":string|null,"komplet_ilosc":number|null,"komplet_platnych":number|null,"komplet_cena":number|null,"kolejna_taniej_proc":number|null,"promocja":string|null,"warunek":string|null}\n'
            + rules)


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
            ck = os.path.join(cache_dir, hashlib.sha1((slug + '|' + img + '|v2').encode()).hexdigest() + '.json')
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
                if fails >= 5:
                    raise
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
    return offers, warns
