// Stałe produkty, najtańszy koszyk, spiżarnia i plan miesiąca. Czyste funkcje, całe liczenie w kodzie.
// Do koszyka i alertów trafiają wyłącznie oferty z potwierdzoną ceną za jednostkę (isSure).
import { offerCalc, familyOf, isSure } from './offers.js';
import { catOf } from './cats.js';
import { norm } from './util.js';

const stem = t => (t.length > 3 ? t.slice(0, -1) : t);

// Oferty pasujące do wpisanej nazwy, od najniższej ceny za jednostkę.
// Najpierw słowa z nazwy (w tej samej kategorii), dopiero bez trafień rodzina produktu.
export function matchOffers(name, offers, today) {
  const toks = norm(name).split(' ').filter(Boolean);
  if (!toks.length) return [];
  const cat = catOf(name), fam = familyOf(name);
  const live = offers.filter(o => o.until >= today && (!o.from || o.from <= today) && isSure(o));
  let hit = live.filter(o => {
    const ts = norm(o.name).split(' ');
    return toks.every(w => ts.some(t => t.startsWith(stem(w)))) && (cat === 'inne' || (o.cat || catOf(o.name)) === cat);
  });
  if (!hit.length && fam) hit = live.filter(o => { const f = familyOf(o.name); return f && f.id === fam.id; });
  const rows = hit.map(o => ({ o, c: offerCalc(o) }));
  const count = {}; for (const r of rows) count[r.c.base] = (count[r.c.base] || 0) + 1;
  const base = Object.keys(count).sort((a, b) => count[b] - count[a])[0]; // nie mieszamy kg ze sztukami
  return rows.filter(r => r.c.base === base).sort((a, b) => a.c.up - b.c.up);
}

export function basket(names, offers, today) {
  const found = [], missing = [], stores = new Map();
  for (const name of names) {
    const m = matchOffers(name, offers, today);
    if (!m.length) { missing.push(name); continue; }
    const row = { name, o: m[0].o, c: m[0].c, alts: m.length - 1 };
    found.push(row);
    if (!stores.has(row.o.store)) stores.set(row.o.store, { store: row.o.store, rows: [], sum: 0 });
    const s = stores.get(row.o.store); s.rows.push(row); s.sum += row.c.total;
  }
  const list = [...stores.values()].sort((a, b) => b.rows.length - a.rows.length || a.store.localeCompare(b.store, 'pl'));
  return { stores: list, missing, total: list.reduce((a, s) => a + s.sum, 0), found: found.length };
}

export const pantryLow = items => items.filter(i => i.qty <= i.min);

// Ile można wydać na dzień po odjęciu tego, co już wydane i zaplanowane.
export function planSummary({ limit, spent, plan, listSum = 0, day, days }) {
  const planned = plan.filter(p => !p.done).reduce((s, p) => s + p.amount, 0);
  const free = limit - spent - planned - listSum, left = Math.max(1, days - day + 1);
  return { planned, free, left, perDay: limit ? Math.max(0, Math.floor(free / left)) : 0 };
}
