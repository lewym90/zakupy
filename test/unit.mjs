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

console.log(bad ? bad + ' błędów' : 'unit OK');
process.exit(bad ? 1 : 0);
