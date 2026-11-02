// Porównywanie ofert. Całe liczenie jest deterministyczne (bez AI).
// Oferta: { price (grosze), amount (ile w JEDNYM opakowaniu), unit (szt|kg|g|l|ml),
//           mode: 'unit' | 'bundle' | 'nth', need (ile opakowań trzeba kupić), pct (dla 'nth': o ile % tańsze) }
//  - unit   : cena `price` za jedno opakowanie (need = 1)
//  - bundle : `need` opakowań razem za `price` (np. 3 butelki za 9,99)
//  - nth    : kup `need` opakowań po `price`, ostatnie jest o `pct`% tańsze (np. drugi 50% taniej)
import { norm } from './util.js';

const TO_BASE = { szt: ['szt', 1], kg: ['kg', 1], g: ['kg', 0.001], l: ['l', 1], ml: ['l', 0.001] };
export const UNITS = ['szt', 'kg', 'g', 'l', 'ml'];
// Oferta z niepotwierdzonym odczytem: nie pokazujemy z niej żadnych liczb pochodnych i nie porównujemy jej.
export const isSure = o => o.conf !== 'check';

export function offerCalc(o) {
  const [base, f] = TO_BASE[o.unit] || ['szt', 1];
  const need = Math.max(1, Math.round(o.need || 1));
  const amount = (o.amount > 0 ? o.amount : 1) * f; // w jednostce bazowej, jedno opakowanie
  let total;
  if (o.mode === 'bundle') total = o.price;
  else if (o.mode === 'nth') total = o.price * (need - 1) + o.price * (1 - (o.pct || 0) / 100);
  else total = o.price * need; // 'unit': need = 1, ale gdyby było więcej, każde po cenie
  const qty = amount * need;
  return {
    base, need,
    total: Math.round(total),                // ile zapłacisz za całą promocyjną partię
    pack: Math.round(total / need),          // średnio za jedno opakowanie
    qty,                                     // ile litrów/kg/sztuk dostajesz
    up: Math.round(total / qty),             // cena za l / kg / szt (grosze)
  };
}

// Rodziny produktów: co uznajemy za "ten sam rodzaj" przy porównaniu. Pierwsze trafienie wygrywa.
// Klucz z $ na końcu = dokładne słowo; z odstępem = fragment frazy; reszta = początek słowa.
export const FAMILIES = [
  ['cola', 'Cola i napoje gazowane', ['cola', 'pepsi', 'fanta', 'sprite', 'schweppes', 'dr pepper', '7up', 'napoj gazowany']],
  ['woda', 'Woda', ['woda$', 'wody$']],
  ['sok', 'Soki', ['sok$', 'soki$', 'nektar']],
  ['piwo', 'Piwo', ['piwo', 'lager', 'pils']],
  ['mleko', 'Mleko', ['mleko$']],
  ['maslo', 'Masło', ['maslo']],
  ['jaja', 'Jajka', ['jaja$', 'jajka$']],
  ['twarog', 'Twaróg', ['twarog']],
  ['ser', 'Ser żółty', ['ser$', 'gouda', 'edamski', 'ser zolty']],
  ['jogurt', 'Jogurty', ['jogurt']],
  ['smietana', 'Śmietana', ['smietana', 'smietanka']],
  ['kawa', 'Kawa', ['kawa$', 'kawy$', 'kawe$']],
  ['herbata', 'Herbata', ['herbata']],
  ['makaron', 'Makaron', ['makaron']],
  ['ryz', 'Ryż', ['ryz$']],
  ['maka', 'Mąka', ['maka$']],
  ['cukier', 'Cukier', ['cukier$']],
  ['olej', 'Olej', ['olej$']],
  ['oliwa', 'Oliwa', ['oliwa']],
  ['szynka', 'Szynka', ['szynka', 'szynki']],
  ['kielbasa', 'Kiełbasa', ['kielbasa', 'kielbasy']],
  ['parowki', 'Parówki', ['parowk']],
  ['kurczak', 'Kurczak', ['kurczak', 'kurcz', 'podudzi']],
  ['schab', 'Schab', ['schab']],
  ['karkowka', 'Karkówka', ['karkow']],
  ['mielone', 'Mięso mielone', ['mielone$']],
  ['losos', 'Łosoś', ['losos']],
  ['jablka', 'Jabłka', ['jablk']],
  ['pomidory', 'Pomidory', ['pomidor']],
  ['banany', 'Banany', ['banan']],
  ['ziemniaki', 'Ziemniaki', ['ziemniak']],
  ['chleb', 'Chleb', ['chleb']],
  ['pizza', 'Pizza mrożona', ['pizza']],
  ['papier', 'Papier toaletowy', ['papier toaletowy']],
  ['plyn-naczynia', 'Płyn do naczyń', ['plyn do naczyn']],
  ['proszek', 'Proszek i kapsułki do prania', ['proszek do prania', 'kapsulki do prania', 'zel do prania']],
];
const PREP = FAMILIES.map(([id, n, ks]) => ({ id, n, ks: ks.map(k => (k.endsWith('$') ? norm(k.slice(0, -1)) + '$' : norm(k))) }));

export function familyOf(name) {
  const n = norm(name), toks = n.split(' ');
  for (const f of PREP) for (const k of f.ks) {
    if (k.endsWith('$')) { if (toks.includes(k.slice(0, -1))) return { id: f.id, n: f.n }; }
    else if (k.includes(' ')) { if (n.includes(k)) return { id: f.id, n: f.n }; }
    else if (toks.some(t => t.startsWith(k))) return { id: f.id, n: f.n };
  }
  return null;
}

// Grupy do porównania: ta sama rodzina i ta sama jednostka bazowa, min. 2 oferty.
export function compareGroups(offers, today) {
  const map = new Map();
  for (const o of offers) {
    if (o.until < today || !isSure(o)) continue;
    const fam = familyOf(o.name); if (!fam) continue;
    const c = offerCalc(o), key = fam.id + '|' + c.base;
    if (!map.has(key)) map.set(key, { id: key, fam, base: c.base, rows: [] });
    map.get(key).rows.push({ o, c });
  }
  const out = [];
  for (const g of map.values()) {
    if (g.rows.length < 2) continue;
    g.rows.sort((a, b) => a.c.up - b.c.up);
    const best = g.rows[0].c.up;
    g.rows.forEach((r, i) => { r.rank = i + 1; r.over = best > 0 ? (r.c.up - best) / best : 0; });
    g.per = g.base === 'kg' ? (g.rows.some(r => r.c.qty < 1) ? '100g' : 'kg') : undefined; // jedna jednostka w całej grupie
    g.best = g.rows[0];
    g.stores = new Set(g.rows.map(r => r.o.store)).size;
    g.spread = g.rows[g.rows.length - 1].c.up - best; // różnica między najdroższą a najtańszą (grosze za jednostkę)
    out.push(g);
  }
  // najpierw grupy z różnymi sklepami i największą różnicą (tam wybór ma największe znaczenie)
  out.sort((a, b) => (b.stores > 1) - (a.stores > 1) || (b.spread / (a.best.c.up || 1)) - (a.spread / (b.best.c.up || 1)) || a.fam.n.localeCompare(b.fam.n, 'pl'));
  return out;
}

// Tekst opisujący warunek promocji, np. "3 × 1,5 l za 9,99 zł".
export function offerLabel(o, fmtMoney, fmtNum) {
  const c = offerCalc(o), u = o.unit, a = fmtNum(o.amount);
  if (o.mode === 'bundle' && c.need > 1) return `${c.need} × ${a} ${u} razem za ${fmtMoney(o.price)}`;
  if (o.mode === 'nth' && c.need > 1) return `${c.need} × ${a} ${u}, ostatnie ${o.pct}% taniej`;
  return `${a} ${u} za ${fmtMoney(o.price)}`;
}

// ---------- Wyświetlanie: cena opakowania, zawartość, przeliczenie ----------
// Rzeczowniki dla sztuk, rozpoznawane po nazwie: [wzorzec, l.poj., l.mn. (2-4), dopełniacz l.mn. (5+), biernik "za 1 ..."]
const NOUNS = [
  ['papier toaletowy|toaletow|recznik papierowy|recznik kuchenny', 'rolka', 'rolki', 'rolek', 'rolkę'],
  ['papier do pieczenia|folia aluminiowa', 'arkusz', 'arkusze', 'arkuszy', 'arkusz'],
  ['kapsulk', 'kapsułka', 'kapsułki', 'kapsułek', 'kapsułkę'],
  ['tabletk', 'tabletka', 'tabletki', 'tabletek', 'tabletkę'],
  ['saszetk', 'saszetka', 'saszetki', 'saszetek', 'saszetkę'],
  ['chusteczk', 'chusteczka', 'chusteczki', 'chusteczek', 'chusteczkę'],
  ['listk', 'listek', 'listki', 'listków', 'listek'],
  ['wor(ki|ek)|woreczk', 'worek', 'worki', 'worków', 'worek'],
  ['pieluch', 'pielucha', 'pieluchy', 'pieluch', 'pieluchę'],
  ['\\bjaj', 'jajko', 'jajka', 'jaj', 'jajko'],
];
const NOUN_RE = NOUNS.map(n => ({ re: new RegExp(n[0]), n: n.slice(1) }));
const DEFAULT_NOUN = ['sztuka', 'sztuki', 'szt.', 'sztukę'];
export function countNoun(name) { const t = norm(name); const f = NOUN_RE.find(x => x.re.test(t)); return f ? f.n : DEFAULT_NOUN; }
const numFmt = n => String(Math.round(n * 1000) / 1000).replace('.', ',');
function plural(n, noun) {
  const i = Math.round(n);
  if (Math.abs(n - i) > 1e-9) return noun[2];
  if (i === 1) return noun[0];
  const m10 = i % 10, m100 = i % 100;
  return m10 >= 2 && m10 <= 4 && !(m100 >= 12 && m100 <= 14) ? noun[1] : noun[2];
}
// Ilość (w jednostce bazowej kg/l/szt) jako tekst: 300 g, 1,5 kg, 330 ml, 8 rolek.
export function fmtQty(q, base, name) {
  if (base === 'kg') return q < 1 ? `${numFmt(q * 1000)} g` : `${numFmt(q)} kg`;
  if (base === 'l') return q < 1 ? `${numFmt(q * 1000)} ml` : `${numFmt(q)} l`;
  return `${numFmt(q)} ${plural(q, countNoun(name))}`;
}
// Zawartość jednego opakowania lub całej promocyjnej partii, np. "300 g", "8 rolek", "3 × 1,5 l = 4,5 l".
export function packLabel(o) {
  const c = offerCalc(o), [, f] = [0, ({ szt: 1, kg: 1, g: 0.001, l: 1, ml: 0.001 })[o.unit] || 1];
  const one = fmtQty((o.amount > 0 ? o.amount : 1) * f, c.base, o.name);
  if (c.need > 1 && (o.mode === 'bundle' || o.mode === 'nth')) return `${c.need} × ${one} = ${fmtQty(c.qty, c.base, o.name)}`;
  return one;
}
// Cena jednostkowa do pokazania: kg dla >= 1 kg, 100 g poniżej (lub wymuszone `force` = '100g'|'kg' w porównaniach), litr, rolka/arkusz/sztuka.
export function unitPrice(o, force) {
  const c = offerCalc(o);
  if (c.base === 'kg') {
    const per = force || (c.qty < 1 ? '100g' : 'kg');
    return per === '100g' ? { price: Math.round(c.total / c.qty / 10), label: '100 g', per } : { price: Math.round(c.total / c.qty), label: '1 kg', per };
  }
  if (c.base === 'l') return { price: Math.round(c.total / c.qty), label: '1 l', per: 'l' };
  const n = countNoun(o.name);
  return { price: Math.round(c.total / c.qty), label: '1 ' + n[3], per: 'szt' };
}

// Oznaczenie promocji dokładnie tak, jak w sklepie: "3 za 2", "3 za 9,99 zł", "2. produkt −50%". Brak dla zwykłej ceny.
export function promoLabel(o, fmtMoney) {
  const need = Math.max(1, Math.round(o.need || 1));
  if (o.promo) return o.promo; // napis dokładnie taki, jak w sklepie
  if (o.mode === 'bundle' && need > 1) return o.pay && o.pay < need ? `${need} za ${o.pay}` : `${need} za ${fmtMoney(o.price)}`;
  if (o.mode === 'nth' && need > 1) return o.pct >= 100 ? `${need}. produkt gratis` : `${need}. produkt −${numFmt(o.pct)}%`;
  return '';
}
// Gdzie szukać oferty w sklepie (promocje wielosztukowe bywają poza zwykłą półką).
export function whereLabel(o) {
  if (o.store === 'Lidl') return o.page ? `gazetka Lidl, str. ${o.page}` : 'gazetka Lidl';
  if (o.section) return `dział „${o.section}”`;
  return '';
}
// Adres strony gazetki Lidla, żeby można było sprawdzić ofertę na źródle.
export function flyerUrl(o) {
  return o.store === 'Lidl' && o.page && o.section ? `https://www.lidl.pl/l/pl/gazetki/${encodeURIComponent(o.section)}/view/flyer/page/${o.page}` : '';
}
export const isMulti = o => (o.mode === 'bundle' || o.mode === 'nth') && Math.round(o.need || 1) > 1;
