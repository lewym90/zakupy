"""Kaufland: oferta tygodnia ze strony sklep.kaufland.pl (HTML renderowany w przeglądarce).
Nie omijamy żadnych zabezpieczeń: jeśli strona pokaże wyzwanie/blokadę, kończymy z komunikatem."""
import datetime as dt
import re

from normalize import make_offer, money, parse_pack, parse_valid, verify

URL_CURRENT = 'https://sklep.kaufland.pl/oferta/przeglad.html?kloffer-week=current'
URL_NEXT = 'https://sklep.kaufland.pl/oferta/przeglad.html?kloffer-week=next'
SKIP_SECTIONS = re.compile(r'AGD|elektro|Tekstylia|dla dzieci|Zabawki|samochod|sezonowe', re.I)

# Wykonywane w stronie. Zwraca wiersze: [sekcja, ważność, marka, nazwa, opakowanie, cena_za_jednostkę, rabat, cena, cena_przed, z_kartą]
EXTRACT_JS = r"""
() => {
  const tx = (e, s) => { const n = e.querySelector(s); return n ? n.textContent.replace(/\s+/g, ' ').trim() : ''; };
  const root = document.querySelector('main') || document.body;
  let sec = '', valid = '', prevLeaf = '';
  const rows = [];
  for (const e of root.querySelectorAll('*')) {
    if (e.classList && e.classList.contains('k-product-tile')) {
      rows.push([sec, valid, tx(e, '.k-product-tile__title'), tx(e, '.k-product-tile__subtitle'), tx(e, '.k-product-tile__unit-price'),
        tx(e, '.k-product-tile__base-price'), tx(e, '.k-price-tag__discount'), tx(e, '.k-price-tag__price'),
        tx(e, '.k-price-tag__old-price-line-through'), /Cena z kart/i.test(e.textContent) ? 1 : 0]);
    } else if (e.children.length === 0 && !e.closest('.k-product-tile')) {
      const s = e.textContent.trim();
      if (/^Oferta ważna/.test(s)) { valid = s; sec = prevLeaf; }
      else if (s && s.length < 60) prevLeaf = s;
    }
  }
  return rows;
}
"""


def parse_rows(rows, today=None):
    """Wiersze ze strony -> (oferty, ostrzeżenia). Czysta funkcja, testowana bez przeglądarki."""
    today = today or dt.date.today()
    offers, warns, seen = [], [], set()
    for sec, valid, brand, sub, pack_t, base_t, disc, price_t, old_t, card in rows:
        sec = re.sub(r'\s*\d{2}\.\d{2}\.\d{4}.*$', '', sec or '').strip()
        if SKIP_SECTIONS.search(sec):
            continue
        name = ' '.join(x for x in [brand, sub] if x).strip()
        price = money(price_t)
        if not name or not price:
            continue
        old = money(old_t)
        pack = parse_pack(pack_t) or parse_pack(name)
        key = (name, pack_t, price)
        if key in seen:
            continue
        seen.add(key)
        vf, vt = parse_valid(valid, today)
        if not vt:
            warns.append(f'brak daty ważności: {name}')
            continue
        conf, note = verify(price, pack, base_t)
        if not pack:
            pack = dict(amount=1.0, unit='szt', conf='check', note='')
        offers.append(make_offer('Kaufland', name, pack, price, old if old and old > price else 0, vf, vt,
                                 cond='z kartą Kaufland Card XTRA' if card else '', section=sec, conf=conf, note=note, brand=brand))
    return offers, warns


def collect(page, url=URL_CURRENT, today=None):
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    try:
        page.wait_for_selector('.k-product-tile', timeout=30000)
    except Exception:
        title = (page.title() or '')[:80]
        raise RuntimeError(f'Kaufland: nie widzę ofert (tytuł strony: „{title}”). Możliwa blokada lub zmiana strony; niczego nie omijam.')
    page.wait_for_timeout(2500)  # dociągnięcie reszty kafelków
    rows = page.evaluate(EXTRACT_JS)
    return parse_rows(rows, today)
