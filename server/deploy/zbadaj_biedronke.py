"""Jednorazowe rozpoznanie: budowa danych gazetki Biedronki. Tylko publiczne dane, bez omijania blokad. Niczego nie zapisuje."""
import json
import re

from playwright.sync_api import sync_playwright


def shape(x, d=0):
    if d > 4:
        return '…'
    if isinstance(x, dict):
        return {k: shape(v, d + 1) for k, v in list(x.items())[:22]}
    if isinstance(x, list):
        return [len(x), shape(x[0], d + 1)] if x else []
    return str(x)[:70] if x is not None else None


with sync_playwright() as p:
    b = p.chromium.launch()
    g = b.new_context(locale='pl-PL', viewport={'width': 1366, 'height': 900}).new_page()
    g.goto('https://www.biedronka.pl/pl/gazetki', wait_until='domcontentloaded', timeout=60000); g.wait_for_timeout(4000)
    links = sorted({h for h in g.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.href)") if '/pl/press,' in h})
    print('gazetek:', len(links))
    fl = next(x for x in links if 'codziennie' in x)
    got = []

    def resp(r):
        if 'leaflet-api' in r.url:
            try:
                got.append((r.url, r.json()))
            except Exception:
                pass
    g.on('response', resp)
    g.goto(fl, wait_until='domcontentloaded', timeout=60000); g.wait_for_timeout(7000)
    for u, j in got[:2]:
        print('adres:', re.sub(r'[0-9a-f-]{36}', '<id>', u)[:90])
        print(json.dumps(shape(j), ensure_ascii=False)[:1700])
    print('skąd id:', [m[:60] for m in re.findall(r'[0-9a-f]{8}-[0-9a-f-]{27}', g.content())[:2]])
    im = g.evaluate("[...document.images].map(i=>i.src).filter(s=>/images.biedronka.cloud/.test(s)).slice(0,2)")
    print('obrazy:', [x[:120] for x in im], g.evaluate("[...document.images].filter(i=>/images.biedronka.cloud/.test(i.src)).slice(0,1).map(i=>[i.naturalWidth,i.naturalHeight])"))
    print('linki gazetek:', [re.sub(r'.*press,id,', '', x)[:48] for x in links])
    b.close()
