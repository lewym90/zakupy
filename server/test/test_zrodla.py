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
        {'nazwa': 'Parówki z szynki', 'marka': 'Pikok', 'opakowanie': '300 g', 'cena': 6.99, 'cena_przed': 9.99, 'cena_jednostkowa': '1 kg = 23,30', 'komplet_ilosc': None, 'komplet_cena': None, 'kolejna_taniej_proc': None, 'warunek': None},
        {'nazwa': 'Napój Coca-Cola', 'marka': None, 'opakowanie': '1,5 l', 'cena': 3.33, 'cena_przed': None, 'cena_jednostkowa': '1 l = 2,22', 'komplet_ilosc': 3, 'komplet_cena': 9.99, 'kolejna_taniej_proc': None, 'warunek': 'z Lidl Plus'},
        {'nazwa': 'Ser Gouda', 'marka': 'Pilos', 'opakowanie': '300 g', 'cena': 11.39, 'cena_przed': None, 'cena_jednostkowa': '1 kg = 99,99', 'komplet_ilosc': None, 'komplet_cena': None, 'kolejna_taniej_proc': None, 'warunek': None},  # zły odczyt: cena jedn. się nie zgadza
        {'nazwa': 'Jogurt', 'marka': None, 'opakowanie': '150 g', 'cena': 1.99, 'cena_przed': None, 'cena_jednostkowa': None, 'komplet_ilosc': None, 'komplet_cena': None, 'kolejna_taniej_proc': 50, 'warunek': None},
        {'nazwa': '', 'marka': None, 'opakowanie': None, 'cena': 5, 'cena_przed': None, 'cena_jednostkowa': None, 'komplet_ilosc': None, 'komplet_cena': None, 'kolejna_taniej_proc': None, 'warunek': None},  # bez nazwy: odrzucone
    ]}

    def test_map_item(self):
        import lidl
        offers = [lidl.map_item(i, '2026-11-02', '2026-11-04') for i in self.ITEMS['oferty']]
        self.assertIsNone(offers[4])
        par, cola, ser, jog = offers[:4]
        self.assertEqual((par['name'], par['price'], par['old'], par['conf']), ('Pikok Parówki z szynki', 699, 999, 'ok'))
        self.assertEqual((cola['mode'], cola['need'], cola['price'], cola['amount'], cola['unit'], cola['conf']), ('bundle', 3, 999, 1.5, 'l', 'check'))
        self.assertEqual(ser['conf'], 'check'); self.assertIn('wg sklepu', ser['note'])
        self.assertEqual((jog['mode'], jog['pct'], jog['need'], jog['conf']), ('nth', 50.0, 2, 'check'))

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



class Czas(unittest.TestCase):
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
