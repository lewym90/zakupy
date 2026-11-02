# Odczyt zdjęcia paragonu z PODSTAWIONYMI odpowiedziami Google (nie łączy się z prawdziwym Gemini).
# Scenariusz użytkownika: zapisany stary model => 404 "no longer available" => lista modeli => nowy model => odczyt.
import json, subprocess, sys, time
from playwright.sync_api import sync_playwright
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8766', '--directory', '.'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
fails = []; calls = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m); (c or fails.append(m))
READ = {"sklep": "Lidl", "data": "2026-11-02", "suma": 35.78, "pozycje": [
    {"nazwa": "Karkówka wieprzowa", "ilosc": 1.2, "jednostka": "kg", "wartosc": 28.80},
    {"nazwa": "Mleko UHT", "ilosc": 2, "jednostka": "szt", "wartosc": 6.98}]}
def route(r):
    u = r.request.url; calls.append(u.split('googleapis.com')[1])
    if '/models/gemini-2.5-flash:generateContent' in u or '/models/gemini-9.9-flash:generateContent' in u:
        r.fulfill(status=404, content_type='application/json', body=json.dumps({"error": {"code": 404, "message": "This model models/gemini-2.5-flash is no longer available to new users."}}))
    elif u.endswith('/v1beta/models') or '/v1beta/models?' in u:
        r.fulfill(status=200, content_type='application/json', body=json.dumps({"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]}]}))
    elif '/models/gemini-3.8-flash:generateContent' in u:
        r.fulfill(status=200, content_type='application/json', body=json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(READ)}]}}]}))
    else: r.fulfill(status=500, body='nieoczekiwane')
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block'); pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.route('**/generativelanguage.googleapis.com/**', route)
        pg.goto('http://127.0.0.1:8766/'); pg.wait_for_selector('.tab')
        # stan jak u użytkownika: klucz i STARY model zapisane w telefonie
        pg.evaluate("""async()=>{const {kvSet}=await import('./js/db.js'); await kvSet('geminiKey','TEST'); await kvSet('geminiModel','gemini-2.5-flash');}"""); pg.reload(); pg.wait_for_selector('.tab')
        pg.click('[data-tab="paragony"]'); pg.click('[data-act="new"]'); pg.wait_for_selector('.sheet .f-name')
        pg.set_input_files('.f-photo', '/tmp/receipt.jpg')
        pg.wait_for_selector('.ln .f-name[value="Karkówka wieprzowa"]', timeout=8000)
        check(pg.locator('.ln').count() == 2, 'odczytano 2 pozycje mimo wycofanego modelu')
        check(pg.input_value('.f-decl') == '35,78', 'suma z paragonu 35,78 wpisana')
        check('Sprawdź' in pg.inner_text('.sheet') or pg.locator('.ln.chk').count() >= 1, 'pozycje oznaczone do sprawdzenia')
        check(any('gemini-3.8-flash:generateContent' in c for c in calls), 'użyto modelu z listy Google')
        saved = pg.evaluate("""async()=>{const {kvGet}=await import('./js/db.js'); return kvGet('geminiModel')}""")
        check(saved == 'gemini-3.8-flash', 'nowy model zapisany w telefonie: ' + str(saved))
        pg.click('[data-close]')
        # drugi odczyt idzie już od razu nowym modelem (bez 404)
        calls.clear(); pg.click('[data-act="new"]'); pg.wait_for_selector('.sheet .f-name'); pg.set_input_files('.f-photo', '/tmp/receipt.jpg')
        pg.wait_for_selector('.ln .f-name[value="Mleko UHT"]', timeout=8000)
        check(len(calls) == 1 and '3.8-flash' in calls[0], 'drugi odczyt: jedno zapytanie, nowy model: ' + str(calls))
        # Ustawienia: model pokazuje nowy, a "Sprawdź klucz" potwierdza dostępność
        pg.click('[data-close]'); pg.click('[data-tab="ustawienia"]')
        check(pg.input_value('#gmodel') == 'gemini-3.8-flash', 'Ustawienia pokazują nowy model')
        pg.click('[data-act="testkey"]'); pg.wait_for_function("document.getElementById('key-status').textContent.includes('dostępny')", timeout=5000)
        # model, którego nie ma na liście wycofanych, a Google go nie zna (404) => lista modeli => nowy
        pg.evaluate("""async()=>{const {kvSet}=await import('./js/db.js'); await kvSet('geminiModel','gemini-9.9-flash');}"""); pg.reload(); pg.wait_for_selector('.tab')
        calls.clear(); pg.click('[data-tab="paragony"]'); pg.click('[data-act="new"]'); pg.wait_for_selector('.sheet .f-name'); pg.set_input_files('.f-photo', '/tmp/receipt.jpg')
        pg.wait_for_selector('.ln .f-name[value="Karkówka wieprzowa"]', timeout=8000)
        check(calls[0].startswith('/v1beta/models/gemini-9.9-flash') and any('3.8-flash:generateContent' in c for c in calls), 'ścieżka 404 -> lista -> nowy model: ' + str(calls))
        check(pg.evaluate("""async()=>{const {kvGet}=await import('./js/db.js'); return kvGet('geminiModel')}""") == 'gemini-3.8-flash', 'po 404 nowy model zapisany')
        check(not errs, 'brak błędów JS: ' + '; '.join(errs[:3]))
        b.close()
finally:
    srv.terminate()
print('WSZYSTKO OK' if not fails else 'BŁĘDY: %s' % fails); sys.exit(1 if fails else 0)
