// Narzędzia: formatowanie, parsowanie, daty. Kwoty trzymamy w groszach (liczby całkowite).
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const zl = g => (g / 100).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' zł';
export const zlShort = g => Math.round(g / 100).toLocaleString('pl-PL') + ' zł';

export function parseMoney(s) {
  const t = String(s ?? '').replace(/\s|zł/gi, '').replace(',', '.');
  if (t === '' || !/^-?\d*\.?\d+$/.test(t)) return NaN;
  return Math.round(parseFloat(t) * 100);
}
export function parseNum(s) {
  const t = String(s ?? '').replace(/\s/g, '').replace(',', '.');
  const v = parseFloat(t);
  return isFinite(v) ? v : NaN;
}
export const centsToInput = g => (g / 100).toFixed(2).replace('.', ',');

export const norm = s => String(s || '').toLowerCase().replace(/ł/g, 'l').normalize('NFD')
  .replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9% ]+/g, ' ').replace(/\s+/g, ' ').trim();

export const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

const p2 = n => String(n).padStart(2, '0');
export const todayISO = (d = new Date()) => d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate());
export const ymOf = iso => iso.slice(0, 7);
const MN = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec', 'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień'];
export const monthName = ym => MN[+ym.slice(5, 7) - 1] + ' ' + ym.slice(0, 4);
export const monthShort = ym => MN[+ym.slice(5, 7) - 1].slice(0, 3);
export function addMonth(ym, k) {
  const y = +ym.slice(0, 4), m = +ym.slice(5, 7) - 1 + k;
  const d = new Date(y, m, 1);
  return d.getFullYear() + '-' + p2(d.getMonth() + 1);
}
export const daysInMonth = ym => new Date(+ym.slice(0, 4), +ym.slice(5, 7), 0).getDate();
export function fmtDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}
export function median(a) {
  if (!a.length) return 0;
  const s = [...a].sort((x, y) => x - y), h = s.length >> 1;
  return s.length % 2 ? s[h] : Math.round((s[h - 1] + s[h]) / 2);
}
