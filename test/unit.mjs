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
console.log(bad ? bad + ' błędów' : 'unit OK');
process.exit(bad ? 1 : 0);
