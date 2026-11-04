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


_N = r'(\d{1,2})'
_MB_PAY = re.compile(r'\b' + _N + r'\s*(?:w\s+cenie|za)\s*' + _N + r'\b(?![.,]\d|\s*(?:zł|zl|pln))', re.I)          # 3 w cenie 2, 3 za 2
_MB_PLUS = re.compile(r'\b' + _N + r'\s*\+\s*' + _N + r'\s*(?:gratis\w*|gratis)', re.I)                              # 2+1 gratis
_MB_PLUS_BARE = re.compile(r'(?<![\d.,])([1-9])\s*\+\s*([1-9])(?![\d.,]|\s*(?:g|kg|ml|l|szt|dag)\b)', re.I)             # 2+1
_MB_TOTAL = re.compile(r'\b' + _N + r'\s*za\s*(\d+(?:[.,]\d{1,2})?)\s*(?:zł|zl|pln)', re.I)                          # 3 za 9,99 zł
_MB_NTH = [
    re.compile(r'(?:drugi|kolejny|2\.)\s*(?:produkt|artyku\w*|szt\w*)?\s*(?:o\s*)?-?\s*(\d{1,3})\s*%', re.I),
    re.compile(r'-?\s*(\d{1,3})\s*%\s*(?:taniej\s*)?(?:na|przy zakupie)\s*(?:drugi|kolejny|2\.)', re.I),
]


def parse_multibuy(text):
    """Tekst promocji -> {'need','pay'} | {'need','total'} | {'need':2,'pct'} albo None. Obsługuje: 3 za 2, 3 w cenie 2, 2+1 gratis,
    3 za 9,99 zł, drugi produkt -50% / drugi gratis."""
    t = (text or '').replace('\u00a0', ' ')
    m = _MB_TOTAL.search(t)
    if m and int(m.group(1)) >= 2:
        return {'need': int(m.group(1)), 'total': money(m.group(2))}
    m = _MB_PAY.search(t)
    if m and int(m.group(1)) >= 2 and 1 <= int(m.group(2)) < int(m.group(1)):
        return {'need': int(m.group(1)), 'pay': int(m.group(2))}
    m = _MB_PLUS.search(t) or _MB_PLUS_BARE.search(t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return {'need': a + b, 'pay': a}
    for rx in _MB_NTH:
        m = rx.search(t)
        if m and 0 < int(m.group(1)) <= 100:
            return {'need': 2, 'pct': float(m.group(1))}
    if re.search(r'(?:drugi|kolejny)\s+(?:produkt\s+|artyku\w*\s+)?gratis', t, re.I):
        return {'need': 2, 'pct': 100.0}
    return None


def apply_multibuy(o, mb, single_price):
    """Nakłada promocję wielosztukową na ofertę. single_price = cena jednej sztuki (grosze), o ile znana."""
    if not mb:
        return o
    if 'pay' in mb and single_price:
        o['mode'], o['need'], o['pay'], o['price'] = 'bundle', mb['need'], mb['pay'], single_price * mb['pay']
    elif 'total' in mb and mb['total']:
        o['mode'], o['need'], o['price'] = 'bundle', mb['need'], mb['total']
    elif 'pct' in mb and single_price:
        o['mode'], o['need'], o['pct'], o['price'] = 'nth', mb['need'], mb['pct'], single_price
    return o


# ---------- Interpretacja dosłownego odczytu (Gemini tylko czyta, liczy wyłącznie ten kod) ----------
TOL = 0.02  # zgodność z ceną jednostkową wydrukowaną w gazetce
_WORDS = {'dwu': 2, 'trzy': 3, 'cztero': 4, 'pięcio': 5, 'piecio': 5, 'sześcio': 6, 'szescio': 6, 'ośmio': 8, 'osmio': 8, 'dziesięcio': 10, 'dziesiecio': 10, 'dwunasto': 12}
_WORD_RE = re.compile(r'\b(' + '|'.join(_WORDS) + r')(?:sztuk\w*|pak\w*)', re.I)
_KAUCJA_RE = re.compile(r'\+?\s*(?:\+\s*)?kaucj\w*\s*[:=]?\s*' + NUM + r'\s*(?:zł|zl|pln)?', re.I)
_LINE_RE = re.compile(r'(\d{1,2})\s*[x×*]\s*(\d+(?:[.,]\d{1,2})?)(?!\s*(?:kg|g|ml|l|szt)\b)', re.I)


def parse_pack_parts(text):
    """Opakowanie -> {count, each, unit, conf, note, word}. Tylko rozkłada tekst; nie mnoży niczego drugi raz.
    'Dwusztuk 2 x 1 L' -> 2 sztuki po 1 l; '500 g' -> 1 sztuka po 500 g."""
    t = re.sub(r'\s+', ' ', (text or '').lower().replace('\u00a0', ' ').replace('×', 'x').replace('*', 'x')).strip()
    w = _WORD_RE.search(t)
    word = w.group(0) if w else ''
    m = re.search(r'(\d+)\s*x\s*' + NUM + r'\s*(kg|g|ml|l)\b', t)
    if m:
        return dict(count=int(m.group(1)), each=fnum(m.group(2)), unit=m.group(3), conf='ok', note='', word=word)
    p = parse_pack(t)
    if not p:
        return None
    return dict(count=_WORDS[w.group(1)] if w else 1, each=p['amount'], unit=p['unit'], conf=p['conf'], note=p['note'], word=word)


def parse_anchor(text):
    """Cena jednostkowa z gazetki -> {base, up (grosze za kg/l/szt), deposit (grosze|None)} albo None. Kaucja jest osobna i nie wchodzi do ceny.
    '1 L = 4,99 + kaucja 1,00 zł' -> l, 499, 100."""
    t = (text or '').lower().replace('\u00a0', ' ')
    k = _KAUCJA_RE.search(t)
    deposit = int(round(fnum(k.group(1)) * 100)) if k else None
    t = _KAUCJA_RE.sub(' ', t).replace('zł', ' ').replace('zl', ' ').replace('pln', ' ')
    m = re.search(NUM + r'\s*/\s*' + NUM + r'?\s*(kg|g|ml|l|szt)\b', t)  # 4,99/1 l
    if m and re.search(r'/\s*\d*\s*(kg|g|ml|l|szt)\b', t):
        price, n, u = fnum(m.group(1)), fnum(m.group(2)) if m.group(2) else 1.0, m.group(3)
    else:
        if re.search(r'\d\s*/\s*\d|\d[.,]\d{2}\s*-\s*\d', t):
            return None  # kilka wariantów (31,96/34,74); „10,15/but.” to zwykła cena sztuki
        m = re.search(NUM + r'?\s*(kg|g|ml|l|szt)\b\.?\s*=?\s*' + NUM, t)
        if not m:
            return None
        n, u, price = fnum(m.group(1)) if m.group(1) else 1.0, m.group(2), fnum(m.group(3))
    b, f = TO_BASE[u]
    return dict(base=b, up=price * 100 / (n * f), deposit=deposit)


def variants_match(price, pack_text, unit_text):
    """Kilka wielkości w jednej cenie: '50 g, 55 g' i '100 g = 13,98/12,71'. Prawda, gdy wydrukowana cena zgadza się z którąś wielkością."""
    t = _KAUCJA_RE.sub(' ', (unit_text or '').lower().replace('zł', ' '))
    m = re.search(NUM + r'?\s*(kg|g|ml|l|szt)\b\.?\s*=?\s*(\d+[.,]\d{2}(?:\s*[/-]\s*\d+[.,]\d{2})+)', t)
    if not m:
        return False
    n, u = fnum(m.group(1)) if m.group(1) else 1.0, m.group(2)
    b, f = TO_BASE[u]
    ups = [fnum(x) * 100 / (n * f) for x in re.findall(r'\d+[.,]\d{2}', m.group(3))]
    sizes = []
    for a, a2, un in re.findall(NUM + r'(?:\s*[/-]\s*' + NUM + r')?\s*(kg|g|ml|l|szt)\b', (pack_text or '').lower()):
        for x in (a, a2):
            if x and TO_BASE[un][0] == b:
                sizes.append(fnum(x) * TO_BASE[un][1])
    return any(_near(price / s, up) for s in sizes for up in ups if s)


def _prices(text):
    t = _KAUCJA_RE.sub(' ', str(text if text is not None else ''))
    t = re.sub(r'\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l|szt)\b\.?\s*=?\s*\d+(?:[.,]\d+)?', ' ', t, flags=re.I)  # 1 L = 4,99
    return [int(round(fnum(x) * 100)) for x in re.findall(r'\d+[.,]\d{1,2}', t)]


def _line(*texts):
    """'4 x 7,99 zł za butelkę' -> (4, 799)."""
    for t in texts:
        m = _LINE_RE.search(_KAUCJA_RE.sub(' ', str(t or '')))
        if m and int(m.group(1)) >= 2:
            return int(m.group(1)), int(round(fnum(m.group(2)) * 100))
    return None


def _near(a, b, tol=TOL):
    return b > 0 and abs(a - b) / b <= tol


def _dedupe(xs):
    return list(dict.fromkeys(x for x in xs if x))


def interpret(name, pack_text, price, extra='', unit_text='', deposit='', promo=''):
    """Dosłowne teksty oferty -> dokładnie jedna interpretacja albo oznaczenie 'check'.
    Układamy możliwe odczytania i wybieramy to, które zgadza się z ceną jednostkową WYDRUKOWANĄ w gazetce.
    Gdy nic się nie zgadza, nie wolno podać liczb pochodnych: wynik to zwykła cena z conf='check'.
    Zwraca None, gdy nie ma ceny."""
    line = _line(price, extra)
    prs = _prices(price)
    big = max(prs) if prs else money(price)
    if line and not prs:
        big = line[0] * line[1]
    if not big or big <= 0:
        return None
    anchor = parse_anchor(unit_text) or parse_anchor(extra)
    dep = money(deposit) if deposit else None
    if dep is None and anchor:
        dep = anchor['deposit']
    if dep is None:
        k = _KAUCJA_RE.search(str(extra or ''))
        dep = int(round(fnum(k.group(1)) * 100)) if k else 0
    parts = parse_pack_parts(pack_text) or parse_pack_parts(name)
    if not parts and anchor and _near(big, anchor['up']):  # towar na wagę: cena za 1 kg / 1 l
        parts = dict(count=1, each=1.0, unit={'kg': 'kg', 'l': 'l', 'szt': 'szt'}[anchor['base']], conf='ok', note='', word='')
    if not parts:
        return dict(amount=1.0, unit='szt', price=big, mode='unit', need=1, conf='check', note='nie rozpoznano opakowania', deposit=dep, promo=(promo or '').strip()[:40])
    count, each, unit = parts['count'], parts['each'], parts['unit']
    q = count * each
    base, f = TO_BASE[unit]
    mb = parse_multibuy(promo or '')
    singles = _dedupe([line[1] if line else 0, *prs, *_prices(extra), big])
    hyps = []

    def hyp(need, amount, total, mode='bundle', pay=0, pct=0, tests=None):
        hyps.append(dict(need=need, amount=amount, total=int(round(total)), mode=mode, pay=pay, pct=pct,
                         tests=tests if tests is not None else [total / (need * amount * f)]))
    if mb and 'pay' in mb:
        for s in singles:
            hyp(mb['need'], q, s * mb['pay'], pay=mb['pay'], tests=[s / (q * f), s * mb['pay'] / (mb['need'] * q * f)])
    elif mb and 'total' in mb and mb['total']:
        need, x = mb['need'], mb['total']
        for a in _dedupe([each if count == need else q, q / need if count == 1 else 0]):
            hyp(need, a, x, tests=[x / (need * a * f)] + [s / (a * f) for s in singles if s != x])
    elif mb and 'pct' in mb:
        for s in singles:
            hyp(mb['need'], q, s, mode='nth', pct=mb['pct'], tests=[s / (q * f), s * (1 - mb['pct'] / 100) / (q * f)])
    else:
        n = count if count > 1 else (line[0] if line else 1)
        if n > 1:
            real_set = bool(line or parts['word'])  # „Dwusztuk”, „2 x 4,99 za butelkę”: kupujesz komplet
            if not real_set:
                hyp(1, q, big, mode='unit')  # „4 x 125 g” za 3,99: jedno opakowanie zbiorcze
            for a in _dedupe([each, q / n if count == 1 else 0]):
                # big * n tylko bez wydrukowanej linii „N x cena”; przy niej ilość kompletu byłaby liczona podwójnie
                for t in _dedupe([line[0] * line[1], big] if line else [big, big * n]):
                    hyp(n, a, t)
        else:
            hyp(1, q, big, mode='unit')

    chosen, note = None, ''
    # 1 kg, 1 l, 100 g, 1 szt.: gazetka nie drukuje osobnej ceny jednostkowej, bo jest nią sama cena i nie ma czego mnożyć
    exact = count == 1 and not line and (unit, each) in {('kg', 1), ('l', 1), ('g', 1000), ('ml', 1000), ('g', 100), ('ml', 100), ('szt', 1)}
    regular_note = re.search(r'przed obniżką|poza promocją', f'{extra} {unit_text}', re.I)
    if not anchor and not mb and (variants_match(big, pack_text, unit_text) or variants_match(big, pack_text, extra)):
        return dict(amount=q, unit=unit, price=big, mode='unit', need=1, conf='cena', note='kilka wariantów wielkości w tej samej cenie, więc cena za jednostkę zależy od wariantu', deposit=dep, promo='')
    if parts['conf'] != 'ok':
        note = parts['note']
    elif anchor and anchor['base'] == base:
        chosen = next((h for h in hyps if any(_near(v, anchor['up']) for v in h['tests'])), None)
        if not chosen and exact and not mb and regular_note and big < anchor['up']:  # wydrukowana cena jednostkowa to cena sprzed obniżki
            chosen = hyps[0]
        if not chosen:
            note = f"cena za jednostkę wg sklepu {anchor['up'] / 100:.2f}, odczyt jej nie potwierdza"
    elif line and _near(line[0] * line[1], big, 0.002):  # brak ceny jednostkowej, ale druk zgadza się sam ze sobą: 2 x 4,99 = 9,98
        chosen = next((h for h in hyps if h['need'] == line[0] and h['total'] == big), None)
    elif exact and not anchor:
        chosen = hyps[0]
    if not chosen and not note:
        note = 'brak ceny jednostkowej, by potwierdzić odczyt'
    label = (promo or '').strip() or parts['word'].capitalize()
    if not chosen:
        return dict(amount=q, unit=unit, price=big, mode='unit', need=1, conf='check', note=note, deposit=dep, promo=label[:40])
    r = dict(amount=chosen['amount'], unit=unit, price=chosen['total'], mode=chosen['mode'], need=chosen['need'], conf='ok', note='', deposit=dep, promo=label[:40] if chosen['need'] > 1 else '')
    if chosen['pay']:
        r['pay'] = chosen['pay']
    if chosen['pct']:
        r['pct'] = chosen['pct']
    return r


def clean_name(brand, nazwa, store=''):
    """Porządkuje nazwę z gazetki: bez gwiazdek, gramatury na końcu i powtórzonej marki; marką nie jest sam sklep."""
    n = re.sub(r'\*+', '', nazwa or '').strip(' ,')
    b = (brand or '').replace('*', '').strip()
    if b.lower() == store.lower():
        b = ''
    pack = re.compile(r',?\s*\d+(?:[.,]\d+)?(?:\s*x\s*\d+(?:[.,]\d+)?)?\s*(?:kg|g|ml|l|szt\.?)\s*$', re.I)
    tail = lambda t, w: t[:-len(w)].rstrip(' ,') if w and t.lower().endswith(w.lower()) and len(t) > len(w) else t
    for _ in range(2):
        n = tail(tail(pack.sub('', n).strip(' ,'), b), store)
    if n.isupper() and len(n) > 3:
        n = n.capitalize()
    if b and not n.lower().startswith(b.lower()):
        return f'{b} {n}'.strip()
    return n


def dedupe_offers(offers):
    """Ta sama oferta z kilku gazetek: zostaje jedna, pewniejsza i ważna najdłużej."""
    rank = {'ok': 2, 'cena': 1, 'check': 0}
    best = {}
    for o in offers:
        canon = re.sub(r'[^a-ząćęłńóśźż0-9]+', '', re.sub(r'\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l|szt)\b\.?', '', o['name'].lower()))
        k = (o['store'], canon, o.get('need', 1), o['price'])
        c = best.get(k)
        if c is None or (rank.get(o['conf'], 0), o['until']) > (rank.get(c['conf'], 0), c['until']):
            best[k] = o
    return list(best.values())
