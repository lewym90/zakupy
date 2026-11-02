"""Wspólne, deterministyczne przeliczanie ofert. Żadnego AI: tylko wyrażenia regularne i arytmetyka.
Ceny w groszach (int). Jednostki bazowe: kg, l, szt."""
import datetime as dt
import hashlib
import re

NUM = r'(\d+(?:[.,]\d+)?)'
TO_BASE = {'g': ('kg', 0.001), 'kg': ('kg', 1.0), 'ml': ('l', 0.001), 'l': ('l', 1.0), 'szt': ('szt', 1.0)}


def fnum(s):
    return float(str(s).replace(',', '.').replace(' ', ''))


def money(s):
    """'13,98' / '1 299,00' / '13.98 zł' -> 1398 (grosze) albo None."""
    s = str(s or '').replace(' ', ' ')
    m = re.search(r'\d+(?: \d{3})*(?:[.,]\d{1,2})?', s)
    if not m:
        return None
    return int(round(fnum(m.group(0)) * 100))


def parse_pack(text):
    """Opakowanie -> {amount, unit, conf, note}. unit: g|kg|ml|l|szt. conf 'check' gdy tekst jest niejednoznaczny."""
    t = (text or '').lower().replace(' ', ' ')
    t = re.sub(r'\s+', ' ', t).strip()
    m = re.search(NUM + r'\s*(kg|g|ml|l)\b\s*\+\s*' + NUM + r'\s*(kg|g|ml|l)\b', t)  # 400 g + 50 g sos
    if m and m.group(2) == m.group(4):
        return dict(amount=fnum(m.group(1)) + fnum(m.group(3)), unit=m.group(2), conf='ok', note='')
    m = re.search(r'(\d+)\s*x\s*' + NUM + r'\s*(kg|g|ml|l)\b', t)  # 4 x 125 g
    if m:
        return dict(amount=int(m.group(1)) * fnum(m.group(2)), unit=m.group(3), conf='ok', note=f'{m.group(1)} szt. w opakowaniu')
    m = re.search(NUM + r'\s*[/-]\s*' + NUM + r'?[^0-9]{0,3}\s*(kg|g|ml|l)?\b', t)  # 250/230 g, 181-165 g
    if m and re.search(NUM + r'\s*[/-]\s*\d', t):
        unit = None
        mu = re.search(r'(kg|g|ml|l)\b', t[m.start():])
        if mu:
            unit = mu.group(1)
        if unit:
            return dict(amount=fnum(m.group(1)), unit=unit, conf='check', note='kilka wariantów wagi: ' + text.strip())
    m = re.search(NUM + r'\s*(kg|g|ml|l)\b', t)
    if m:
        return dict(amount=fnum(m.group(1)), unit=m.group(2), conf='ok', note='')
    m = re.search(r'(\d+)\s*(?:szt|sztuk)\b', t)
    if m:
        return dict(amount=float(m.group(1)), unit='szt', conf='ok', note='')
    if re.search(r'\bsztuk[ai]?\b|\bszt\b', t):
        return dict(amount=1.0, unit='szt', conf='ok', note='')
    m = re.search(NUM + r'\s*m\b', t)  # folie, rękawy: cena za rolkę
    if m:
        return dict(amount=1.0, unit='szt', conf='ok', note='rolka ' + m.group(0))
    return None


def base_of(amount, unit):
    b, f = TO_BASE[unit]
    return b, amount * f


def unit_price(price, amount, unit):
    """cena (grosze) za jedną jednostkę bazową (kg, l, szt), w groszach (float)."""
    b, q = base_of(amount, unit)
    return b, price / q if q else None


def parse_base_price(text):
    """'1 kg 19,98' / '100 g 0,82' / '1 szt 0,47' -> (jednostka bazowa, grosze za jednostkę bazową) albo None.
    Wiele wariantów ('1 kg 31,96/34,74') => None (nie weryfikujemy)."""
    t = re.sub(r'\s+', ' ', (text or '').lower().replace('=', '').replace('(', '').replace(')', '')).strip()
    if '/' in t:
        return None
    m = re.match(NUM + r'?\s*(kg|g|ml|l|szt|m)\s+' + NUM + r'$', t)
    if not m:
        return None
    n = fnum(m.group(1)) if m.group(1) else 1.0
    u, price = m.group(2), fnum(m.group(3)) * 100
    if u == 'm':
        return ('m', price / n)
    b, f = TO_BASE[u]
    return b, price / (n * f)


def verify(price, pack, base_text):
    """Porównuje własne przeliczenie z ceną za jednostkę podaną przez sklep. Zwraca ('ok'|'check', uwaga)."""
    if not pack:
        return 'check', 'nie rozpoznano opakowania'
    if pack['conf'] == 'check':
        return 'check', pack['note']
    if not base_text:
        return 'ok', ''
    pb = parse_base_price(base_text)
    if not pb:
        return 'ok', ''
    ub, up = unit_price(price, pack['amount'], pack['unit'])
    if pb[0] == 'm' or pb[0] != ub:
        return 'ok', ''
    if abs(up - pb[1]) / pb[1] <= 0.02:
        return 'ok', ''
    return 'check', f'cena za jednostkę wg sklepu {pb[1] / 100:.2f}, wg opakowania {up / 100:.2f}'


def parse_valid(text, today):
    """'Oferta ważna od 29.10. do 04.11.' / 'Oferta ważna 02.11.' -> (od, do) jako RRRR-MM-DD albo (None, None)."""
    ds = re.findall(r'(\d{1,2})\.(\d{1,2})\.(?:(\d{4}))?', text or '')
    if not ds:
        return None, None

    def mk(d, mth, y, ref):
        return dt.date(int(y) if y else ref, int(mth), int(d))
    try:
        a = mk(*ds[0], today.year)
        b = mk(*ds[-1], today.year) if len(ds) > 1 else a
    except ValueError:
        return None, None
    if not ds[0][2] and not ds[-1][2] and b < a:  # przełom roku: 28.12. - 03.01.
        if today.month <= 2:
            a = a.replace(year=a.year - 1)
        else:
            b = b.replace(year=b.year + 1)
    return a.isoformat(), b.isoformat()


def make_offer(store, name, pack, price, old, valid_from, valid_to, cond='', section='', src='html', conf='ok', note='', brand=''):
    pid = hashlib.sha1('|'.join(map(str, [store, name, pack['amount'], pack['unit'], price, valid_to])).encode()).hexdigest()[:12]
    return {
        'id': pid, 'store': store, 'name': name, 'brand': brand, 'price': price, 'old': old or 0,
        'amount': round(pack['amount'], 4), 'unit': pack['unit'], 'mode': 'unit', 'need': 1, 'pct': 0,
        'from': valid_from, 'until': valid_to, 'cond': cond, 'section': section, 'src': src, 'conf': conf, 'note': note,
    }
