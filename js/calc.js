// Cała logika liczenia jest tutaj i jest deterministyczna. Żadnego AI w wyliczeniach.
import { norm, median, ymOf } from './util.js';

export const lineSum = r => r.lines.reduce((s, l) => s + (l.total || 0), 0);
export const receiptTotal = r => (r.declared > 0 ? r.declared : lineSum(r));

// Wszystkie zakupy jako płaska lista z ceną za jednostkę (grosze za szt/kg/l).
export function entries(receipts) {
  const out = [];
  for (const r of receipts) for (const l of r.lines) {
    if (!l.name || !(l.qty > 0) || !(l.total > 0)) continue;
    out.push({ key: norm(l.name), name: l.name, cat: l.cat, date: r.date, store: r.store, unit: l.unit,
      qty: l.qty, total: l.total, up: Math.round(l.total / l.qty), reg: l.reg || 0 });
  }
  return out;
}

export function products(receipts) {
  const m = new Map();
  for (const e of entries(receipts)) { if (!m.has(e.key)) m.set(e.key, []); m.get(e.key).push(e); }
  const res = [];
  for (const [key, arr] of m) {
    arr.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    const last = arr[arr.length - 1];
    const same = arr.filter(e => e.unit === last.unit);
    const ups = same.map(e => e.up);
    res.push({ key, name: last.name, cat: last.cat, unit: last.unit, n: same.length, skipped: arr.length - same.length,
      last: last.up, lastDate: last.date, lastStore: last.store, min: Math.min(...ups), med: median(ups), hist: same });
  }
  return res;
}

export function matchProduct(prods, name) {
  const k = norm(name);
  if (k.length < 3) return null;
  let best = null;
  for (const p of prods) {
    const hit = p.key === k || (k.length >= 4 && p.key.includes(k)) || (p.key.length >= 4 && k.includes(p.key));
    if (hit && (!best || p.n > best.n)) best = p;
  }
  return best;
}

// Ocena okazji względem WŁASNYCH paragonów. Progi (3 zakupy, 10%, 3%, 5%) to założenia robocze, jeszcze niezmierzone.
export function verdict(up, unit, prod) {
  if (!prod) return { t: 'nodata', txt: 'Jeszcze tego nie kupowaliście' };
  if (prod.unit !== unit) return { t: 'nodata', txt: 'Na paragonach cena jest w innej jednostce (' + prod.unit + ')' };
  if (prod.n < 3) return { t: 'few', txt: 'Za mało zakupów do oceny (' + prod.n + ' z 3)' };
  if (up <= prod.min) return { t: 'best', txt: 'Najniższa cena z Waszych paragonów' };
  const pct = (prod.med - up) / prod.med;
  if (pct >= 0.10) return { t: 'good', txt: Math.round(pct * 100) + '% poniżej Waszej zwykłej ceny' };
  if (pct >= 0.03) return { t: 'slight', txt: 'Nieco taniej niż zwykle' };
  if (pct > -0.05) return { t: 'norm', txt: 'Zwykła cena' };
  return { t: 'bad', txt: 'Drożej niż zwykle' };
}

export function monthStats(receipts, ym) {
  const rs = receipts.filter(r => ymOf(r.date) === ym);
  let spent = 0, saved = 0;
  const cats = {};
  for (const r of rs) {
    const tot = receiptTotal(r);
    spent += tot;
    let assigned = 0;
    for (const l of r.lines) {
      if (!l.total) continue;
      cats[l.cat] = (cats[l.cat] || 0) + l.total;
      assigned += l.total;
      if (l.total < 0) saved += -l.total;            // rabat zapisany jako osobna pozycja
      else if (l.reg > l.total) saved += l.reg - l.total; // cena regularna wpisana przy pozycji
    }
    if (tot > assigned) cats.__rest = (cats.__rest || 0) + (tot - assigned);
  }
  return { rs, spent, saved, cats, n: rs.length };
}

export const monthTotals = (receipts, yms) => yms.map(ym => ({ ym, spent: monthStats(receipts, ym).spent }));
