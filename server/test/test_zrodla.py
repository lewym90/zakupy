"""Testy źródeł bez internetu: Kaufland na stronie-atrapie z prawdziwym układem kafelków, Lidl z atrapą API i atrapą Gemini."""
import datetime as dt
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..', 'zbieracz'))
os.environ['ZBIERACZ_PAUSE'] = '0'

TILE = ('<div class="k-grid__item"><a class="k-product-tile" href="#"><div class="k-product-tile__main"><div class="k-product-tile__text">'
        '<div class="k-product-tile__title">{t}</div><div class="k-product-tile__subtitle">{s}</div><div class="k-product-tile__unit-price">{u}</div>'
        '<div class="k-product-tile__base-price">{b}</div></div></div><div class="k-product-tile__bottom"><div class="k-price-tag">'
        '<div class="k-price-tag__discount">{d}</div><div class="k-price-tag__price">{p} </div><div class="k-price-tag__old-price">'
        '<span class="k-price-tag__old-price-line-through">{o}</span><span>cena przed obniżką</span></div></div></div></a></div>')


def page_html():
    sec = lambda name, valid, tiles: f'<section><div><h2>{name}</h2></div><div><span>{valid}</span></div>{"".join(tiles)}</section>'
    return ('<html><body><main>' +
            sec('Napoje', 'Oferta ważna od 29.10. do 04.11.', [TILE.format(t='Coca-Cola,', s='Fanta, Sprite Napój gazowany', u='2 x 2 l opakowanie', b='(=1 l 3,50)', d='tylko', p='13,98', o='')]) +
            sec('Hity tygodnia', 'Oferta ważna 02.11.', [TILE.format(t='Pomidory rzymskie mini', s='', u='500 g opakowanie', b='(=1 kg 19,98)', d='-37%', p='9,99', o='15,99')]) +
            sec('Artykuły AGD', 'Oferta ważna od 22.10. do 04.11.', [TILE.format(t='Robot', s='kuchenny', u='', b='(=1 szt 139,00)', d='tylko', p='139,00', o='')]) +
            '</main></body></html>')


class Kaufland(unittest.TestCase):
    def test_przegladarka_na_atrapie(self):
        from playwright.sync_api import sync_playwright
        import kaufland
        d = tempfile.mkdtemp()
        f = os.path.join(d, 'k.html'); open(f, 'w', encoding='utf-8').write(page_html())
        with sync_playwright() as p:
            b = p.chromium.launch(); page = b.new_page()
            offers, warns = kaufland.collect(page, 'file://' + f, dt.date(2026, 11, 2))
            b.close()
        by = {o['name']: o for o in offers}
        self.assertEqual(len(offers), 2, offers)  # AGD pominięte
        c = by['Coca-Cola, Fanta, Sprite Napój gazowany']
        self.assertEqual((c['price'], c['amount'], c['unit'], c['conf'], c['until']), (1398, 4.0, 'l', 'ok', '2026-11-04'))
        t = by['Pomidory rzymskie mini']
        self.assertEqual((t['price'], t['old'], t['from'], t['until']), (999, 1599, '2026-11-02', '2026-11-02'))

    def test_blokada_nie_jest_omijana(self):
        from playwright.sync_api import sync_playwright
        import kaufland
        d = tempfile.mkdtemp(); f = os.path.join(d, 'b.html'); open(f, 'w').write('<html><title>Just a moment...</title><body>Sprawdzamy przeglądarkę</body></html>')
        with sync_playwright() as p:
            b = p.chromium.launch(); page = b.new_page()
            kaufland.collect.__globals__['page_timeout'] = 1
            orig = page.wait_for_selector
            page.wait_for_selector = lambda sel, timeout=0: orig(sel, timeout=1500)
            with self.assertRaises(RuntimeError) as cm:
                kaufland.collect(page, 'file://' + f, dt.date(2026, 11, 2))
            b.close()
        self.assertIn('niczego nie omijam', str(cm.exception))


class Lidl(unittest.TestCase):
    ITEMS = {'oferty': [
        {'nazwa': 'Parówki z szynki', 'marka': 'Pikok', 'opakowanie': '300 g', 'cena': '6,99', 'cena_przed': '9,99', 'cena_jednostkowa': '1 kg = 23,30'},
        {'nazwa': 'Napój Coca-Cola', 'marka': None, 'opakowanie': '1,5 l', 'cena': '9,99', 'cena_jednostkowa': '1 l = 2,22', 'promocja': '3 za 9,99 zł', 'warunek': 'z Lidl Plus'},
        {'nazwa': 'Ser Gouda', 'marka': 'Pilos', 'opakowanie': '300 g', 'cena': '11,39', 'cena_jednostkowa': '1 kg = 99,99'},  # zły odczyt: cena jedn. się nie zgadza
        {'nazwa': 'Jogurt', 'marka': None, 'opakowanie': '150 g', 'cena': '1,99', 'promocja': 'drugi produkt -50%'},
        {'nazwa': '', 'marka': None, 'opakowanie': None, 'cena': '5,00'},  # bez nazwy: odrzucone
    ]}

    def test_map_item(self):
        import lidl
        offers = [lidl.map_item(i, '2026-11-02', '2026-11-04') for i in self.ITEMS['oferty']]
        self.assertIsNone(offers[4])
        par, cola, ser, jog = offers[:4]
        self.assertEqual((par['name'], par['price'], par['old'], par['conf']), ('Pikok Parówki z szynki', 699, 999, 'ok'))
        self.assertEqual((cola['mode'], cola['need'], cola['price'], cola['amount'], cola['unit'], cola['conf']), ('bundle', 3, 999, 1.5, 'l', 'ok'))
        self.assertEqual(ser['conf'], 'check'); self.assertIn('wg sklepu', ser['note'])
        self.assertEqual((jog['mode'], jog['need'], jog['price'], jog['conf'], jog['promo']), ('unit', 1, 199, 'check', 'drugi produkt -50%'))  # bez kontroli: tylko cena z gazetki

    def test_collect_z_atrapa_gemini_i_cache(self):
        import lidl
        calls = []

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                n = int(self.headers.get('Content-Length', 0)); raw = self.rfile.read(n); calls.append(self.path)
                nimg = raw.count(b'inline_data')
                if 'gemini-9.0-flash' in self.path:
                    self.send_response(404); self.send_header('Content-Type', 'application/json'); self.end_headers()
                    self.wfile.write(json.dumps({'error': {'message': 'no longer available'}}).encode()); return
                body = {'candidates': [{'content': {'parts': [{'text': json.dumps({'strony': [{'numer': i + 1, 'oferty': Lidl.ITEMS['oferty']} for i in range(nimg)]})}]}}]}
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps(body).encode())
            def do_GET(self):
                calls.append(self.path)
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({'models': [{'name': 'models/gemini-3.8-flash', 'supportedGenerationMethods': ['generateContent']}]}).encode())
        srv = http.server.HTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        import gemini
        gemini.BASE = f'http://127.0.0.1:{srv.server_port}/v1beta'; gemini.DEFAULT_MODEL = 'gemini-9.0-flash'

        class R:
            def __init__(s, js=None, by=b'\xff\xd8x'): s.ok, s.status, s._j, s._b = True, 200, js, by
            def json(s): return s._j
            def body(s): return s._b

        class Ctx:
            class request:
                @staticmethod
                def get(url, **kw):
                    if 'flyer?' in url:
                        return R({'flyer': {'offerStartDate': '2026-11-02', 'offerEndDate': '2026-11-04', 'pages': [{'number': 1, 'image': 'https://img/1.jpg'}, {'number': 2, 'image': 'https://img/2.jpg'}]}})
                    return R()

        class Page:
            def goto(s, *a, **k): pass
            def wait_for_timeout(s, ms): pass
            def evaluate(s, js): return ['/l/pl/gazetki/gazetka-02-11-pon-kw45/ar/0?_ab=1', '/l/pl/gazetki/katalog-zabawek-kw45/ar/0', '/l/pl/gazetki/gazetka-02-11-pon-kw45/ar/0']

        cache = tempfile.mkdtemp()
        offers, warns = lidl.collect(Page(), Ctx(), 'KEY', cache, log=lambda *a: None)
        self.assertEqual(len(offers), 8)  # 2 strony x 4 poprawne pozycje (run.py scala potem po id)
        self.assertEqual(len({o['id'] for o in offers}), 4)
        self.assertEqual(len([c for c in calls if c.endswith(':generateContent')]), 2)  # 404 (stary model) + jedno zapytanie z 2 stronami
        n = len(calls)
        offers2, _ = lidl.collect(Page(), Ctx(), 'KEY', cache, log=lambda *a: None)  # drugi raz: wszystko z pamięci, zero zapytań do Gemini
        self.assertEqual(len(offers2), 8); self.assertEqual(len(calls), n)
        self.assertTrue(all(o['store'] == 'Lidl' and o['until'] == '2026-11-04' for o in offers))
        srv.shutdown()



class Biedronka(unittest.TestCase):
    def setUp(self):
        import biedronka
        self.b = biedronka

    def test_daty_z_adresu(self):
        t = dt.date(2026, 11, 4)
        self.assertEqual(self.b.valid_from_slug('https://x/pl/press,id,j2,title,festiwal-wdlin-od-3-11', t), dt.date(2026, 11, 3))
        self.assertEqual(self.b.valid_from_slug('https://x/title,codziennie-niskie-ceny-p-oferta-od-29-10', t), dt.date(2026, 10, 29))
        self.assertIsNone(self.b.valid_from_slug('https://x/title,bez-daty', t))
        self.assertEqual(self.b.valid('Oferta od 03.11 do 08.11', dt.date(2026, 11, 3), t), ('2026-11-03', '2026-11-08'))
        self.assertEqual(self.b.valid(None, dt.date(2026, 11, 3), t), ('2026-11-03', '2026-11-09'))

    def _page(self):
        b = self
        class P:
            def __init__(s): s.h = None
            def goto(s, url, **k):
                s.url = url
                if 'press' in url:
                    s.h(type('R', (), {'url': 'https://leaflet-api.prod.biedronka.cloud/api/leaflets/abc?ctx=web', 'json': lambda self: {'images_mobile': [{'page': '0', 'image': 'https://img/0'}, {'page': '1', 'image': 'https://img/1'}]}})())
            def wait_for_timeout(s, ms): pass
            def title(s): return 'Gazetki'
            def evaluate(s, js): return ['https://www.biedronka.pl/pl/press,id,a,title,festiwal-nabiau-od-3-11#page=1', 'https://www.biedronka.pl/pl/press,id,b,title,home-od-31-10', 'https://glovoapp.com/biedronka-express', 'https://www.biedronka.pl/pl/press,id,c,title,magiczna-kraina-zabawek']
            def on(s, ev, fn): s.h = fn
            def remove_listener(s, ev, fn): s.h = None
        return P()

    def test_tylko_spozywcze_i_caly_odczyt(self):
        import gemini
        calls = []
        def rj(self2, imgs, prompt):
            calls.append(len(imgs)); self.assertIn('Biedronki', prompt); self.assertIn('"opakowanie"', prompt); self.assertIn('"wazne"', prompt)
            return {'strony': [{'numer': 1, 'oferty': [{'nazwa': 'Masło', 'opakowanie': '200 g', 'cena': '6,99', 'cena_jednostkowa': '1 kg = 34,95', 'promocja': None}, None]}, {'numer': 2, 'oferty': [{'nazwa': 'Ser', 'opakowanie': '150 g', 'cena': '4,99'}]}]}
        orig = gemini.Reader.read_json; self.b.Reader.read_json = rj
        class R:
            ok, status = True, 200
            def body(s): return b'RIFFxxxx'
        class Ctx:
            class request:
                get = staticmethod(lambda url, **k: R())
        try:
            cache = tempfile.mkdtemp()
            offers, warns = self.b.collect(self._page(), Ctx(), 'K', cache, log=lambda *a: None, today=dt.date(2026, 11, 4))
            self.assertEqual(calls, [2])
            self.assertEqual({(o['name'], o['conf'], o['store'], o['page']) for o in offers}, {('Masło', 'ok', 'Biedronka', 1), ('Ser', 'check', 'Biedronka', 2)})
            self.assertTrue(offers[0]['link'].endswith('festiwal-nabiau-od-3-11#page=1'))
            self.b.collect(self._page(), Ctx(), 'K', cache, log=lambda *a: None, today=dt.date(2026, 11, 4))
            self.assertEqual(calls, [2])  # drugi raz z pamięci
        finally:
            gemini.Reader.read_json = orig


class Porzadek(unittest.TestCase):
    def test_nazwy(self):
        from normalize import clean_name as c
        self.assertEqual(c('Gusto Bello', 'Prosciutto cotto Gusto Bello, 100 g', 'Biedronka'), 'Gusto Bello Prosciutto cotto')
        self.assertEqual(c('Biedronka', 'Prosciutto di Parma Biedronka', 'Biedronka'), 'Prosciutto di Parma')
        self.assertEqual(c('Delikate', 'Ser mozzarella wiórki Delikate, 300 g', 'Biedronka'), 'Delikate Ser mozzarella wiórki')
        self.assertEqual(c('DZIK', 'NAPÓJ GAZOWANY DZIK ZERO**', 'Biedronka'), 'DZIK Napój gazowany dzik zero')
        self.assertEqual(c('', 'Kaki', 'Lidl'), 'Kaki')

    def test_duplikaty(self):
        from normalize import dedupe_offers as d
        o = lambda n, p, u, c='ok', s='Lidl', need=1: {'name': n, 'price': p, 'until': u, 'conf': c, 'store': s, 'need': need}
        r = d([o('Kaki', 499, '2026-11-04'), o('Kaki', 499, '2026-11-07'), o('Kaki', 499, '2026-11-09', 'check'), o('Kaki', 599, '2026-11-07'), o('Kaki', 499, '2026-11-07', s='Biedronka'), o('Woda 1,5 l', 200, '2026-11-07'), o('Woda', 200, '2026-11-05')])
        self.assertEqual(sorted((x['store'], x['price'], x['until']) for x in r), [('Biedronka', 499, '2026-11-07'), ('Lidl', 200, '2026-11-07'), ('Lidl', 499, '2026-11-07'), ('Lidl', 599, '2026-11-07')])

    def test_dobor_grafik(self):
        import klasyfikuj as k
        self.assertEqual(len(k.LABELS), 384)
        calls = []
        class R:
            def read_json(s, imgs, prompt):
                calls.append(prompt); return {'w': [{'i': 0, 'g': 7, 'k': 'nabial'}, {'i': 1, 'g': 9999, 'k': 'nabial'}, {'i': 2, 'g': 1, 'k': 'zle'}, None]}
        d = tempfile.mkdtemp()
        offers = [{'name': 'A'}, {'name': 'B'}, {'name': 'C'}]
        self.assertEqual(k.classify(offers, d, 'K', lambda *a: None, reader=R()), 1)
        self.assertEqual((offers[0]['thumb'], offers[0]['aiCat']), (7, 'nabial')); self.assertNotIn('thumb', offers[1])  # złe odpowiedzi odrzucone
        k.classify([{'name': 'A'}], d, 'K', lambda *a: None, reader=R())
        self.assertEqual(len(calls), 1)  # znana nazwa nie kosztuje zapytania


class Promocje(unittest.TestCase):
    def test_parse_multibuy(self):
        from normalize import parse_multibuy as pm
        self.assertEqual(pm('3 w cenie 2'), {'need': 3, 'pay': 2})
        self.assertEqual(pm('Promocja 3 za 2'), {'need': 3, 'pay': 2})
        self.assertEqual(pm('2+1 gratis'), {'need': 3, 'pay': 2})
        self.assertEqual(pm('kup 2 + 1 gratis'), {'need': 3, 'pay': 2})
        self.assertEqual(pm('3 za 9,99 zł'), {'need': 3, 'total': 999})
        self.assertEqual(pm('drugi produkt -50%'), {'need': 2, 'pct': 50.0})
        self.assertEqual(pm('-30% na drugi produkt'), {'need': 2, 'pct': 30.0})
        self.assertEqual(pm('drugi gratis'), {'need': 2, 'pct': 100.0})
        for nic in ['400 g + 50 g', '2 x 2 l opakowanie', '-37%', '1 kg za 9,99 zł', 'tylko', '']:
            self.assertIsNone(pm(nic), nic)

    def test_lidl_trzy_w_cenie_dwoch(self):
        import lidl
        it = {'nazwa': 'Coca-Cola', 'marka': None, 'opakowanie': '2 l', 'cena': '7,49', 'cena_jednostkowa': '1 l = 3,75', 'promocja': '3 za 2'}
        o = lidl.map_item(it, '2026-11-02', '2026-11-04')
        self.assertEqual((o['mode'], o['need'], o['pay'], o['price'], o['conf'], o['promo']), ('bundle', 3, 2, 1498, 'ok', '3 za 2'))
        o2 = lidl.map_item(dict(it, promocja='2+1 gratis'), '2026-11-02', '2026-11-04')
        self.assertEqual((o2['mode'], o2['need'], o2['pay']), ('bundle', 3, 2))

    def test_kaufland_wykrywa_promocje(self):
        import kaufland
        row = ['Napoje', 'Oferta ważna od 29.10. do 04.11.', 'Pepsi', 'Napój gazowany', '2 l opakowanie', '(=1 l 3,75)', '3 za 2', '7,49', '', 0, 'Pepsi Napój gazowany 2 l (=1 l 3,75) 3 za 2 7,49']
        offers, _ = kaufland.parse_rows([row], dt.date(2026, 11, 2))
        o = offers[0]
        self.assertEqual((o['mode'], o['need'], o['pay'], o['price'], o['conf']), ('bundle', 3, 2, 1498, 'ok'))  # etykieta promocji + zgodna cena za litr
        r2 = list(row); r2[6] = ''  # promocja tylko w opisie: niepewna
        self.assertEqual(kaufland.parse_rows([r2], dt.date(2026, 11, 2))[0][0]['conf'], 'check')
        r3 = ['Napoje', 'Oferta ważna od 29.10. do 04.11.', 'Cola', 'Napój', '3 x 1,5 l', '(=1 l 2,22)', '3 za 9,99 zł', '9,99', '', 0, '']
        o3 = kaufland.parse_rows([r3], dt.date(2026, 11, 2))[0][0]
        self.assertEqual((o3['need'], o3['amount'], o3['price'], o3['conf']), (3, 1.5, 999, 'ok'))  # bez podwójnego mnożenia


class Czas(unittest.TestCase):
    def test_wiele_zmian_modelu_nie_konczy_sie_pustym_wynikiem(self):
        import gemini
        r = gemini.Reader('K', pause=0)
        names = iter(['m2', 'm3', 'm4', 'm5', 'm6'])
        r._next_model = lambda: next(names, None)
        calls = []
        def call(*a):
            calls.append(r.model)
            if r.model == 'm6':
                return {'candidates': [{'content': {'parts': [{'text': '{"ok":1}'}]}}]}
            raise gemini.GeminiError(429, 'quota RequestsPerDay')
        r._call = call
        self.assertEqual(r.read_json(b'x', 'p'), {'ok': 1})  # dawniej po czterech zmianach wynikiem było None
        self.assertEqual(len(calls), 6)

    def test_odpowiedz_null_to_blad_a_nie_awaria(self):
        import gemini
        r = gemini.Reader('K', pause=0)
        r._call = lambda *a: {'candidates': [{'content': {'parts': [{'text': 'null'}]}}]}
        with self.assertRaises(gemini.GeminiError) as cm:
            r.read_json(b'x', 'p')
        self.assertIn('null', str(cm.exception))

    def test_kaufland_pomija_katalog_zabawek(self):
        import kaufland
        row = ['Katalog Zabawka cz.1', 'Oferta ważna od 29.10. do 04.11.', 'Marka', 'Klocki', '1 szt', '', '', '49,99', '', 0, '']
        self.assertEqual(kaufland.parse_rows([row], dt.date(2026, 11, 2))[0], [])

    def test_kaufland_pewna_cena_bez_przeliczenia(self):
        import kaufland
        v = 'Oferta ważna od 29.10. do 04.11.'
        wiersz = lambda nazwa, pack, base, cena: ['Dom', v, 'Marka', nazwa, pack, base, '', cena, '', 0, '']
        o = kaufland.parse_rows([wiersz('Spray', '750/435 ml opakowanie', '', '14,99')], dt.date(2026, 11, 2))[0][0]
        self.assertEqual((o['conf'], o['price'], o['printed']), ('cena', 1499, '750/435 ml opakowanie'))
        o = kaufland.parse_rows([wiersz('Farba', 'opakowanie', '', '21,99')], dt.date(2026, 11, 2))[0][0]
        self.assertEqual(o['conf'], 'cena')
        o = kaufland.parse_rows([wiersz('Maszynki', 'sztuka', '(=1 szt 3,00)', '8,99')], dt.date(2026, 11, 2))[0][0]
        self.assertEqual((o['conf'], o['amount'], o['unit']), ('ok', 3.0, 'szt'))  # ilość wynika z ceny za sztukę ze sklepu
        o = kaufland.parse_rows([wiersz('Ser', '300 g', '(=1 kg 99,99)', '11,39')], dt.date(2026, 11, 2))[0][0]
        self.assertEqual(o['conf'], 'check')  # waga niezgodna: nadal niepewne

    def test_timeout_to_ponowienie(self):
        import gemini, urllib.request
        calls = []
        orig = urllib.request.urlopen

        class Resp:
            def __enter__(s): return s
            def __exit__(s, *a): pass
            def read(s): return json.dumps({'candidates': [{'content': {'parts': [{'text': '{"oferty": []}'}]}}]}).encode()

        def fake(r, timeout=None):
            calls.append(1)
            if len(calls) == 1: raise TimeoutError('The read operation timed out')
            return Resp()
        urllib.request.urlopen = fake
        gemini.time.sleep = lambda s: None
        try:
            self.assertEqual(gemini.Reader('K', 'gemini-3.8-flash', pause=0).read_json(b'x', 'p'), {'oferty': []})
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(len(calls), 2)


    def test_dzienny_limit(self):
        import gemini, urllib.request, urllib.error, io
        orig = urllib.request.urlopen
        def fake(r, timeout=None):
            raise urllib.error.HTTPError('u', 429, 'x', {}, io.BytesIO(json.dumps({'error': {'message': 'Quota exceeded for metric GenerateRequestsPerDayPerProjectPerModel-FreeTier'}}).encode()))
        urllib.request.urlopen = fake
        try:
            with self.assertRaises(gemini.DailyQuota):
                gemini.Reader('K', 'm', pause=0).read_json(b'x', 'p')
        finally:
            urllib.request.urlopen = orig


    def test_zmiana_modelu_po_dziennym_limicie(self):
        import gemini
        seen = []
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', 0))); seen.append(self.path)
                if 'gemini-3.8-flash:' in self.path:
                    self.send_response(429); self.send_header('Content-Type', 'application/json'); self.end_headers()
                    self.wfile.write(json.dumps({'error': {'message': 'Quota exceeded for metric ...RequestsPerDay... FreeTier'}}).encode()); return
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({'candidates': [{'content': {'parts': [{'text': '{"strony":[]}'}]}}]}).encode())
            def do_GET(self):
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({'models': [{'name': 'models/gemini-3.8-flash', 'supportedGenerationMethods': ['generateContent']}, {'name': 'models/gemini-3.8-flash-lite', 'supportedGenerationMethods': ['generateContent']}, {'name': 'models/gemini-3.8-pro', 'supportedGenerationMethods': ['generateContent']}]}).encode())
        srv = http.server.HTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        gemini.BASE = f'http://127.0.0.1:{srv.server_port}/v1beta'
        r = gemini.Reader('K', 'gemini-3.8-flash', pause=0)
        self.assertEqual(r.read_json([b'x', b'y'], 'p'), {'strony': []})
        self.assertEqual(r.model, 'gemini-3.8-flash-lite')
        self.assertTrue(seen[-1].endswith('gemini-3.8-flash-lite:generateContent'))
        srv.shutdown()


if __name__ == '__main__':
    unittest.main()
