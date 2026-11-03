"""Jednorazowe rozpoznanie: jak Biedronka publikuje oferty. Tylko ogląda publiczne strony jak zwykła przeglądarka.
Przy blokadzie lub CAPTCHA kończy z komunikatem. Niczego nie zapisuje i nie wypisuje sekretów."""
import collections
import re
import sys

from playwright.sync_api import sync_playwright

START = 'https://www.biedronka.pl/pl/gazetki'
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(locale='pl-PL', viewport={'width': 1366, 'height': 900})
    g = c.new_page()
    seen = collections.Counter()
    samples = {}

    def resp(r):
        u, t = r.url.split('?')[0], (r.headers.get('content-type') or '').split(';')[0]
        k = re.sub(r'https?://([^/]+).*', r'\1', u) + ' ' + t
        seen[k] += 1
        if t in ('application/json', 'text/json') or re.search(r'\.(json|pdf)$', u):
            samples.setdefault(u[:110], r.status)
    g.on('response', resp)
    g.goto(START, wait_until='domcontentloaded', timeout=60000); g.wait_for_timeout(5000)
    print('tytuł:', g.title()[:70], '| adres:', g.url[:80])
    if re.search(r'just a moment|captcha|attention required|access denied', g.title() + g.inner_text('body')[:400], re.I):
        print('BLOKADA: niczego nie omijam.'); sys.exit(0)
    links = sorted({h for h in g.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.href)") if re.search(r'gazetk|press|leaflet|oferta|promoc', h, re.I)})
    print('linki:', len(links)); [print(' ', x[:100]) for x in links[:14]]
    fl = next((x for x in links if re.search(r'press|gazetk\w*/.+|leaflet', x)), None)
    if fl:
        g.goto(fl, wait_until='domcontentloaded', timeout=60000); g.wait_for_timeout(7000)
        print('gazetka:', g.title()[:70], '| adres:', g.url[:90])
        print('elementy:', g.evaluate("({canvas:document.querySelectorAll('canvas').length,img:document.images.length,iframe:[...document.querySelectorAll('iframe')].map(f=>f.src.slice(0,90))})"))
        print('obrazy:', [i[:90] for i in g.evaluate("[...document.images].map(i=>i.src).filter(s=>/page|leaflet|gazet|press/i.test(s)).slice(0,4)")])
    print('ruch:'); [print(' ', v, k) for k, v in seen.most_common(14)]
    print('json/pdf:'); [print(' ', s, u) for u, s in list(samples.items())[:14]]
    b.close()
