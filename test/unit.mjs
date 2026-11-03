import { catOf } from '../js/cats.js';
import { parseMoney, parseNum, norm } from '../js/util.js';
import { verdict, products, monthStats } from '../js/calc.js';
let bad = 0; const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('FAIL', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
const cats = { 'Karkówka wieprzowa': 'mieso', 'Filet z dorsza': 'ryby', 'Kiełbasa śląska': 'wedliny', 'Mleko UHT 3,2%': 'nabial', 'Ser żółty gouda': 'nabial', 'Serwetki': 'inne', 'Chleb żytni': 'pieczywo', 'Jabłka Ligol': 'warzywa', 'Sok jabłkowy': 'napoje', 'Kawa mielona': 'kawa', 'Czekolada mleczna': 'slodycze', 'Cukierki': 'slodycze', 'Cukier biały': 'spizarnia', 'Płyn do naczyń': 'chemia', 'Karma dla kota': 'zwierzeta', 'Piwo jasne': 'alkohol', 'Pizza mrożona': 'mrozonki', 'Papier toaletowy': 'chemia', 'Pierś z kurczaka': 'mieso' };
for (const [n, c] of Object.entries(cats)) eq(catOf(n), c, n);
eq(parseMoney('12,5'), 1250, 'money'); eq(parseMoney('abc'), NaN, 'nan'); eq(parseMoney('-2,30'), -230, 'neg'); eq(parseNum('1,5'), 1.5, 'num');
// weryfikacja: kwoty w groszach, brak błędów zmiennoprzecinkowych
eq(parseMoney('0,29') + parseMoney('0,14'), 43, 'float');
const R = (date, store, name, qty, unit, total, reg = 0) => ({ id: date + name, date, store, declared: 0, lines: [{ name, cat: 'mieso', qty, unit, total, reg }] });
const rs = [R('2026-10-01', 'Lidl', 'Karkówka', 1, 'kg', 2400), R('2026-10-08', 'Lidl', 'Karkówka', 1.2, 'kg', 3000), R('2026-10-15', 'Biedronka', 'karkówka', 1, 'kg', 2200, 2600), R('2026-10-20', 'Biedronka', 'Karkówka', 0.5, 'kg', 1500)];
const p = products(rs); eq(p.length, 1, 'jeden produkt'); eq(p[0].n, 4, 'n=4'); eq(p[0].min, 2200, 'min'); eq(p[0].med, 2450, 'med (2200,2400,2500,3000)');
eq(verdict(2100, 'kg', p[0]).t, 'best', 'best'); eq(verdict(2100 + 600, 'kg', p[0]).t, 'bad', 'bad');
eq(verdict(2200 + 100, 'kg', p[0]).t, 'slight', 'slight (pct 6%)'); eq(verdict(2000, 'l', p[0]).t, 'nodata', 'inna jednostka');
eq(verdict(1000, 'kg', { ...p[0], n: 2 }).t, 'few', 'za mało');
const st = monthStats(rs, '2026-10'); eq(st.spent, 2400 + 3000 + 2200 + 1500, 'wydane'); eq(st.saved, 400, 'oszczędzone'); eq(st.n, 4, 'n paragonów');
const st2 = monthStats([{ id: 'x', date: '2026-11-02', store: 'Lidl', declared: 0, lines: [{ name: 'A', cat: 'inne', qty: 1, unit: 'szt', total: 1000, reg: 0 }, { name: 'Rabat', cat: 'inne', qty: 1, unit: 'szt', total: -300, reg: 0 }] }], '2026-11'); eq(st2.saved, 300, 'rabat liczony jako oszczędność'); eq(st2.spent, 700, 'wydane po rabacie');

// wersja w app.js i sw.js musi być taka sama (inaczej aktualizacja się nie pobierze)
import { readFileSync } from 'node:fs';
const av = /VERSION = '([^']+)'/.exec(readFileSync(new URL('../js/app.js', import.meta.url), 'utf8'))[1];
const sv = /VER = 'zakupy-v([^']+)'/.exec(readFileSync(new URL('../sw.js', import.meta.url), 'utf8'))[1];
if (av !== sv) { bad++; console.log('FAIL wersje: app.js ' + av + ' vs sw.js ' + sv); }
console.log('wersje zgodne', av);

// ---- oferty: przeliczanie i porównywanie ----
import { offerCalc, familyOf, compareGroups } from '../js/offers.js';
const O = (store, name, price, amount, unit, extra = {}) => ({ id: store + name, store, name, price, amount, unit, until: '2026-12-31', mode: 'unit', need: 1, ...extra });
// Kaufland: 2 × 2 l za 13,98 (podane jako komplet) => 3,50 zł/l
let c = offerCalc(O('Kaufland', 'Coca-Cola', 1398, 2, 'l', { mode: 'bundle', need: 2 }));
eq(c.up, 175 * 2 / 2 === 349 ? 349 : 350, 'kaufland cola za litr'); // 1398 / 4 l = 349,5 => 350
// Lidl: 3 butelki 1,5 l za 9,99 => 9,99 / 4,5 = 2,22 zł/l
c = offerCalc(O('Lidl', 'Coca-Cola', 999, 1.5, 'l', { mode: 'bundle', need: 3 }));
eq(c.up, 222, 'lidl cola za litr'); eq(c.pack, 333, 'lidl cola za butelkę'); eq(c.total, 999, 'lidl razem');
// drugi 50% taniej: 2 szt. po 10,00 => 15,00 za 2 = 7,50 za sztukę
c = offerCalc(O('X', 'Jogurt', 1000, 1, 'szt', { mode: 'nth', need: 2, pct: 50 })); eq(c.total, 1500, 'drugi 50% - razem'); eq(c.pack, 750, 'drugi 50% - sztuka');
// gramy i mililitry
eq(offerCalc(O('X', 'Ser', 399, 135, 'g')).up, 2956, '135 g za 3,99 = 29,56 zł/kg'); eq(offerCalc(O('X', 'Olej', 499, 1000, 'ml')).base, 'l', 'ml -> l');
eq(familyOf('Coca-Cola Zero 2 l').id, 'cola', 'rodzina cola'); eq(familyOf('Serek wiejski'), null, 'serek to nie ser żółty'); eq(familyOf('Ser Gouda 100 g').id, 'ser', 'gouda to ser');
eq(familyOf('Woda źródlana 5 l').id, 'woda', 'woda'); eq(familyOf('Wódka czysta'), null, 'wódka to nie woda');
const g = compareGroups([
  O('Kaufland', 'Coca-Cola', 1398, 2, 'l', { mode: 'bundle', need: 2 }),
  O('Lidl', 'Coca-Cola', 999, 1.5, 'l', { mode: 'bundle', need: 3 }),
  O('Biedronka', 'Pepsi', 549, 2, 'l'),
  O('Lidl', 'Mleko 3,2%', 299, 1, 'l'),                // sama w rodzinie => nie ma grupy
  O('Lidl', 'Coca-Cola puszka', 349, 330, 'ml', { until: '2020-01-01' }), // po terminie => pominięta
], '2026-11-02');
eq(g.length, 1, 'jedna grupa porównań'); eq(g[0].rows.map(r => r.o.store).join(), 'Lidl,Biedronka,Kaufland', 'kolejność: Lidl najtaniej'); eq(g[0].rows[0].rank, 1, 'miejsce 1');
console.log('oferty OK');

// ---- Gemini: wybór modelu ----
import { pickFlash, effectiveModel, DEFAULT_MODEL } from '../js/gemini.js';
const ML = [{ name: 'models/gemini-2.5-flash', supportedGenerationMethods: ['generateContent'] }, { name: 'models/gemini-3.8-flash', supportedGenerationMethods: ['generateContent'] },
  { name: 'models/gemini-3.8-flash-lite', supportedGenerationMethods: ['generateContent'] }, { name: 'models/gemini-3.9-flash-image', supportedGenerationMethods: ['generateContent'] },
  { name: 'models/gemini-4.0-flash', supportedGenerationMethods: ['embedContent'] }, { name: 'models/gemini-3.1-pro', supportedGenerationMethods: ['generateContent'] }];
eq(pickFlash(ML), 'gemini-3.8-flash', 'pickFlash: najnowszy zwykły flash z generateContent'); eq(pickFlash([]), null, 'pickFlash: pusta lista');
eq(effectiveModel('gemini-2.5-flash'), DEFAULT_MODEL, 'wycofany model => domyślny'); eq(effectiveModel(''), DEFAULT_MODEL, 'brak modelu => domyślny'); eq(effectiveModel('gemini-3.9-flash'), 'gemini-3.9-flash', 'własny model zostaje');

{
  const { packLabel, unitPrice, countNoun } = await import('../js/offers.js');
  const o = (name, price, amount, unit, mode = 'unit', need = 1, pct = 0) => ({ name, price, amount, unit, mode, need, pct });
  const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('FAIL', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
  eq(packLabel(o('Almusso Papier toaletowy', 2299, 40, 'szt')), '40 rolek', 'papier toaletowy: rolki');
  eq(unitPrice(o('Almusso Papier toaletowy', 2299, 40, 'szt')), { price: 57, label: '1 rolkę', per: 'szt' }, 'cena za rolkę');
  eq(unitPrice(o('K-Classic Papier do pieczenia', 399, 30, 'szt')).label, '1 arkusz', 'papier do pieczenia: arkusz');
  eq(packLabel(o('Ser Gouda', 699, 300, 'g')), '300 g', 'zawartość 300 g');
  eq(unitPrice(o('Ser Gouda', 699, 300, 'g')), { price: 233, label: '100 g', per: '100g' }, 'poniżej 1 kg: za 100 g');
  eq(unitPrice(o('Kawa mielona', 3299, 1, 'kg')), { price: 3299, label: '1 kg', per: 'kg' }, 'od 1 kg: za kg');
  eq(unitPrice(o('Kawa mielona', 3299, 1000, 'g')).label, '1 kg', '1000 g to już kilogram');
  eq(packLabel(o('Coca-Cola', 999, 1.5, 'l', 'bundle', 3)), '3 × 1,5 l = 4,5 l', 'komplet coli');
  eq(unitPrice(o('Coca-Cola', 999, 1.5, 'l', 'bundle', 3)).price, 222, 'cola za litr');
  eq(packLabel(o('Kapsułki do zmywarki', 2999, 32, 'szt')), '32 kapsułki', 'odmiana 32 kapsułki');
  eq(packLabel(o('Papier toaletowy', 1000, 8, 'szt')), '8 rolek', 'odmiana 8 rolek');
  eq(packLabel(o('Papier toaletowy', 500, 4, 'szt')), '4 rolki', 'odmiana 4 rolki');
  eq(countNoun('Żelki Haribo')[3], 'sztukę', 'domyślnie sztuka');
  const { compareGroups: cg } = await import('../js/offers.js');
  const g = cg([{ ...o('Ser Gouda Kaufland', 699, 250, 'g'), until: '2999-01-01', store: 'A', id: 'a' }, { ...o('Ser Gouda Biedronka', 1099, 1, 'kg'), until: '2999-01-01', store: 'B', id: 'b' }], '2026-01-01')[0];
  eq(g.per, '100g', 'porównanie: wspólna jednostka 100 g gdy któraś oferta < 1 kg');
}
{
  const { promoLabel, whereLabel, isMulti, offerCalc: oc, unitPrice: up } = await import('../js/offers.js');
  const zl = c => (c / 100).toFixed(2).replace('.', ',') + ' zł';
  const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('FAIL', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
  const cola = { name: 'Pepsi', price: 1498, amount: 2, unit: 'l', mode: 'bundle', need: 3, pay: 2, pct: 0 };
  eq(promoLabel(cola, zl), '3 za 2', '3 za 2');
  eq(oc(cola).total, 1498, '3 za 2: płacisz za 2 sztuki');
  eq(up(cola).price, 250, '3 za 2: cena za litr = 14,98 / 6 l');
  eq(promoLabel({ ...cola, pay: undefined, price: 999 }, zl), '3 za 9,99 zł', '3 za 9,99 zł');
  eq(promoLabel({ name: 'x', price: 500, amount: 1, unit: 'szt', mode: 'nth', need: 2, pct: 50 }, zl), '2. produkt −50%', 'drugi −50%');
  eq(promoLabel({ name: 'x', price: 500, amount: 1, unit: 'szt', mode: 'nth', need: 2, pct: 100 }, zl), '2. produkt gratis', 'drugi gratis');
  eq(promoLabel({ name: 'x', price: 500, amount: 1, unit: 'szt', mode: 'unit', need: 1 }, zl), '', 'zwykła cena bez oznaczenia');
  eq(isMulti(cola), true, 'isMulti');
  eq(whereLabel({ store: 'Lidl', page: 14 }), 'gazetka Lidl, str. 14', 'gdzie: Lidl');
  eq(whereLabel({ store: 'Kaufland', section: 'Napoje' }), 'dział „Napoje”', 'gdzie: Kaufland');
}
{
  const { compareGroups: cg, isSure, flyerUrl, promoLabel } = await import('../js/offers.js');
  const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('FAIL', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
  const zl = c => (c / 100).toFixed(2).replace('.', ',') + ' zł';
  const bl = { id: 'x', store: 'Lidl', name: 'Coca-Cola', price: 998, amount: 2, unit: 'l', mode: 'bundle', need: 2, until: '2999-01-01', conf: 'check' };
  const ok = { id: 'k', store: 'Kaufland', name: 'Coca-Cola', price: 1398, amount: 2, unit: 'l', mode: 'bundle', need: 2, until: '2999-01-01', conf: 'ok' };
  const ok2 = { ...ok, id: 'l', store: 'Lidl', price: 998, amount: 1 };
  eq(cg([bl, ok], '2026-01-01').length, 0, 'niepewna oferta nie tworzy porównania');
  eq(cg([bl, ok, ok2], '2026-01-01')[0].rows.map(r => r.o.id), ['k', 'l'], 'niepewna poza „najtaniej”: wygrywa potwierdzone 3,50 zł/l');
  eq(isSure({}), true, 'własna oferta bez znacznika jest pewna');
  eq(cg([{ ...ok, conf: 'cena' }, ok2], '2026-01-01').length, 0, 'pewna cena bez przeliczenia nie wchodzi do porównania');
  eq(promoLabel({ ...ok2, promo: 'Dwusztuk' }, zl), 'Dwusztuk', 'napis jak w sklepie');
  eq(flyerUrl({ store: 'Lidl', section: 'gazetka-02-11-pon-kw45', page: 10 }), 'https://www.lidl.pl/l/pl/gazetki/gazetka-02-11-pon-kw45/view/flyer/page/10', 'link do strony gazetki');
  eq(flyerUrl({ store: 'Kaufland', section: 'Napoje' }), '', 'bez linku poza gazetką');
}
{
  const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('FAIL', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
  const cases = { 'Migdały blanszowane': 'slodycze', 'Alesto Migdały blanszowane, filetowane': 'slodycze', 'Whiskas Karma z kurczakiem': 'zwierzeta', 'Chipsy o smaku papryki': 'slodycze', 'Ciastka z jabłkiem': 'slodycze',
    'Pizza z szynką': 'mrozonki', 'Zupa z kurczaka': 'spizarnia', 'Woda micelarna': 'chemia', 'Masło orzechowe': 'spizarnia', 'Krem do rąk z masłem shea': 'chemia', 'Filet z dorsza': 'ryby', 'Filet z piersi kurczaka': 'mieso',
    'Czekolada z orzechami': 'slodycze', 'Rolada ogrodowa': 'slodycze', 'Herbatniki': 'slodycze', 'Herbata czarna': 'kawa', 'Pianka do golenia': 'chemia', 'Garnier Farba do włosów': 'chemia', 'Rodzynki': 'slodycze', 'Gillette Maszynka do golenia': 'chemia' };
  for (const [n, c] of Object.entries(cases)) eq(catOf(n), c, n);
  const { itemFromOffer, byStore } = await import('../js/lista.js');
  const zl = c => (c / 100).toFixed(2).replace('.', ',') + ' zł';
  const cola = itemFromOffer({ id: 'a', store: 'Lidl', name: 'Coca-Cola', price: 998, amount: 1, unit: 'l', mode: 'bundle', need: 2, promo: 'Dwusztuk', page: 10, cond: 'z Lidl Plus', deposit: 100, conf: 'ok' }, zl);
  eq([cola.price, cola.pack, cola.promo, cola.where, cola.unit.price], [998, '2 × 1 l = 2 l', 'Dwusztuk', 'gazetka Lidl, str. 10', 499], 'pozycja z oferty');
  const un = itemFromOffer({ id: 'b', store: 'Kaufland', name: 'X', price: 500, amount: 1, unit: 'szt', mode: 'unit', need: 1, conf: 'check', printed: '2 x 1 L' }, zl);
  eq([un.unit, un.pack, un.unsure], [null, '2 x 1 L', true], 'niepewna pozycja bez przeliczeń');
  const g = byStore([{ ...un, done: true }, cola, { ...cola, id: 'c', qty: 2, done: true }, { id: 'd', name: 'Mleko', store: 'Lidl', price: 0, qty: 1 }]);
  eq(g.map(x => [x.store, x.left, x.sum, x.noPrice]), [['Lidl', 2, 998, 1], ['Kaufland', 0, 0, 0]], 'grupy: sklepy z zakupami najpierw, kupione nie liczą się do sumy');
  eq(g[0].items.map(i => i.done || false), [false, false, true], 'kupione na dole');
  eq(byStore([cola, un], 'Lidl').length, 1, 'filtr sklepu');
}
{
  const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('FAIL', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
  const { matchOffers, basket, pantryLow, planSummary } = await import('../js/plan.js');
  const T = '2026-11-03', O = (id, store, name, price, amount, unit, x = {}) => ({ id, store, name, price, amount, unit, mode: 'unit', need: 1, from: '2026-11-02', until: '2026-11-08', conf: 'ok', ...x });
  const of = [O('a', 'Lidl', 'Masło extra', 699, 200, 'g'), O('b', 'Kaufland', 'Masło polskie', 599, 200, 'g'), O('c', 'Lidl', 'Masło orzechowe', 399, 350, 'g'),
    O('d', 'Lidl', 'Mleko 3,2%', 349, 1, 'l', { conf: 'check' }), O('e', 'Lidl', 'Masło stare', 100, 200, 'g', { until: '2026-11-01' }), O('f', 'Lidl', 'Masło przyszłe', 100, 200, 'g', { from: '2026-11-09' }),
    O('g', 'Kaufland', 'Coca-Cola', 1398, 2, 'l', { mode: 'bundle', need: 2 }), O('h', 'Lidl', 'Pepsi', 500, 2, 'l')];
  eq(matchOffers('masło', of, T).map(r => r.o.id), ['b', 'a'], 'koszyk: najtaniej, bez orzechowego, starych, przyszłych');
  eq(matchOffers('mleko', of, T), [], 'koszyk: niepewna oferta nie liczy się');
  eq(matchOffers('coca-cola', of, T).map(r => r.o.id), ['g'], 'wpisana marka nie miesza się z inną');
  const b = basket(['masło', 'coca-cola', 'szafran'], of, T);
  eq([b.total, b.stores.length, b.missing, b.stores[0].store, b.found], [1997, 1, ['szafran'], 'Kaufland', 2], 'koszyk: suma, sklepy, brakujące');
  eq(pantryLow([{ qty: 1, min: 1 }, { qty: 2, min: 1 }, { qty: 0, min: 1 }]).length, 2, 'spiżarnia: na minimum to już mało');
  const p = planSummary({ limit: 300000, spent: 100000, plan: [{ amount: 50000 }, { amount: 90000, done: true }], listSum: 20000, day: 21, days: 30 });
  eq([p.planned, p.free, p.left, p.perDay], [50000, 130000, 10, 13000], 'plan: zrobione się nie liczy, dzień dzisiejszy tak');
  eq(planSummary({ limit: 1000, spent: 5000, plan: [], day: 1, days: 30 }).perDay, 0, 'plan: bez ujemnej kwoty na dzień');
}
{
  const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { bad++; console.log('FAIL', m, JSON.stringify(a), '!=', JSON.stringify(b)); } };
  const { catOfOffer } = await import('../js/cats.js');
  eq(catOfOffer('Ambi Pur Elegance', 'Drogeria i Chemia gospodarcza'), 'chemia', 'dział wygrywa z nieznaną nazwą');
  eq(catOfOffer('Whiskas dla kota', 'Drogeria i Chemia gospodarcza'), 'zwierzeta', 'dozwolona kategoria w dziale');
  eq(catOfOffer('Pilsner Urquell', 'Napoje'), 'alkohol', 'piwo w dziale Napoje');
  eq(catOfOffer('Szynka', 'Mięso, Drób, Wędliny'), 'wedliny', 'dział łączony: decyduje nazwa');
  eq(catOfOffer('Tymbark sok', 'Hity tygodnia'), 'napoje', 'dział promocyjny nic nie mówi');
}
console.log(bad ? bad + ' błędów' : 'unit OK');
process.exit(bad ? 1 : 0);
