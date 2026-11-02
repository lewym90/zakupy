// Lista zakupów: pozycje grupowane sklepami. Pozycja z oferty to kopia z chwili dodania, bo oferty z serwera się zmieniają.
import { offerCalc, packLabel, unitPrice, promoLabel, whereLabel, isSure, isHidden, flyerUrl } from './offers.js';

export function itemFromOffer(o, fmtMoney) {
  const sure = isSure(o), u = sure ? unitPrice(o) : null;
  return {
    id: 'o:' + o.id, offerId: o.id, name: o.name, store: o.store, price: offerCalc(o).total, qty: 1, done: false,
    pack: sure ? packLabel(o) : (o.printed || ''), unit: u ? { label: u.label, price: u.price } : null,
    promo: promoLabel(o, fmtMoney), where: whereLabel(o), cond: o.cond || '', deposit: o.deposit || 0,
    from: o.from || '', until: o.until || '', unsure: isHidden(o), url: flyerUrl(o),
  };
}
export const manualItem = (id, name, store) => ({ id, name, store, price: 0, qty: 1, done: false });

// Sklepy z czymś do kupienia najpierw; w sklepie kupione lądują na dole.
export function byStore(items, only) {
  const m = new Map();
  for (const i of items) {
    if (only && i.store !== only) continue;
    if (!m.has(i.store)) m.set(i.store, []);
    m.get(i.store).push(i);
  }
  return [...m].map(([store, rows]) => {
    const left = rows.filter(i => !i.done);
    return { store, items: [...left, ...rows.filter(i => i.done)], left: left.length, sum: left.reduce((s, i) => s + (i.price || 0) * (i.qty || 1), 0), noPrice: left.filter(i => !i.price).length };
  }).sort((a, b) => (!a.left - !b.left) || a.store.localeCompare(b.store, 'pl'));
}
