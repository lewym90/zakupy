import re
# Test w przeglądarce (rozmiar telefonu). Użycie: python3 test/e2e.py <katalog_zrzutów>
import sys, subprocess, time, os, json
from playwright.sync_api import sync_playwright
VER = re.search(r"VERSION = '([^']+)'", open('js/app.js').read()).group(1)
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/shots'; os.makedirs(OUT, exist_ok=True)
srv = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--bind', '127.0.0.1'], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errs = []; fails = []
def check(cond, msg):
    if not cond: fails.append(msg); print('FAIL', msg)
    else: print('ok  ', msg)
try:
  with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, locale='pl-PL')
    pg = ctx.new_page()
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('http://127.0.0.1:8765/'); pg.wait_for_selector('.tab')
    pg.screenshot(path=f'{OUT}/01-start-pusty.png')

    def add_receipt(store, date, lines, declared=None, shot=None):
        pg.click('[data-tab="paragony"]'); pg.click('[data-act="new"]'); pg.wait_for_selector('.sheet .f-name')
        pg.click(f'[data-ea="store"][data-s="{store}"]'); pg.fill('.f-date', date)
        for i, (n, q, u, t, reg) in enumerate(lines):
            if i: pg.click('[data-ea="add"]')
            row = pg.locator('.ln').nth(i)
            row.locator('.f-name').fill(n); row.locator('.f-qty').fill(q); row.locator('.f-unit').select_option(u); row.locator('.f-total').fill(t)
            if reg:
                row.locator('[data-ea="reg"]').click(); pg.locator('.ln').nth(i).locator('.f-reg').fill(reg)
        if declared: pg.fill('.f-decl', declared)
        if shot: pg.screenshot(path=f'{OUT}/{shot}')
        return pg.inner_text('.foot .stat')

    st = add_receipt('Lidl', '2026-11-01', [('Karkówka wieprzowa', '1,2', 'kg', '28,80', ''), ('Mleko UHT 3,2%', '2', 'szt', '6,98', ''), ('Kawa mielona', '1', 'szt', '24,99', '')], '60,00', '02-edytor-roznica.png')
    check('droższe o 0,77' in st.replace(' ', ' '), 'różnica sumy wykryta: ' + st)
    check(pg.locator('.ln-cat').nth(0).inner_text() == '🥩' and pg.locator('.ln-cat').nth(1).inner_text() == '🥛' and pg.locator('.ln-cat').nth(2).inner_text() == '☕', 'auto-kategorie 🥩🥛☕')
    check('Zapisz mimo różnicy' in pg.inner_text('[data-ea="save"]'), 'przycisk ostrzega o różnicy')
    pg.fill('.f-decl', '60,77'); st = pg.inner_text('.foot .stat'); check('✓' in st, 'suma zgodna po poprawce')
    pg.click('[data-ea="save"]'); pg.wait_for_selector('.sheet', state='detached')

    add_receipt('Biedronka', '2026-10-20', [('Karkówka wieprzowa', '1', 'kg', '24,00', '30,00')], '24,00')
    pg.click('[data-ea="save"]'); pg.wait_for_selector('.sheet', state='detached')
    add_receipt('Biedronka', '2026-10-27', [('Karkówka wieprzowa', '1', 'kg', '25,00', '')])
    pg.click('[data-ea="save"]'); pg.wait_for_selector('.sheet', state='detached')
    add_receipt('Kaufland', '2026-11-02', [('Rabat kuponowy', '1', 'szt', '-3,00', ''), ('Ser żółty gouda', '0,4', 'kg', '16,00', '')])
    pg.click('[data-ea="save"]'); pg.wait_for_selector('.sheet', state='detached')

    pg.click('[data-tab="start"]'); pg.wait_for_selector('.tape')
    check('Listopad' in pg.inner_text('.mnav'), 'miesiąc Listopad')
    spent = pg.inner_text('.tape .big').replace(' ', ' ')
    check(spent == '73,77 zł', 'wydane w listopadzie = 60,77 + 13,00 = 73,77 (jest: ' + spent + ')')
    pg.screenshot(path=f'{OUT}/03-start.png')

    pg.click('[data-tab="paragony"]'); pg.screenshot(path=f'{OUT}/04-paragony.png')
    pg.click('[data-tab="cennik"]'); pg.wait_for_selector('.item'); pg.screenshot(path=f'{OUT}/05-cennik.png')
    pg.click('[data-act="product"] >> nth=0'); pg.wait_for_selector('.spark'); pg.screenshot(path=f'{OUT}/06-produkt.png')
    body = pg.inner_text('.sheet').replace(' ', ' ')
    check('Liczba zakupów\n3' in body.replace('\t', ''), 'karkówka: 3 zakupy')
    check('24,00 zł/kg' in body, 'cena za kg 24,00 widoczna (najniżej)')
    pg.click('.sheet [data-close]')

    pg.click('[data-tab="okazje"]'); pg.click('[data-act="newoffer"]'); pg.wait_for_selector('.o-name')
    pg.click('[data-s="Kaufland"]'); pg.fill('.o-name', 'Karkówka wieprzowa'); pg.fill('.o-price', '19,99'); pg.fill('.o-cond', 'z kartą, limit 3 kg')
    pv = pg.inner_text('#prev'); check('Najniższa cena z Waszych paragonów' in pv, 'okazja 19,99 vs min 24,00 = najniższa: ' + pv.replace('\n', ' '))
    pg.screenshot(path=f'{OUT}/07-okazja-edytor.png'); pg.click('[data-oa="save"]'); pg.wait_for_selector('.sheet', state='detached')
    pg.click('[data-act="newoffer"]'); pg.fill('.o-name', 'Pomidory'); pg.fill('.o-price', '7,99'); pg.fill('.o-amount', '1'); pg.select_option('.o-unit', 'kg')
    pg.click('[data-oa="save"]'); pg.wait_for_selector('.sheet', state='detached')
    pg.screenshot(path=f'{OUT}/08-okazje.png')
    check(pg.locator('.offer').count() == 2, 'dwie okazje na liście')

    # porównanie: cola w Lidlu (3 × 1,5 l za 9,99) i w Kauflandzie (2 × 2 l za 13,98)
    def add_offer(store, name, price, need, amount, unit):
        pg.click('[data-tab="okazje"]'); pg.click('[data-act="newoffer"]'); pg.wait_for_selector('.sheet .o-name')
        pg.click(f'.sheet [data-s="{store}"]'); pg.fill('.o-name', name); pg.click('.sheet [data-mode="bundle"]')
        pg.fill('.o-need', str(need)); pg.fill('.o-price', price); pg.fill('.o-amount', amount); pg.select_option('.o-unit', unit)
        return pg.inner_text('#prev')
    add_offer('Lidl', 'Coca-Cola', '9,99', 3, '1,5', 'l'); pg.screenshot(path=f'{OUT}/08b-edytor-promocji.png')
    check('2,22' in pg.inner_text('#prev') and '4,5 l' in pg.inner_text('#prev') and '9,99' in pg.inner_text('#prev'), 'Lidl: komplet 9,99, zawartość 4,5 l, 2,22 zł za 1 l')
    pg.click('[data-oa="save"]'); pg.wait_for_selector('.sheet', state='detached')
    prev = add_offer('Kaufland', 'Coca-Cola', '13,98', 2, '2', 'l')
    check('3,50' in prev and '2. z 2' in prev and 'najtaniej Lidl' in prev, 'Kaufland: 3,50 zł/l, 2. z 2, najtaniej Lidl')
    pg.click('[data-oa="save"]'); pg.wait_for_selector('.sheet', state='detached')
    pg.click('[data-act="omode"][data-m="porownanie"]'); pg.wait_for_selector('.cmp')
    rows = pg.locator('.cmp-row'); check(rows.count() == 2, 'porównanie: dwa wiersze')
    check('Lidl' in rows.nth(0).inner_text() and '2,22' in rows.nth(0).inner_text(), 'porównanie: Lidl pierwszy')
    check('+58%' in rows.nth(1).inner_text(), 'porównanie: Kaufland +58%')
    pg.screenshot(path=f'{OUT}/08c-porownanie.png', full_page=True)
    pg.click('[data-act="omode"][data-m="lista"]')

    pg.click('[data-tab="budzet"]'); pg.fill('#limit', '3000'); pg.click('[data-act="savelimit"]')
    pg.click('[data-act="catlimit"][data-c="mieso"]'); pg.fill('#cl', '60'); pg.click('[data-cl="save"]')
    pg.screenshot(path=f'{OUT}/09-budzet.png', full_page=True)
    pg.click('[data-tab="start"]'); pg.screenshot(path=f'{OUT}/10-start-limit.png')
    check('zostało' in pg.inner_text('.tape .of'), 'limit: zostało …')

    pg.click('[data-tab="ustawienia"]')
    check(VER in pg.inner_text('#view'), 'ustawienia pokazują wersję')
    pg.fill('#gkey', 'TEST-KEY'); pg.fill('#gmodel', 'gemini-2.5-flash'); pg.click('[data-act="savegem"]'); pg.wait_for_function("document.getElementById('view').innerText.includes('Zapisany ✓')")
    check('Zapisany' in pg.inner_text('#view'), 'klucz zapisany')
    pg.click('[data-act="upd"]'); pg.wait_for_function("document.getElementById('upd-status').textContent.includes('najnowsz')", timeout=8000)
    check(pg.inner_text('#upd-latest') == VER, 'najnowsza wersja z serwera = ' + VER)
    pg.screenshot(path=f'{OUT}/09b-ustawienia.png', full_page=True)
    pg.click('[data-tab="start"]')

    # oferty z serwera (atrapa pliku): pobranie, lista, porównanie, wyszukiwanie, znacznik "do sprawdzenia", tylko do odczytu
    import datetime as _dt
    until = (_dt.date.today() + _dt.timedelta(days=3)).isoformat()
    mk = lambda i, st, n, pr, am, conf: {'id': i, 'store': st, 'name': n, 'brand': '', 'price': pr, 'old': 0, 'amount': am, 'unit': 'g', 'mode': 'unit', 'need': 1, 'pct': 0, 'from': '', 'until': until, 'cond': '', 'section': '', 'src': 'html', 'conf': conf, 'note': 'cena jednostkowa nie zgadza się' if conf == 'check' else ''}
    feed = {'v': 1, 'updated': _dt.datetime.now().isoformat(), 'stores': {'Kaufland': {'ok': True, 'count': 1}, 'Lidl': {'ok': False, 'msg': 'Brak klucza Gemini'}},
            'offers': [mk('k1', 'Kaufland', 'Masło ekstra Łaciate', 649, 200, 'ok'), mk('l1', 'Lidl', 'Masło polskie', 599, 200, 'check'), dict(mk('l2', 'Lidl', 'Pepsi napój gazowany', 1498, 2000, 'ml'), mode='bundle', need=3, pay=2, page=14, section='gazetka-02-11-pon-kw45'),
              dict(mk('l3', 'Lidl', 'Coca-Cola zły odczyt', 998, 2000, 'check'), unit='ml', printed='Dwusztuk 2 x 1 L · 1 L = 4,99', note='cena za jednostkę wg sklepu 4.99, odczyt jej nie potwierdza'),
              dict(mk('l4', 'Lidl', 'Coca-Cola Dwusztuk', 998, 1000, 'ok'), unit='ml', mode='bundle', need=2, promo='Dwusztuk', deposit=100)]}
    pg.route('**/oferty-test.json', lambda r: r.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=json.dumps(feed)))
    pg.click('[data-tab="ustawienia"]'); pg.fill('#surl', 'http://localhost:8765/oferty-test.json'); pg.click('[data-act="savesrv"]')
    pg.wait_for_function("document.getElementById('view').innerText.includes('Brak klucza Gemini')", timeout=5000)
    check('Pobrane oferty' in pg.inner_text('#view') and '2' in pg.inner_text('#view'), 'serwer: pobrano 2 oferty, widać status sklepów')
    pg.click('[data-tab="okazje"]'); pg.wait_for_selector('#oq')
    pg.fill('#oq', 'maslo'); pg.wait_for_timeout(150)
    t = pg.inner_text('#view'); check('Masło polskie' not in t and 'Masło ekstra' in t and 'Cola' not in t and 'Ukryto 2 oferty z niepewnym odczytem' in t, 'serwer: wyszukiwanie "maslo" (bez polskich znaków); niepewne domyślnie ukryte, widać ile')
    check(pg.eval_on_selector('#oq', 'e => e === document.activeElement'), 'serwer: pole szukania zachowuje fokus podczas pisania')
    pg.fill('#oq', 'zły odczyt'); pg.wait_for_timeout(150); check('Nic nie pasuje' in pg.inner_text('#view'), 'niepewna oferta ukryta')
    pg.click('[data-act="ounsure"]'); pg.wait_for_selector('.offer.unsure'); c_ = pg.inner_text('.offer.unsure')
    check('Na gazetce: Dwusztuk 2 x 1 L' in c_ and '9,98' in c_ and 'odczyt niepewny' in c_ and 'Za 1 l' not in c_ and 'Komplet' not in c_, 'niepewna oferta: tekst z gazetki i cena, bez przeliczeń: ' + c_.replace('\n', ' | '))
    pg.screenshot(path=f'{OUT}/09d-niepewne.png')
    pg.click('.offer.unsure'); pg.wait_for_selector('.sheet'); c_ = pg.inner_text('.sheet')
    check('Na gazetce' in c_ and 'Za 1 l' not in c_ and 'Zawartość' not in c_ and 'Odczytu nie dało się potwierdzić' in c_, 'niepewna oferta: szczegóły bez przeliczeń')
    pg.click('[data-close]'); pg.click('[data-act="ounsure"]'); pg.wait_for_timeout(100)
    pg.fill('#oq', 'dwusztuk'); pg.wait_for_timeout(150); t = pg.inner_text('#view')
    check('Dwusztuk' in t and '2 × 1 l = 2 l' in t and '4,99' in t and '+ kaucja 1,00' in t, 'Dwusztuk: 2 × 1 l = 2 l, 4,99 zł za litr, kaucja osobno: ' + t.replace('\n', ' | ')[:300])
    pg.fill('#oq', ''); pg.click('[data-act="omode"][data-m="porownanie"]'); pg.wait_for_timeout(100)
    t = pg.inner_text('#view'); check('zły odczyt' not in t and 'Masło polskie' not in t and 'nie biorą udziału' in t, 'porównanie bez niepewnych ofert')
    pg.click('[data-act="omode"][data-m="lista"]')
    pg.fill('#oq', 'pepsi'); pg.wait_for_timeout(150); t = pg.inner_text('#view')
    pg.click('[data-act="offer"][data-id="s:l2"]'); pg.wait_for_selector('.sheet')
    check(pg.get_attribute('.sheet a.lnk', 'href').endswith('/gazetki/gazetka-02-11-pon-kw45/view/flyer/page/14'), 'link do strony gazetki w szczegółach'); pg.click('[data-close]')
    check('3 za 2' in t and 'gazetka Lidl, str. 14' in t and '14,98' in t and 'Komplet' in t and '2,50' in t, 'promocja "3 za 2": oznaczenie, miejsce w gazetce, cena kompletu, 2,50 zł za litr')
    pg.fill('#oq', ''); pg.click('[data-act="ocat"][data-c="__multi"]'); pg.wait_for_timeout(100)
    check('Pepsi' in pg.inner_text('#view') and 'Masło' not in pg.inner_text('#view'), 'filtr: tylko komplety i 2+1')
    pg.click('[data-act="ocat"][data-c=""]')
    pg.click('[data-act="offer"][data-id="s:k1"]'); pg.wait_for_selector('.sheet')
    check('nie można jej edytować' in pg.inner_text('.sheet') and pg.query_selector('.sheet #o-name') is None, 'serwer: oferta tylko do odczytu')
    pg.screenshot(path=f'{OUT}/09c-oferta-serwer.png'); pg.click('[data-close]')
    pg.reload(); pg.wait_for_selector('.tab'); pg.click('[data-tab="okazje"]'); check('Masło ekstra' in pg.inner_text('#view'), 'serwer: oferty zostają po przeładowaniu (pamięć telefonu)')
    pg.click('[data-tab="start"]')

    # offline po pierwszym załadowaniu (service worker)
    pg.wait_for_function('navigator.serviceWorker.ready.then(()=>true)'); pg.reload(); time.sleep(1)
    ctx.set_offline(True); pg.reload(); pg.wait_for_selector('.tape'); check(True, 'działa offline po przeładowaniu'); ctx.set_offline(False)
    # trwałość danych
    pg.reload(); pg.wait_for_selector('.tape'); check('73,77' in pg.inner_text('.tape .big').replace(' ', ' '), 'dane zostają po przeładowaniu')

    # tablet i laptop (te same dane): sprawdzenie układu bez poziomego przewijania
    for name, (w, h) in {'tablet': (820, 1180), 'laptop': (1366, 800)}.items():
        pg.set_viewport_size({'width': w, 'height': h})
        for tab in ['start', 'paragony', 'cennik', 'okazje', 'budzet', 'ustawienia']:
            pg.click(f'[data-tab="{tab}"]'); pg.wait_for_timeout(120)
            if tab == 'okazje': pg.click('[data-act="omode"][data-m="porownanie"]'); pg.wait_for_timeout(80)
            pg.screenshot(path=f'{OUT}/r-{name}-{tab}.png')
            ov = pg.evaluate('document.documentElement.scrollWidth - innerWidth')
            check(ov <= 0, f'{name}/{tab}: brak poziomego przewijania ({ov})')
        pg.click('[data-tab="paragony"]'); pg.click('[data-act="new"]'); pg.wait_for_selector('.sheet .f-name'); pg.screenshot(path=f'{OUT}/r-{name}-edytor.png'); pg.click('[data-close]')
    pg.set_viewport_size({'width': 390, 'height': 844})

    # ciemny motyw
    ctx2 = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, color_scheme='dark', locale='pl-PL')
    pg2 = ctx2.new_page(); pg2.goto('http://127.0.0.1:8765/'); pg2.wait_for_selector('.tab'); pg2.screenshot(path=f'{OUT}/11-ciemny-start.png')
    b.close()
finally:
    srv.terminate()
check(not errs, 'brak błędów JS w konsoli: ' + '; '.join(errs[:5]))
print('\nBŁĘDY:' if fails else '\nWSZYSTKO OK', fails)
sys.exit(1 if fails else 0)
