"""Jednorazowe rozpoznanie: jak Biedronka publikuje oferty. Tylko ogląda publiczne strony jak zwykła przeglądarka.
Przy blokadzie lub CAPTCHA kończy z komunikatem. Niczego nie zapisuje i nie wypisuje sekretów."""
import collections
import re
import sys

from playwright.sync_api import sync_playwright

START = 'https://www.biedronka.pl/pl/gazetki'
JS = """() => ({canvas: document.querySelectorAll('canvas').length, img: document.images.length,
 duze: [...document.images].filter(i => i.naturalWidth > 500).map(i => i.src.slice(0, 95)).slice(0, 3),
 klasy: Object.entries([...document.querySelectorAll('[class*=product],[class*=Product],[class*=offer],[class*=tile]')].reduce((a, e) => { const k = String(e.className).split(' ')[0]; a[k] = (a[k] || 0) + 1; return a; }, {})).sort((x, y) => y[1] - x[1]).slice(0, 6),
 ceny: (document.body.innerText.match(/\\d+[,.]\\d{2}/g) || []).length})"""


def strona(g, c, url, nazwa):
    seen, api = collections.Counter(), {}

    def resp(r):
        u, t = r.url.split('?')[0], (r.headers.get('content-type') or '').split(';')[0]
        if 'biedronka' in u or 'leaflet' in u or 'press' in u:
            seen[re.sub(r'https?://([^/]+).*', r'\1', u) + ' ' + t] += 1
            if 'json' in t and not re.search(r'userdata|shippingcenter|cookie', u):
                api.setdefault(u[:95], r.status)
    g.on('response', resp)
    g.goto(url, wait_until='domcontentloaded', timeout=60000); g.wait_for_timeout(7000)
    g.remove_listener('response', resp)
    print(f'== {nazwa}:', g.title()[:60])
    print(g.evaluate(JS))
    t = re.sub(r'\s+', ' ', g.inner_text('body'))
    m = re.search(r'.{70}\d+[,.]\d{2}.{70}', t)
    print('tekst:', m.group(0)[:150] if m else '-')
    print('ruch:', seen.most_common(4))
    print('api:', list(api.items())[:6])


with sync_playwright() as p:
    b = p.chromium.launch()
    g = b.new_context(locale='pl-PL', viewport={'width': 1366, 'height': 900}).new_page()
    g.goto(START, wait_until='domcontentloaded', timeout=60000); g.wait_for_timeout(5000)
    if re.search(r'just a moment|captcha|attention required|access denied', g.title() + g.inner_text('body')[:400], re.I):
        print('BLOKADA: niczego nie omijam.'); sys.exit(0)
    links = sorted({h for h in g.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.href)") if '/pl/press,' in h})
    print('gazetki:', [re.sub(r'.*title,', '', x)[:32] for x in links])
    fl = next((x for x in links if 'codziennie' in x), links[0] if links else None)
    if fl:
        strona(g, None, fl, 'gazetka')
    strona(g, None, 'https://www.biedronka.pl/pl/nowa-oferta', 'nowa oferta')
    strona(g, None, 'https://home.biedronka.pl/promocje/', 'promocje')
    b.close()
