import { all, put, del, clear, kvGet, kvSet } from './db.js';
import { CATS, catOf, catById, STORES } from './cats.js';
import { esc, zl, zlShort, parseMoney, parseNum, centsToInput, norm, uid, todayISO, ymOf, monthName, monthShort, addMonth, daysInMonth, fmtDate } from './util.js';
import { products, matchProduct, verdict, monthStats, monthTotals, receiptTotal, lineSum } from './calc.js';
import { readReceipt, DEFAULT_MODEL, effectiveModel, listModels, pickFlash } from './gemini.js';
import { offerCalc, compareGroups, familyOf, offerLabel, UNITS, packLabel, unitPrice, promoLabel, whereLabel, isMulti, isSure, isHidden, flyerUrl } from './offers.js';

const VERSION = '0.4.1';
const NOW_YM = () => todayISO().slice(0, 7);
const S = { receipts: [], offers: [], kv: {}, tab: 'start', omode: 'lista', ym: NOW_YM(), q: '', cat: '', ocat: '', lastStore: 'Biedronka', srv: null, oq: '', ounsure: false };
const view = document.getElementById('view');

const ICON = {
  start: '<path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  paragony: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9.5 8h5M9.5 12h5"/>',
  cennik: '<path d="M3 12 12 3h8v8l-9 9z"/><circle cx="15.5" cy="8.5" r="1.3"/>',
  okazje: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  ustawienia: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
  budzet: '<path d="M3 7.5h17a1 1 0 0 1 1 1V19a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M3 7.5 5.5 4h11"/><circle cx="16.5" cy="13.5" r="1.2"/>',
};
const TABS = [['start', 'Start'], ['paragony', 'Paragony'], ['cennik', 'Cennik'], ['okazje', 'Okazje'], ['budzet', 'Budżet'], ['ustawienia', 'Ustawienia']];

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('on');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('on'), Math.min(9000, 2600 + String(msg).length * 45));
}

/* ---------- start ---------- */
async function init() {
  const [receipts, offers] = await Promise.all([all('receipts'), all('offers')]);
  S.receipts = receipts; S.offers = offers;
  for (const k of ['limit', 'catLimits', 'geminiKey', 'geminiModel', 'srvUrl']) S.kv[k] = await kvGet(k);
  S.srv = (await kvGet('srvOffers')) || null;
  document.getElementById('tabbar').innerHTML = TABS.map(([id, n]) =>
    `<button class="tab" data-tab="${id}"><svg viewBox="0 0 24 24" aria-hidden="true">${ICON[id]}</svg>${n}</button>`).join('');
  document.getElementById('tabbar').addEventListener('click', e => {
    const b = e.target.closest('[data-tab]'); if (!b) return;
    if (S.reload) { location.reload(); return; }
    S.tab = b.dataset.tab; window.scrollTo(0, 0); render();
  });
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
  startUpdates();
  render();
  fetchSrv(false);
}

function render() {
  S._p = null;
  document.querySelectorAll('.tab').forEach(b => b.setAttribute('aria-current', b.dataset.tab === S.tab ? 'page' : 'false'));
  view.dataset.screen = S.tab;
  view.innerHTML = SCREENS[S.tab]();
  const names = [...new Map(S.receipts.flatMap(r => r.lines).filter(l => l.name).map(l => [norm(l.name), l.name])).values()];
  document.getElementById('prod').innerHTML = names.sort().map(n => `<option value="${esc(n)}">`).join('');
}

/* ---------- ekrany ---------- */
const SCREENS = { start, paragony, cennik, okazje, budzet, ustawienia };

function receiptEmoji(r) {
  const sums = {};
  for (const l of r.lines) if (l.total > 0) sums[l.cat] = (sums[l.cat] || 0) + l.total;
  const top = Object.entries(sums).sort((a, b) => b[1] - a[1])[0];
  return top ? catById(top[0]).e : '🧾';
}
function receiptItem(r) {
  const mark = r.check === 'ok' ? '<span class="down" title="Suma się zgadza"> ✓</span>' : r.check === 'diff' ? '<span class="up" title="Suma się nie zgadza"> ⚠</span>' : '';
  return `<button class="item" data-act="receipt" data-id="${r.id}"><span class="em">${receiptEmoji(r)}</span>
    <span class="mid"><span class="t">${esc(r.store)}${mark}</span><span class="s">${fmtDate(r.date)} · ${r.lines.length} poz.</span></span>
    <span class="r num">${zl(receiptTotal(r))}</span></button>`;
}

function start() {
  const st = monthStats(S.receipts, S.ym);
  const limit = S.kv.limit || 0;
  const cur = S.ym === NOW_YM();
  const over = limit && st.spent > limit;
  const pct = limit ? Math.min(100, (st.spent / limit) * 100) : 0;
  const rows = Object.entries(st.cats).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([c, v]) => `<div class="ln-line"><span class="l">${c === '__rest' ? '🧾 Nieprzypisane' : catById(c).e + ' ' + catById(c).n}</span><span class="d"></span><span class="v">${zl(v)}</span></div>`).join('');
  const day = new Date().getDate();
  const proj = cur && day >= 5 && st.spent > 0 ? Math.round((st.spent / day) * daysInMonth(S.ym)) : 0;
  const good = allOffers().filter(o => o.until >= todayISO() && isSure(o)).filter(o => ['best', 'good'].includes(offerVerdict(o).t)).length;
  return `<div class="head"><div><h1>Zakupy</h1><p class="sub">${S.receipts.length ? 'Wasz miesiąc w skrócie' : 'Zacznij od pierwszego paragonu'}</p></div>
    <div class="mnav"><button data-act="mprev" aria-label="Poprzedni miesiąc">‹</button><b>${monthName(S.ym)}</b><button data-act="mnext" aria-label="Następny miesiąc">›</button></div></div>
    <div class="tapewrap"><div class="tape ${st.saved > 0 ? "withst" : ""}">
      <div class="shop"><span>Wydane</span><button data-act="new" aria-label="Dodaj paragon">+</button></div>
      <div class="big">${zl(st.spent)}</div>
      ${limit ? `<div class="of">z limitu ${zlShort(limit)}${over ? ' · przekroczony o ' + zl(st.spent - limit) : ' · zostało ' + zl(limit - st.spent)}</div><div class="bar ${over ? 'over' : ''}"><i style="width:${pct}%"></i></div>`
        : `<div class="of">Limit miesięczny ustawisz w Budżecie</div>`}
      ${rows ? `<div class="dots"></div>${rows}` : ''}
      ${proj ? `<div class="proj">Przy tym tempie: ok. ${zlShort(proj)} na koniec miesiąca</div>` : ''}
    </div>${st.saved > 0 ? `<div class="sticker"><b>${zl(st.saved)}</b><span>Oszczędzone na promocjach</span></div>` : ''}</div>
    ${S.receipts.length === 0 ? `<div class="card empty"><div class="big">🧾</div><b>Tu zaczyna się Wasz cennik</b><p>Dodaj paragon ręcznie albo ze zdjęcia. Z kilku paragonów zobaczysz, ile naprawdę płacicie i które promocje się opłacają.</p><button class="btn" data-act="new">Dodaj pierwszy paragon</button></div>` : ''}
    ${good ? `<button class="item" data-act="goto" data-tab="okazje" style="margin-bottom:8px"><span class="em">⚡</span><span class="mid"><span class="t">${good} ${good === 1 ? 'okazja jest' : 'okazji jest'} lepsza niż zwykle</span><span class="s">Na podstawie Waszych paragonów</span></span><span class="r">›</span></button>` : ''}
    ${st.rs.length ? `<h2>Ostatnie paragony</h2><div class="list">${[...st.rs].sort((a, b) => (a.date < b.date ? 1 : -1)).slice(0, 3).map(receiptItem).join('')}</div>` : ''}`;
}

function paragony() {
  const q = norm(S.q);
  let rs = [...S.receipts].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  if (q) rs = rs.filter(r => norm(r.store).includes(q) || r.lines.some(l => norm(l.name).includes(q)));
  const groups = [];
  for (const r of rs) {
    const ym = ymOf(r.date);
    if (!groups.length || groups[groups.length - 1].ym !== ym) groups.push({ ym, items: [] });
    groups[groups.length - 1].items.push(receiptItem(r));
  }
  const html = groups.map(g => `<h2>${monthName(g.ym)} <span class="sub num" style="font-weight:600">· ${zl(monthStats(S.receipts, g.ym).spent)}</span></h2><div class="list">${g.items.join('')}</div>`).join('');
  return `<div class="head"><div><h1>Paragony</h1><p class="sub">${S.receipts.length} zapisanych</p></div><button class="btn sm" data-act="new">Dodaj</button></div>
    <label class="field"><span>Szukaj sklepu lub produktu</span><input type="search" data-q="1" value="${esc(S.q)}" placeholder="np. karkówka"></label>
    ${rs.length ? html : `<div class="empty"><div class="big">🧾</div><b>${q ? 'Nic nie znaleziono' : 'Brak paragonów'}</b><p>${q ? 'Spróbuj innej nazwy.' : 'Dodaj pierwszy paragon, a zbudujemy z niego Wasz cennik.'}</p>${q ? '' : '<button class="btn" data-act="new">Dodaj paragon</button>'}</div>`}`;
}

function cennik() {
  const prods = products(S.receipts);
  const q = norm(S.q);
  const usedCats = [...new Set(prods.map(p => p.cat))];
  let list = prods.filter(p => (!S.cat || p.cat === S.cat) && (!q || p.key.includes(q)));
  list.sort((a, b) => b.n - a.n || (a.name < b.name ? -1 : 1));
  const chips = `<div class="chips"><button class="chip" aria-pressed="${!S.cat}" data-act="cat" data-c="">Wszystko</button>${CATS.filter(c => usedCats.includes(c.id)).map(c => `<button class="chip" aria-pressed="${S.cat === c.id}" data-act="cat" data-c="${c.id}">${c.e} ${c.n}</button>`).join('')}</div>`;
  const items = list.map(p => {
    const dev = p.n >= 3 && p.med ? (p.last - p.med) / p.med : 0;
    const tr = p.n >= 3 ? (dev > 0.05 ? `<small class="up">▲ ${Math.round(dev * 100)}% ponad zwykłą</small>` : dev < -0.05 ? `<small class="down">▼ ${Math.round(-dev * 100)}% poniżej zwykłej</small>` : '<small>cena zwykła</small>') : `<small>${p.n} ${p.n === 1 ? 'zakup' : 'zakupy'}</small>`;
    return `<button class="item" data-act="product" data-k="${esc(p.key)}"><span class="em">${catById(p.cat).e}</span><span class="mid"><span class="t">${esc(p.name)}</span><span class="s">${esc(p.lastStore)} · ${fmtDate(p.lastDate)}</span></span><span class="r num">${zl(p.last)}/${p.unit}${tr}</span></button>`;
  }).join('');
  return `<div class="head"><div><h1>Cennik</h1><p class="sub">Ceny z Waszych paragonów</p></div></div>
    <label class="field"><span>Szukaj produktu</span><input type="search" data-q="1" value="${esc(S.q)}" placeholder="np. mleko"></label>${prods.length ? chips : ''}
    ${list.length ? `<div class="list">${items}</div>` : `<div class="empty"><div class="big">🏷️</div><b>${prods.length ? 'Nic nie znaleziono' : 'Cennik jest pusty'}</b><p>${prods.length ? 'Zmień filtr lub wyszukiwanie.' : 'Pojawi się sam, gdy dodasz paragony. Im więcej zakupów, tym dokładniejsza ocena promocji.'}</p></div>`}`;
}

const RANK = { best: 0, good: 1, slight: 2, norm: 3, few: 4, nodata: 5, bad: 6 };
const fmtN = n => String(Math.round(n * 1000) / 1000).replace('.', ',');
const offerUP = o => offerCalc(o).up;
const prods = () => S._p || (S._p = products(S.receipts));
function offerVerdict(o) { const c = offerCalc(o); return verdict(c.up, c.base, matchProduct(prods(), o.name)); }
// Oferty własne + oferty z serwera (tylko do odczytu, id z prefiksem "s:")
let _ao = { m: null, s: null, v: [] };
function allOffers() {
  const sv = S.srv && S.srv.data && Array.isArray(S.srv.data.offers) ? S.srv.data.offers : null;
  if (_ao.m !== S.offers || _ao.s !== sv) _ao = { m: S.offers, s: sv, v: [...S.offers, ...(sv || []).map(o => ({ ...o, id: 's:' + o.id, cat: catOf(o.name), srv: true }))] };
  return _ao.v;
}
const normQ = t => String(t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
async function fetchSrv(manual) {
  const url = (S.kv.srvUrl || '').trim();
  if (!url) { if (manual) toast('Najpierw wklej adres ofert'); return false; }
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    if (!j || j.v !== 1 || !Array.isArray(j.offers)) throw new Error('to nie jest plik ofert');
    S.srv = { at: Date.now(), data: j }; await kvSet('srvOffers', S.srv);
    if (!document.querySelector('.sheet')) render();
    if (manual) toast('Pobrano ' + j.offers.length + ' ofert');
    return true;
  } catch (e) { if (manual) toast('Nie udało się pobrać ofert (' + e.message + ')'); return false; }
}
const UNIT_LBL = { l: 'l', kg: 'kg', szt: 'szt' };

const promoPill = o => { const t = promoLabel(o, zl); return t ? `<span class="pill promo">🏷️ ${esc(t)}</span>` : ''; };
const depositLine = o => (o.deposit ? `<span class="hint">+ kaucja ${zl(o.deposit)} (poza ceną)</span>` : '');
const whereLine = o => { const w = whereLabel(o); return w ? `<span class="hint">Szukaj: ${esc(w)}</span>` : ''; };
function offerCard(o, v) {
  const c = offerCalc(o), multi = isMulti(o), hid = isHidden(o);
  if (!isSure(o)) return `<button class="offer${hid ? ' unsure' : ''}" data-act="offer" data-id="${o.id}"><span class="em">${catById(o.cat).e}</span>
    <span class="mid"><span class="t">${esc(o.name)}</span><span class="hint">${esc(o.store)} · do ${fmtDate(o.until)}${o.cond ? ' · ' + esc(o.cond) : ''}</span>
      ${promoPill(o)}${o.printed ? `<span class="hint">${hid ? 'Na gazetce' : 'W sklepie'}: ${esc(o.printed)}</span>` : ''}${whereLine(o)}<span class="pill nodata">${hid ? 'odczyt niepewny' : 'bez ceny za jednostkę'}</span></span>
    <span class="p num"><b>${zl(c.total)}</b><small>${hid ? 'cena z odczytu' : 'za opakowanie'}</small>${o.old ? `<s>${zl(o.old)}</s>` : ''}</span></button>`;
  const u = unitPrice(o);
  return `<button class="offer" data-act="offer" data-id="${o.id}"><span class="em">${catById(o.cat).e}</span>
    <span class="mid"><span class="t">${esc(o.name)}</span><span class="hint">${esc(o.store)} · do ${fmtDate(o.until)}${o.cond ? ' · ' + esc(o.cond) : ''}</span>
      ${promoPill(o)}
      <span class="hint">${multi ? 'Komplet' : 'Opakowanie'}: <b>${esc(packLabel(o))}</b></span>
      <span class="uprice">Za ${esc(u.label)}: <b>${zl(u.price)}</b></span>${depositLine(o)}${whereLine(o)}${v ? `<span class="pill ${v.t}">${esc(v.txt)}</span>` : ''}</span>
    <span class="p num"><b>${zl(c.total)}</b><small>${multi ? 'za komplet' : 'za opakowanie'}</small>${o.old ? `<s>${zl(o.old)}</s>` : ''}</span></button>`;
}

function okazje() {
  const today = todayISO();
  const every = allOffers(), all = every.filter(o => o.until >= today), old = S.offers.filter(o => o.until < today).length;
  const nUnsure = all.filter(isHidden).length, act = S.ounsure ? all : all.filter(o => !isHidden(o));
  const nOf = `${nUnsure} ${nUnsure === 1 ? 'ofertę' : nUnsure % 10 >= 2 && nUnsure % 10 <= 4 && !(nUnsure % 100 >= 12 && nUnsure % 100 <= 14) ? 'oferty' : 'ofert'}`;
  const unsureBar = nUnsure ? `<p class="unsure-bar">${S.ounsure ? `Pokazuję też ${nOf} z niepewnym odczytem: tylko cena, bez przeliczeń.` : `Ukryto ${nOf} z niepewnym odczytem.`} <button class="lnk" data-act="ounsure">${S.ounsure ? 'Ukryj' : 'Pokaż'}</button></p>` : '';
  const seg = `<div class="seg" role="tablist"><button aria-pressed="${S.omode === 'lista'}" data-act="omode" data-m="lista">Lista</button><button aria-pressed="${S.omode === 'porownanie'}" data-act="omode" data-m="porownanie">Porównanie</button></div>`;
  let body;
  if (S.omode === 'porownanie') {
    const groups = compareGroups(every, today);
    body = groups.length ? '<div class="cmpgrid">' + groups.map(g => {
      const b = g.best;
      const rows = g.rows.map(r => { const u = unitPrice(r.o, g.per), multi = isMulti(r.o);
        return `<button class="cmp-row ${r.rank === 1 ? 'best' : ''}" data-act="offer" data-id="${r.o.id}">
        <span class="rk">${r.rank}</span>
        <span class="mid"><span class="t">${esc(r.o.store)}</span><span class="hint">${esc(r.o.name)}</span>${promoPill(r.o)}
          <span class="hint">${multi ? 'Komplet' : 'Opakowanie'}: <b>${esc(packLabel(r.o))}</b></span>
          <span class="uprice">Za ${esc(u.label)}: <b>${zl(u.price)}</b>${r.rank > 1 ? ` <em>+${Math.round(r.over * 100)}%</em>` : ' <em class="bestt">najtaniej</em>'}</span>${depositLine(r.o)}${whereLine(r.o)}</span>
        <span class="p num"><b>${zl(r.c.total)}</b><small>${multi ? 'za komplet' : 'za opakowanie'}</small></span></button>`; }).join('');
      return `<div class="card cmp"><div class="cmp-h"><b>${esc(g.fam.n)}</b><span class="hint">najtaniej: ${esc(b.o.store)}, ${zl(unitPrice(b.o, g.per).price)} za ${esc(unitPrice(b.o, g.per).label)}</span></div>${rows}</div>`;
    }).join('') + '</div><p class="hint" style="text-align:center">Porównuję ten sam rodzaj produktu po cenie za litr, kilogram lub sztukę. Marki mogą się różnić, więc sprawdź, czy to naprawdę to, czego szukasz.' + (nUnsure ? ' Oferty z niepewnym odczytem nie biorą udziału w porównaniu.' : '') + '</p>'
      : `<div class="empty"><div class="big">⚖️</div><b>Na razie nie ma czego porównać</b><p>Porównanie pojawi się, gdy dodasz dwie aktywne okazje na podobny produkt (np. cola w Lidlu i w Kauflandzie).</p><button class="btn" data-act="newoffer">Dodaj okazję</button></div>`;
  } else {
    const used = [...new Set(act.map(o => o.cat))];
    const q = normQ(S.oq).trim();
    const list = act.filter(o => (!S.ocat || (S.ocat === '__multi' ? isMulti(o) : o.cat === S.ocat)) && (!q || normQ(o.store + ' ' + o.name).includes(q))).map(o => ({ o, v: isSure(o) ? offerVerdict(o) : null }));
    list.sort((a, b) => (!a.v - !b.v) || (a.v ? RANK[a.v.t] - RANK[b.v.t] : 0) || (isMulti(b.o) - isMulti(a.o)) || a.o.name.localeCompare(b.o.name, 'pl'));
    const nMulti = act.filter(isMulti).length;
    const chips = `<div class="chips"><button class="chip" aria-pressed="${!S.ocat}" data-act="ocat" data-c="">Wszystko</button>${nMulti ? `<button class="chip" aria-pressed="${S.ocat === '__multi'}" data-act="ocat" data-c="__multi">🏷️ Komplety i 2+1 (${nMulti})</button>` : ''}${CATS.filter(c => used.includes(c.id)).map(c => `<button class="chip" aria-pressed="${S.ocat === c.id}" data-act="ocat" data-c="${c.id}">${c.e} ${c.n}</button>`).join('')}</div>`;
    body = (act.length ? `<input class="search" id="oq" type="search" placeholder="Szukaj okazji, np. masło" value="${esc(S.oq)}" autocomplete="off">` + chips : '') + unsureBar + (list.length ? `<div class="list grid">${list.map(({ o, v }) => offerCard(o, v)).join('')}</div>` : `<div class="empty"><div class="big">⚡</div><b>${act.length ? 'Nic nie pasuje' : nUnsure ? 'Brak potwierdzonych ofert' : 'Brak aktywnych okazji'}</b><p>${act.length ? 'Zmień wyszukiwanie lub kategorię.' : 'Dodaj promocję ręcznie albo podłącz serwer z ofertami w Ustawieniach.'}</p>${act.length ? '' : '<button class="btn" data-act="newoffer">Dodaj okazję</button>'}</div>`);
  }
  return `<div class="head"><div><h1>Okazje</h1><p class="sub">${S.omode === 'porownanie' ? 'Która oferta wychodzi taniej' : 'Oceniane względem Waszych cen'}</p></div><button class="btn sm" data-act="newoffer">Dodaj</button></div>
    ${seg}${body}
    ${old ? `<p style="text-align:center"><button class="lnk" data-act="purge">Usuń zakończone okazje (${old})</button></p>` : ''}`;
}

function budzet() {
  const ym = NOW_YM(), st = monthStats(S.receipts, ym), limit = S.kv.limit || 0, cl = S.kv.catLimits || {};
  const yms = [5, 4, 3, 2, 1, 0].map(k => addMonth(ym, -k));
  const tots = monthTotals(S.receipts, yms);
  const mx = Math.max(limit, ...tots.map(t => t.spent), 1);
  const H = 76;
  const hist = `<div class="hist" style="position:relative">${tots.map(t => `<div class="col ${t.ym === ym ? 'cur' : ''}"><i style="height:${Math.max(3, (t.spent / mx) * H)}px"></i><span>${monthShort(t.ym)}</span></div>`).join('')}${limit ? `<div class="lim" style="bottom:${23 + (limit / mx) * H}px"></div>` : ''}</div>`;
  const rows = CATS.map(c => {
    const v = st.cats[c.id] || 0, l = cl[c.id] || 0;
    if (!v && !l) return '';
    const p = l ? Math.min(100, (v / l) * 100) : 0;
    return `<button class="catrow" data-act="catlimit" data-c="${c.id}"><span class="em">${c.e}</span><span class="mid"><span>${c.n}</span>${l ? `<div class="bar ${v > l ? 'over' : ''}"><i style="width:${p}%"></i></div>` : ''}</span><span class="v">${zl(v)}${l ? `<br><small class="${v > l ? 'up' : ''}" style="font-weight:600;color:${v > l ? '' : 'var(--mut)'}">z ${zlShort(l)}</small>` : ''}</span></button>`;
  }).join('');
  return `<div class="head"><div><h1>Budżet</h1><p class="sub">${monthName(ym)}</p></div></div>
    <div class="card"><label class="field" style="margin:0"><span>Limit miesięczny na zakupy (zł)</span><div class="row" style="flex-wrap:nowrap"><input id="limit" inputmode="decimal" value="${limit ? centsToInput(limit).replace(',00', '') : ''}" placeholder="np. 3000"><button class="btn" data-act="savelimit">Zapisz</button></div></label></div>
    <h2>Ostatnie 6 miesięcy</h2><div class="card">${hist}<p class="hint" style="margin:6px 0 0">${limit ? 'Przerywana linia to Wasz limit.' : 'Po ustawieniu limitu zobaczysz tu linię limitu.'}</p></div>
    <h2>Ten miesiąc wg kategorii</h2><div class="card">${rows || '<p class="hint" style="margin:0">Po dodaniu paragonów zobaczysz tu podział wydatków. Dotknij kategorii, żeby ustawić jej limit.</p>'}</div>
    `;
}

/* ---------- ustawienia ---------- */
function srvStores() {
  const st = S.srv && S.srv.data && S.srv.data.stores; if (!st) return '';
  return Object.entries(st).map(([n, x]) => `<div class="kv"><span>${esc(n)}</span><b class="${x.ok ? 'down' : 'up'}">${x.ok ? (x.count != null ? x.count + ' ofert' : 'ok') : 'błąd'}</b></div>${!x.ok && x.msg ? `<p class="hint" style="margin:0 0 6px">${esc(x.msg)}</p>` : ''}`).join('');
}
function ustawienia() {
  const key = S.kv.geminiKey || '';
  const n = S.receipts.length, nl = S.receipts.reduce((x, r) => x + r.lines.length, 0);
  return `<div class="head"><div><h1>Ustawienia</h1><p class="sub">Zakupy ${VERSION}</p></div></div>
    <h2>Aplikacja</h2><div class="card">
      <div class="kv"><span>Zainstalowana wersja</span><b>${VERSION}</b></div>
      <div class="kv"><span>Najnowsza na serwerze</span><b id="upd-latest">—</b></div>
      <p class="hint" id="upd-status" style="margin:8px 0 12px">Przy każdym uruchomieniu aplikacja sama sprawdza, czy jest nowa wersja.</p>
      <button class="btn" style="width:100%;margin-bottom:8px" data-act="upd">Sprawdź i pobierz aktualizację</button>
      <button class="lnk" data-act="forceupd">Coś nie działa? Wymuś pełne odświeżenie</button>
      <p class="hint" style="margin:6px 0 0">Pełne odświeżenie czyści tylko pliki aplikacji. Paragonów i ustawień nie rusza.</p></div>
    <h2>Odczyt zdjęć paragonów (Gemini)</h2><div class="card">
      <div class="kv"><span>Klucz</span><b class="${key ? 'down' : 'up'}">${key ? 'Zapisany ✓' : 'Brak'}</b></div>
      <p class="hint" style="margin:8px 0 10px">Darmowy klucz zrobisz na aistudio.google.com (Get API key). Zostaje tylko w tym telefonie i nie trafia do kopii zapasowej. Wynik odczytu zawsze trzeba sprawdzić, a aplikacja porównuje sumę pozycji z sumą na paragonie.</p>
      <label class="field"><span>Klucz API</span><div class="row" style="flex-wrap:nowrap"><input id="gkey" type="password" autocomplete="off" value="${esc(key)}" placeholder="wklej klucz"><button class="btn ghost sm" data-act="showkey" aria-label="Pokaż lub ukryj klucz">Pokaż</button></div></label>
      <label class="field"><span>Model</span><input id="gmodel" value="${esc(effectiveModel(S.kv.geminiModel))}"></label>
      <p class="hint" id="key-status" style="margin:0 0 10px"></p>
      <div class="row"><button class="btn sm" data-act="savegem">Zapisz</button><button class="btn ghost sm" data-act="testkey">Sprawdź klucz</button>${key ? '<button class="btn ghost sm" data-act="delkey">Usuń klucz</button>' : ''}</div></div>
    <h2>Oferty z serwera</h2><div class="card">
      <div class="kv"><span>Pobrane oferty</span><b>${S.srv && S.srv.data ? S.srv.data.offers.length : '—'}</b></div>
      <div class="kv"><span>Zebrane na serwerze</span><b>${S.srv && S.srv.data && S.srv.data.updated ? esc(new Date(S.srv.data.updated).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' })) : '—'}</b></div>
      ${srvStores()}
      <p class="hint" style="margin:8px 0 10px">Serwer zbiera oferty Kauflanda i Lidla dwa razy dziennie. Wklej adres, który pokazał instalator.</p>
      <label class="field"><span>Adres ofert</span><input id="surl" inputmode="url" autocomplete="off" value="${esc(S.kv.srvUrl || '')}" placeholder="https://…/zakupy-oferty/…/oferty.json"></label>
      <div class="row"><button class="btn sm" data-act="savesrv">Zapisz i pobierz</button><button class="btn ghost sm" data-act="getsrv">Pobierz teraz</button></div></div>
    <h2>Dane i kopie</h2><div class="card">
      <div class="kv"><span>Paragony</span><b>${n}</b></div>
      <div class="kv"><span>Pozycje</span><b>${nl}</b></div>
      <div class="kv"><span>Okazje</span><b>${S.offers.length}</b></div>
      <p class="hint" style="margin:8px 0 12px">Wszystkie dane są tylko w tym telefonie. Zapisuj kopię od czasu do czasu, szczególnie przed zmianą telefonu.</p>
      <div class="row"><button class="btn ghost sm" data-act="export">Zapisz kopię</button><button class="btn ghost sm" data-act="import">Wczytaj kopię</button></div>
      <input type="file" id="impfile" accept="application/json" hidden>
      <p style="margin:16px 0 0"><button class="lnk dng" data-act="wipe">Usuń wszystkie dane z tego telefonu</button></p></div>
    <h2>O aplikacji</h2><div class="card"><p class="hint" style="margin:0">Zakupy to prywatna aplikacja do własnego użytku. Ceny i oceny okazji liczą się wyłącznie z Waszych paragonów, a wszystkie obliczenia robi kod, nie AI. AI (Gemini) służy tylko do odczytania zdjęcia paragonu i zawsze podlega Waszej kontroli.</p></div>`;
}

/* ---------- aktualizacje ---------- */
async function latestVersion() {
  try {
    const r = await fetch('sw.js?c=' + Date.now(), { cache: 'no-store' });
    const m = /VER\s*=\s*'zakupy-v([^']+)'/.exec(await r.text());
    return m ? m[1] : null;
  } catch (_) { return null; }
}
function setUpd(txt, latest) {
  const s = document.getElementById('upd-status'), l = document.getElementById('upd-latest');
  if (s) s.textContent = txt;
  if (l && latest !== undefined) l.textContent = latest || 'brak połączenia';
}
function startUpdates() {
  if (!('serviceWorker' in navigator)) return;
  const had = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!had || S.reloading) return;
    S.reloading = true;
    if (document.querySelector('.sheet')) { S.reload = true; toast('Nowa wersja gotowa. Zamknij okno i dotknij zakładki.'); S.reloading = false; }
    else location.reload();
  });
  navigator.serviceWorker.register('sw.js').then(reg => reg.update()).catch(() => {});
}
async function manualUpdate() {
  setUpd('Sprawdzam…');
  const latest = await latestVersion();
  if (!latest) { setUpd('Nie mogę sprawdzić. Brak internetu?', null); return; }
  const reg = await navigator.serviceWorker.getRegistration();
  if (latest === VERSION) { if (reg) await reg.update().catch(() => {}); setUpd('Masz najnowszą wersję.', latest); return; }
  setUpd('Jest nowa wersja ' + latest + '. Pobieram i uruchamiam ponownie…', latest);
  if (reg) await reg.update().catch(() => {});
  setTimeout(() => { if (!S.reloading) forceRefresh(); }, 6000);
}
async function forceRefresh() {
  S.reloading = true;
  try {
    for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
    for (const k of await caches.keys()) await caches.delete(k);
  } catch (_) {}
  location.reload();
}
async function testKey() {
  const k = view.querySelector('#gkey').value.trim(), st = view.querySelector('#key-status');
  if (!k) { st.textContent = 'Najpierw wklej klucz.'; return; }
  st.textContent = 'Sprawdzam…';
  try {
    const models = await listModels(k);
    const have = new Set(models.map(m => String(m.name).replace(/^models\//, '')));
    const cur = effectiveModel(view.querySelector('#gmodel').value.trim() || S.kv.geminiModel);
    let msg = 'Klucz działa ✓';
    if (!have.has(cur)) {
      const next = pickFlash(models);
      if (next) { S.kv.geminiKey = k; S.kv.geminiModel = next; await kvSet('geminiKey', k); await kvSet('geminiModel', next); view.querySelector('#gmodel').value = next; msg += '. Model „' + cur + '” nie jest dostępny, ustawiłam „' + next + '”.'; }
      else msg += ', ale nie widzę żadnego modelu Gemini do odczytu zdjęć.';
    } else msg += '. Model „' + cur + '” jest dostępny.';
    st.textContent = msg;
  } catch (e) { st.textContent = e.status ? e.message : 'Nie mogę połączyć się z Google. Brak internetu?'; }
}

/* ---------- arkusze ---------- */
function sheet(title, body, footer = '') {
  const el = document.createElement('div');
  el.className = 'sheet';
  el.innerHTML = `<div class="sheet-in"><div class="sheet-top"><h3>${esc(title)}</h3><button class="x" data-close aria-label="Zamknij">×</button></div><div class="body">${body}</div></div>${footer ? `<div class="foot"><div class="foot-in">${footer}</div></div>` : ''}`;
  if (footer) el.classList.add('has-foot');
  document.body.append(el);
  el.querySelector('[data-close]').onclick = () => el.remove();
  el.close = () => el.remove();
  return el;
}

function askKey() {
  const el = sheet('Odczyt zdjęć paragonów', `<p>Do odczytu potrzebny jest Twój darmowy klucz Gemini. Zapisze się tylko w tym telefonie.</p>
    <label class="field"><span>Klucz Gemini</span><input id="ak" type="password" autocomplete="off" placeholder="wklej klucz"></label>
    <p class="hint">Klucz zrobisz za darmo na aistudio.google.com (Get API key). Nie wysyłaj go nikomu i nie wklejaj do czatu.</p>`,
    `<button class="btn" style="width:100%" data-ak="save">Zapisz klucz</button>`);
  el.addEventListener('click', async e => {
    if (!e.target.closest('[data-ak]')) return;
    const k = el.querySelector('#ak').value.trim();
    if (!k) { toast('Wklej klucz'); return; }
    S.kv.geminiKey = k; await kvSet('geminiKey', k); el.close(); toast('Klucz zapisany. Dotknij teraz „Zrób zdjęcie paragonu”.');
  });
}

function pickCat(cur, cb) {
  const el = sheet('Kategoria', `<div class="picker">${CATS.map(c => `<button class="chip ${c.id === cur ? 'on' : ''}" data-c="${c.id}">${c.e} ${c.n}</button>`).join('')}</div>`);
  el.addEventListener('click', e => { const b = e.target.closest('[data-c]'); if (b) { cb(b.dataset.c); el.close(); } });
}

const newLine = () => ({ id: uid(), name: '', cat: 'inne', auto: true, qty: '1', unit: 'szt', total: '', reg: '', showReg: false, chk: false });

function openReceipt(id) {
  const ex = id && S.receipts.find(r => r.id === id);
  const d = ex ? {
    id: ex.id, store: ex.store, date: ex.date, declared: ex.declared ? centsToInput(ex.declared) : '', banner: false,
    lines: ex.lines.map(l => ({ id: uid(), name: l.name, cat: l.cat, auto: false, qty: String(l.qty).replace('.', ','), unit: l.unit, total: centsToInput(l.total), reg: l.reg ? centsToInput(l.reg) : '', showReg: !!l.reg, chk: false })),
  } : { id: null, store: S.lastStore, date: todayISO(), declared: '', banner: false, lines: [newLine()] };

  const lineHtml = (l, i) => `<div class="ln ${l.chk ? 'chk' : ''}" data-i="${i}">
    <button class="ln-cat" data-ea="cat" aria-label="Kategoria">${catById(l.cat).e}</button>
    <div class="ln-main"><input class="f-name" list="prod" placeholder="Nazwa produktu" value="${esc(l.name)}" autocomplete="off">
      <div class="ln-row"><input class="f-qty" inputmode="decimal" value="${esc(l.qty)}" aria-label="Ilość"><select class="f-unit" aria-label="Jednostka">${['szt', 'kg', 'l'].map(u => `<option ${u === l.unit ? 'selected' : ''}>${u}</option>`).join('')}</select>
        <input class="f-total" inputmode="decimal" placeholder="Cena razem" value="${esc(l.total)}" aria-label="Cena razem"><button class="ln-del" data-ea="del" aria-label="Usuń pozycję">×</button></div>
      ${l.showReg ? `<input class="f-reg" inputmode="decimal" placeholder="Cena regularna razem (bez promocji)" value="${esc(l.reg)}">` : `<button class="lnk" data-ea="reg">Była promocja?</button>`}</div></div>`;

  const el = sheet(ex ? 'Paragon' : 'Nowy paragon', '', `<div id="ft"></div>`);
  const body = el.querySelector('.body'), ft = el.querySelector('#ft');

  function paint() {
    body.innerHTML = `<div class="chips" role="group" aria-label="Sklep">${STORES.map(s => `<button class="chip" aria-pressed="${s === d.store}" data-ea="store" data-s="${s}">${s}</button>`).join('')}</div>
      <label class="field"><span>Data zakupów</span><input type="date" class="f-date" value="${d.date}" max="${todayISO()}"></label>
      <button class="btn" style="width:100%;margin-bottom:6px" data-ea="photo">📷 Zrób zdjęcie paragonu</button>
      <p class="hint" style="margin:0 0 16px;text-align:center">Odczytam pozycje, Ty tylko sprawdzisz. Możesz też wybrać zdjęcie z galerii albo wpisać ręcznie poniżej.</p><input type="file" class="f-photo" accept="image/*" hidden>
      ${d.banner ? `<div class="stat warn" style="background:#FFF6D9;color:#5A4300">Odczytano ze zdjęcia. Sprawdź każdą żółtą pozycję z paragonem w ręku. <button class="lnk" data-ea="checked">Sprawdziłem</button></div>` : ''}
      <div id="lines">${d.lines.map(lineHtml).join('')}</div>
      <button class="btn line sm" data-ea="add">+ Dodaj pozycję</button>
      <label class="field" style="margin-top:18px"><span>Suma na paragonie (do sprawdzenia)</span><input class="f-decl" inputmode="decimal" placeholder="np. 87,45" value="${esc(d.declared)}"></label>`;
    upd();
  }
  const validLine = l => l.name.trim() && !isNaN(parseMoney(l.total)) && parseMoney(l.total) !== 0 && parseNum(l.qty) > 0;
  function upd() {
    let sum = 0; for (const l of d.lines) { const v = parseMoney(l.total); if (!isNaN(v)) sum += v; }
    const dec = parseMoney(d.declared), has = !isNaN(dec) && dec > 0;
    const diff = has ? dec - sum : 0;
    const [cls, txt] = !has ? ['info', 'Wpisz sumę z paragonu, a sprawdzę, czy pozycje się zgadzają.']
      : diff === 0 ? ['ok', '✓ Suma pozycji zgadza się z paragonem']
      : ['warn', (diff > 0 ? 'Brakuje pozycji za ' : 'Pozycje są droższe o ') + zl(Math.abs(diff)) + '. Sprawdź ilości i ceny.'];
    const n = d.lines.filter(validLine).length;
    ft.innerHTML = `<div class="stat ${cls}">${txt}</div><div class="sumrow"><span>Suma pozycji (${n})</span><span class="num">${zl(sum)}</span></div>
      <div class="row" style="flex-wrap:nowrap">${ex ? '<button class="btn danger" data-ea="delete">Usuń</button>' : ''}<button class="btn" style="flex:1" data-ea="save" ${n && d.date ? '' : 'disabled'}>${has && diff !== 0 ? 'Zapisz mimo różnicy' : 'Zapisz paragon'}</button></div>`;
  }

  el.addEventListener('input', e => {
    const t = e.target, row = t.closest('.ln'), l = row && d.lines[+row.dataset.i];
    if (t.classList.contains('f-date')) d.date = t.value;
    else if (t.classList.contains('f-decl')) d.declared = t.value;
    else if (l) {
      if (t.classList.contains('f-name')) { l.name = t.value; if (l.auto) { l.cat = catOf(l.name); row.querySelector('.ln-cat').textContent = catById(l.cat).e; } }
      else if (t.classList.contains('f-qty')) l.qty = t.value;
      else if (t.classList.contains('f-unit')) l.unit = t.value;
      else if (t.classList.contains('f-total')) l.total = t.value;
      else if (t.classList.contains('f-reg')) l.reg = t.value;
      if (l.chk && !t.classList.contains('f-name')) { /* zostaje żółte do potwierdzenia */ }
    }
    upd();
  });
  el.addEventListener('change', e => {
    const t = e.target, row = t.closest('.ln'), l = row && d.lines[+row.dataset.i];
    if (l && t.classList.contains('f-name')) {
      const p = products(S.receipts).find(x => x.key === norm(l.name));
      if (p) { l.cat = p.cat; l.auto = false; l.unit = p.unit; row.querySelector('.ln-cat').textContent = catById(l.cat).e; row.querySelector('.f-unit').value = l.unit; }
    }
    if (t.classList.contains('f-photo') && t.files[0]) doPhoto(t.files[0]);
  });
  el.addEventListener('click', async e => {
    const b = e.target.closest('[data-ea]'); if (!b) return;
    const row = b.closest('.ln'), i = row ? +row.dataset.i : -1, a = b.dataset.ea;
    if (a === 'store') { d.store = b.dataset.s; el.querySelectorAll('[data-ea="store"]').forEach(x => x.setAttribute('aria-pressed', x.dataset.s === d.store)); }
    else if (a === 'add') { d.lines.push(newLine()); paint(); const ins = body.querySelectorAll('.f-name'); ins[ins.length - 1].focus(); }
    else if (a === 'del') { d.lines.splice(i, 1); if (!d.lines.length) d.lines.push(newLine()); paint(); }
    else if (a === 'reg') { d.lines[i].showReg = true; paint(); }
    else if (a === 'cat') pickCat(d.lines[i].cat, c => { d.lines[i].cat = c; d.lines[i].auto = false; paint(); });
    else if (a === 'checked') { d.lines.forEach(l => (l.chk = false)); d.banner = false; paint(); }
    else if (a === 'photo') {
      if (!S.kv.geminiKey) { askKey(); return; }
      body.querySelector('.f-photo').click();
    }
    else if (a === 'delete') { if (confirm('Usunąć ten paragon?')) { await del('receipts', d.id); S.receipts = S.receipts.filter(r => r.id !== d.id); el.close(); render(); toast('Paragon usunięty'); } }
    else if (a === 'save') await save();
  });

  async function doPhoto(file) {
    toast('Odczytuję paragon…');
    try {
      const r = await readReceipt(file, S.kv.geminiKey, S.kv.geminiModel);
      if (r.usedModel && r.usedModel !== S.kv.geminiModel) { S.kv.geminiModel = r.usedModel; await kvSet('geminiModel', r.usedModel); }
      if (r.store) d.store = r.store;
      if (r.date) d.date = r.date;
      if (r.declared) d.declared = centsToInput(r.declared);
      if (r.lines.length) d.lines = r.lines.map(l => ({ id: uid(), name: l.name, cat: catOf(l.name), auto: true, qty: String(l.qty).replace('.', ','), unit: l.unit, total: centsToInput(l.total), reg: '', showReg: false, chk: true }));
      d.banner = true; paint();
      toast(r.lines.length ? 'Odczytano ' + r.lines.length + ' pozycji. Sprawdź je.' : 'Nie znaleziono pozycji. Wpisz ręcznie.');
    } catch (err) { toast(err.message); }
  }
  async function save() {
    const lines = d.lines.filter(validLine).map(l => {
      const total = parseMoney(l.total), reg = parseMoney(l.reg);
      return { name: l.name.trim(), cat: l.cat, qty: parseNum(l.qty), unit: l.unit, total, reg: !isNaN(reg) && reg > total ? reg : 0 };
    });
    const sum = lines.reduce((s, l) => s + l.total, 0), dec = parseMoney(d.declared), has = !isNaN(dec) && dec > 0;
    const rec = { id: d.id || uid(), store: d.store, date: d.date, lines, declared: has ? dec : 0, check: !has ? 'none' : dec === sum ? 'ok' : 'diff' };
    await put('receipts', rec);
    S.receipts = [...S.receipts.filter(r => r.id !== rec.id), rec];
    S.lastStore = rec.store; S.ym = ymOf(rec.date);
    el.close(); render(); toast('Paragon zapisany');
  }
  paint();
}

function openProduct(key) {
  const p = products(S.receipts).find(x => x.key === key); if (!p) return;
  const h = p.hist, ups = h.map(e => e.up), lo = Math.min(...ups), hi = Math.max(...ups);
  const W = 300, Hh = 80;
  const pts = h.map((e, i) => `${h.length === 1 ? W / 2 : 8 + (i * (W - 16)) / (h.length - 1)},${hi === lo ? Hh / 2 : 8 + (1 - (e.up - lo) / (hi - lo)) * (Hh - 16)}`);
  const spark = h.length >= 2 ? `<svg class="spark" viewBox="0 0 ${W} ${Hh}" preserveAspectRatio="none" aria-label="Wykres cen"><polyline fill="none" stroke="var(--green)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="${pts.join(' ')}"/>${pts.map(q => `<circle cx="${q.split(',')[0]}" cy="${q.split(',')[1]}" r="3.5" fill="var(--green)"/>`).join('')}</svg>` : '<p class="hint">Wykres pojawi się po drugim zakupie.</p>';
  const byStore = {}; for (const e of h) byStore[e.store] = Math.min(byStore[e.store] ?? Infinity, e.up);
  const el = sheet(p.name, `<p class="sub" style="margin:-4px 0 14px">${catById(p.cat).e} ${catById(p.cat).n}</p>
    <div class="card">${spark}<div class="kv"><span>Ostatnio</span><b>${zl(p.last)}/${p.unit}</b></div><div class="kv"><span>Najniżej</span><b>${zl(p.min)}/${p.unit}</b></div>
    <div class="kv"><span>Zwykła cena (mediana)</span><b>${p.n >= 3 ? zl(p.med) + '/' + p.unit : 'po 3 zakupach'}</b></div><div class="kv"><span>Liczba zakupów</span><b>${p.n}</b></div></div>
    ${Object.keys(byStore).length > 1 ? `<h2>Najniższa cena wg sklepu</h2><div class="card">${Object.entries(byStore).sort((a, b) => a[1] - b[1]).map(([s, v]) => `<div class="kv"><span>${esc(s)}</span><b>${zl(v)}/${p.unit}</b></div>`).join('')}</div>` : ''}
    <h2>Historia</h2><div class="card">${[...h].reverse().slice(0, 10).map(e => `<div class="kv"><span>${fmtDate(e.date)} · ${esc(e.store)}${e.reg > e.total ? ' · promocja' : ''}</span><b>${zl(e.up)}/${e.unit}</b></div>`).join('')}</div>
    ${p.skipped ? `<p class="hint">Pominięto ${p.skipped} zakupów w innej jednostce.</p>` : ''}`);
  return el;
}

function openSrvOffer(o) {
  const c = offerCalc(o), v = offerVerdict(o), sure = isSure(o);
  const el = sheet('Oferta ' + o.store, `<h2 style="margin-top:0">${esc(o.name)}</h2>
    ${promoPill(o) ? `<p style="margin:0 0 8px">${promoPill(o)}</p>` : ''}
    <div class="kv"><span>${isHidden(o) ? 'Cena z odczytu' : `Cena ${c.need > 1 && o.mode !== 'unit' ? 'kompletu' : 'opakowania'}`}</span><b>${zl(c.total)}</b></div>
    ${o.old ? `<div class="kv"><span>Cena przed obniżką</span><b>${zl(o.old)}</b></div>` : ''}
    ${sure ? `<div class="kv"><span>Zawartość</span><b>${esc(packLabel(o))}</b></div>
    <div class="kv"><span>Za ${esc(unitPrice(o).label)}</span><b>${zl(unitPrice(o).price)}</b></div>` : ''}
    ${o.printed ? `<div class="kv"><span>${o.store === 'Lidl' ? 'Na gazetce' : 'W sklepie'}</span><b>${esc(o.printed)}</b></div>` : ''}
    ${o.deposit ? `<div class="kv"><span>Kaucja (poza ceną)</span><b>${zl(o.deposit)}</b></div>` : ''}
    <div class="kv"><span>Ważna</span><b>${o.from ? fmtDate(o.from) + ' – ' : 'do '}${fmtDate(o.until)}</b></div>
    ${o.cond ? `<div class="kv"><span>Warunek</span><b>${esc(o.cond)}</b></div>` : ''}
    ${whereLabel(o) ? `<div class="kv"><span>Gdzie szukać</span><b>${esc(whereLabel(o))}</b></div>` : ''}
    ${flyerUrl(o) ? `<p><a class="lnk" href="${esc(flyerUrl(o))}" target="_blank" rel="noopener">Otwórz tę stronę gazetki</a></p>` : ''}
    ${sure && v ? `<p><span class="pill ${v.t}">${esc(v.txt)}</span></p>` : ''}
    ${isHidden(o) ? `<p class="hint">Odczytu nie dało się potwierdzić${o.note ? ': ' + esc(o.note) : ''}. Dlatego nie ma tu przeliczeń ani oceny. Sprawdź ofertę u źródła.</p>` : sure ? '' : `<p class="hint">Cena jest pewna, ale ${esc(o.note || 'nie da się policzyć ceny za jednostkę')}.</p>`}
    <p class="hint">Oferta pobrana automatycznie z serwera, więc nie można jej edytować.</p>`);
  return el;
}

function openOffer(id) {
  const sv = id && String(id).startsWith('s:') && allOffers().find(o => o.id === id);
  if (sv) return openSrvOffer(sv);
  const ex = id && S.offers.find(o => o.id === id);
  const inDays = k => { const d = new Date(); d.setDate(d.getDate() + k); return todayISO(d); };
  const d = ex ? { ...ex, mode: ex.mode || 'unit', need: String(ex.need || 1), pct: String(ex.pct || 50), price: centsToInput(ex.price), amount: fmtN(ex.amount) }
    : { id: null, store: S.lastStore, name: '', cat: 'inne', auto: true, mode: 'unit', need: '1', pct: '50', price: '', amount: '1', unit: 'szt', until: inDays(6), cond: '' };
  const MODES = [['unit', 'Za sztukę'], ['bundle', 'Komplet'], ['nth', 'Drugi taniej']];
  const el = sheet(ex ? 'Okazja' : 'Nowa okazja', `<div class="chips">${STORES.map(s => `<button class="chip" aria-pressed="${s === d.store}" data-s="${s}">${s}</button>`).join('')}</div>
    <label class="field"><span>Produkt</span><input class="o-name" list="prod" value="${esc(d.name)}" placeholder="np. Coca-Cola" autocomplete="off"></label>
    <div class="field"><span>Rodzaj promocji</span><div class="seg" style="margin:0">${MODES.map(([m, n]) => `<button aria-pressed="${m === d.mode}" data-mode="${m}">${n}</button>`).join('')}</div></div>
    <div class="row" style="flex-wrap:nowrap"><label class="field" style="flex:1"><span class="o-pl"></span><input class="o-price" inputmode="decimal" value="${esc(d.price)}" placeholder="0,00"></label>
      <label class="field o-needw" style="width:96px"><span class="o-nl">Ile sztuk</span><input class="o-need" inputmode="numeric" value="${esc(d.need)}"></label>
      <label class="field o-pctw" style="width:84px"><span>Taniej o %</span><input class="o-pct" inputmode="numeric" value="${esc(d.pct)}"></label></div>
    <div class="row" style="flex-wrap:nowrap"><label class="field" style="flex:1"><span>Ile w jednym opakowaniu</span><input class="o-amount" inputmode="decimal" value="${esc(d.amount)}"></label>
      <label class="field" style="width:96px"><span>Jednostka</span><select class="o-unit">${UNITS.map(u => `<option ${u === d.unit ? 'selected' : ''}>${u}</option>`).join('')}</select></label></div>
    <label class="field"><span>Ważna do</span><input type="date" class="o-until" value="${d.until}"></label>
    <label class="field"><span>Warunek (opcjonalnie)</span><input class="o-cond" value="${esc(d.cond)}" placeholder="np. z kartą, limit 3 szt."></label>
    <div class="row" style="margin-bottom:12px"><button class="btn line sm o-cat">${catById(d.cat).e} ${catById(d.cat).n}</button></div><div id="prev"></div>`,
    `<div class="row" style="flex-wrap:nowrap">${ex ? '<button class="btn danger" data-oa="delete">Usuń</button>' : ''}<button class="btn" style="flex:1" data-oa="save">Zapisz okazję</button></div>`);
  const prev = el.querySelector('#prev');
  const build = () => {
    const price = parseMoney(d.price), amt = parseNum(d.amount), need = Math.max(1, Math.round(parseNum(d.need) || 1)), pct = parseNum(d.pct);
    if (isNaN(price) || !(amt > 0) || price <= 0) return null;
    if (d.mode === 'nth' && (!(pct > 0) || pct > 100 || need < 2)) return null;
    return { id: d.id || 'new', store: d.store, name: d.name.trim() || '?', cat: d.cat, price, amount: amt, unit: d.unit, until: d.until, cond: d.cond.trim(), mode: d.mode, need: d.mode === 'unit' ? 1 : need, pct: d.mode === 'nth' ? pct : 0 };
  };
  function upd() {
    el.querySelector('.o-pl').textContent = d.mode === 'bundle' ? 'Cena za komplet' : d.mode === 'nth' ? 'Cena jednej sztuki' : 'Cena promocyjna';
    el.querySelector('.o-needw').style.display = d.mode === 'unit' ? 'none' : '';
    el.querySelector('.o-nl').textContent = d.mode === 'nth' ? 'Ile kupić' : 'Ile sztuk';
    el.querySelector('.o-pctw').style.display = d.mode === 'nth' ? '' : 'none';
    el.querySelectorAll('[data-mode]').forEach(x => x.setAttribute('aria-pressed', x.dataset.mode === d.mode));
    const o = build();
    if (!o) { prev.innerHTML = '<p class="hint">Wpisz cenę i wielkość opakowania, a przeliczę to na litr, kilogram lub sztukę i ocenię na tle Waszych zakupów.</p>'; return; }
    const c = offerCalc(o), v = verdict(c.up, c.base, matchProduct(products(S.receipts), d.name));
    let rank = '';
    const g = compareGroups([...allOffers().filter(x => x.id !== d.id), { ...o, id: 'new' }], todayISO()).find(g => g.rows.some(r => r.o.id === 'new'));
    if (g) { const me = g.rows.find(r => r.o.id === 'new'); rank = `<div class="kv"><span>Na tle innych (${esc(g.fam.n)})</span><b>${me.rank}. z ${g.rows.length}${me.rank === 1 ? '' : ', najtaniej ' + esc(g.best.o.store)}</b></div>`; }
    prev.innerHTML = `<div class="card"><div class="kv"><span>${c.need > 1 && o.mode !== 'unit' ? 'Cena kompletu' : 'Cena opakowania'}</span><b>${zl(c.total)}</b></div>
      <div class="kv"><span>Zawartość</span><b>${esc(packLabel(o))}</b></div>
      <div class="kv"><span>Za ${esc(unitPrice(o).label)}</span><b>${zl(unitPrice(o).price)}</b></div>${rank}
      <div style="padding-top:8px"><span class="pill ${v.t}">${esc(v.txt)}</span></div></div>`;
  }
  upd();
  el.addEventListener('input', e => {
    const t = e.target;
    if (t.classList.contains('o-name')) { d.name = t.value; if (d.auto) { d.cat = catOf(d.name); el.querySelector('.o-cat').textContent = catById(d.cat).e + ' ' + catById(d.cat).n; } }
    else if (t.classList.contains('o-price')) d.price = t.value;
    else if (t.classList.contains('o-need')) d.need = t.value;
    else if (t.classList.contains('o-pct')) d.pct = t.value;
    else if (t.classList.contains('o-amount')) d.amount = t.value;
    else if (t.classList.contains('o-unit')) d.unit = t.value;
    else if (t.classList.contains('o-until')) d.until = t.value;
    else if (t.classList.contains('o-cond')) d.cond = t.value;
    upd();
  });
  el.addEventListener('change', e => {
    if (e.target.classList.contains('o-name')) { const p = products(S.receipts).find(x => x.key === norm(d.name)); if (p) { d.unit = p.unit; d.cat = p.cat; d.auto = false; el.querySelector('.o-unit').value = d.unit; el.querySelector('.o-cat').textContent = catById(d.cat).e + ' ' + catById(d.cat).n; upd(); } }
  });
  el.addEventListener('click', async e => {
    const s = e.target.closest('[data-s]');
    if (s) { d.store = s.dataset.s; el.querySelectorAll('[data-s]').forEach(x => x.setAttribute('aria-pressed', x.dataset.s === d.store)); upd(); return; }
    const m = e.target.closest('[data-mode]');
    if (m) { d.mode = m.dataset.mode; if (d.mode === 'nth' && (parseNum(d.need) || 1) < 2) { d.need = '2'; el.querySelector('.o-need').value = '2'; } if (d.mode === 'bundle' && (parseNum(d.need) || 1) < 2) { d.need = '3'; el.querySelector('.o-need').value = '3'; } upd(); return; }
    if (e.target.closest('.o-cat')) { pickCat(d.cat, c => { d.cat = c; d.auto = false; el.querySelector('.o-cat').textContent = catById(c).e + ' ' + catById(c).n; }); return; }
    const b = e.target.closest('[data-oa]'); if (!b) return;
    if (b.dataset.oa === 'delete') { await del('offers', d.id); S.offers = S.offers.filter(o => o.id !== d.id); el.close(); render(); toast('Okazja usunięta'); return; }
    const built = build();
    if (!d.name.trim() || !built || !d.until) { toast('Uzupełnij produkt, cenę, wielkość opakowania i datę'); return; }
    const o = { ...built, id: d.id || uid(), name: d.name.trim() };
    await put('offers', o);
    S.offers = [...S.offers.filter(x => x.id !== o.id), o];
    S.lastStore = o.store; el.close(); render(); toast('Okazja zapisana');
  });
}

function openCatLimit(c) {
  const cat = catById(c), cur = (S.kv.catLimits || {})[c] || 0;
  const el = sheet('Limit: ' + cat.n, `<label class="field"><span>Limit miesięczny w tej kategorii (zł)</span><input id="cl" inputmode="decimal" value="${cur ? centsToInput(cur).replace(',00', '') : ''}" placeholder="np. 600"></label>`,
    `<div class="row" style="flex-wrap:nowrap">${cur ? '<button class="btn danger" data-cl="rm">Usuń limit</button>' : ''}<button class="btn" style="flex:1" data-cl="save">Zapisz</button></div>`);
  el.addEventListener('click', async e => {
    const b = e.target.closest('[data-cl]'); if (!b) return;
    const map = { ...(S.kv.catLimits || {}) };
    if (b.dataset.cl === 'rm') delete map[c];
    else { const v = parseMoney(el.querySelector('#cl').value); if (isNaN(v) || v <= 0) { toast('Wpisz kwotę większą od zera'); return; } map[c] = v; }
    S.kv.catLimits = map; await kvSet('catLimits', map); el.close(); render();
  });
}

/* ---------- kopie ---------- */
async function doExport() {
  const data = { app: 'zakupy', v: 1, at: new Date().toISOString(), receipts: S.receipts, offers: S.offers, kv: { limit: S.kv.limit || 0, catLimits: S.kv.catLimits || {} } };
  const file = new File([JSON.stringify(data)], 'zakupy-kopia-' + todayISO() + '.json', { type: 'application/json' });
  if (navigator.canShare && navigator.canShare({ files: [file] })) { try { await navigator.share({ files: [file], title: 'Kopia Zakupy' }); return; } catch (e) { if (e.name === 'AbortError') return; } }
  const a = document.createElement('a'); a.href = URL.createObjectURL(file); a.download = file.name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
async function doImport(file) {
  let j; try { j = JSON.parse(await file.text()); } catch (_) { toast('To nie jest plik kopii'); return; }
  if (j.app !== 'zakupy' || !Array.isArray(j.receipts) || !Array.isArray(j.offers)) { toast('To nie jest kopia aplikacji Zakupy'); return; }
  if (!confirm('Wczytać kopię? Obecne dane zostaną zastąpione (' + j.receipts.length + ' paragonów).')) return;
  await clear('receipts'); await clear('offers');
  for (const r of j.receipts) await put('receipts', r);
  for (const o of j.offers) await put('offers', o);
  S.receipts = j.receipts; S.offers = j.offers;
  S.kv.limit = (j.kv && j.kv.limit) || 0; S.kv.catLimits = (j.kv && j.kv.catLimits) || {};
  await kvSet('limit', S.kv.limit); await kvSet('catLimits', S.kv.catLimits);
  render(); toast('Kopia wczytana');
}

/* ---------- zdarzenia ---------- */
view.addEventListener('input', e => {
  if (e.target.dataset.q) { S.q = e.target.value; const pos = e.target.selectionStart; render(); const n = view.querySelector('[data-q]'); n.focus(); n.setSelectionRange(pos, pos); }
});
view.addEventListener('input', e => {
  if (e.target.id !== 'oq') return;
  S.oq = e.target.value; const pos = e.target.selectionStart; render();
  const n = view.querySelector('#oq'); if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (_) {} }
});
view.addEventListener('change', e => { if (e.target.id === 'impfile' && e.target.files[0]) doImport(e.target.files[0]); });
view.addEventListener('click', async e => {
  const b = e.target.closest('[data-act]'); if (!b) return;
  const a = b.dataset.act;
  if (a === 'new') openReceipt();
  else if (a === 'receipt') openReceipt(b.dataset.id);
  else if (a === 'product') openProduct(b.dataset.k);
  else if (a === 'newoffer') openOffer();
  else if (a === 'offer') openOffer(b.dataset.id);
  else if (a === 'cat') { S.cat = b.dataset.c; render(); }
  else if (a === 'ocat') { S.ocat = b.dataset.c; render(); }
  else if (a === 'omode') { S.omode = b.dataset.m; render(); }
  else if (a === 'ounsure') { S.ounsure = !S.ounsure; render(); }
  else if (a === 'goto') { S.tab = b.dataset.tab; render(); }
  else if (a === 'mprev') { S.ym = addMonth(S.ym, -1); render(); }
  else if (a === 'mnext') { S.ym = addMonth(S.ym, 1); render(); }
  else if (a === 'catlimit') openCatLimit(b.dataset.c);
  else if (a === 'purge') { for (const o of S.offers.filter(o => o.until < todayISO())) await del('offers', o.id); S.offers = S.offers.filter(o => o.until >= todayISO()); render(); toast('Zakończone okazje usunięte'); }
  else if (a === 'savelimit') { const v = parseMoney(view.querySelector('#limit').value); S.kv.limit = isNaN(v) || v < 0 ? 0 : v; await kvSet('limit', S.kv.limit); render(); toast(S.kv.limit ? 'Limit zapisany' : 'Limit usunięty'); }
  else if (a === 'export') doExport();
  else if (a === 'import') view.querySelector('#impfile').click();
  else if (a === 'upd') manualUpdate();
  else if (a === 'forceupd') { if (confirm('Pobrać aplikację od nowa? Dane zostaną nietknięte.')) forceRefresh(); }
  else if (a === 'showkey') { const i = view.querySelector('#gkey'); i.type = i.type === 'password' ? 'text' : 'password'; b.textContent = i.type === 'password' ? 'Pokaż' : 'Ukryj'; }
  else if (a === 'testkey') testKey();
  else if (a === 'delkey') { S.kv.geminiKey = ''; await kvSet('geminiKey', ''); render(); toast('Klucz usunięty'); }
  else if (a === 'wipe') {
    if (!confirm('Usunąć WSZYSTKIE paragony, okazje i limity z tego telefonu? Tego nie da się cofnąć. Zapisz kopię, jeśli chcesz je zachować.')) return;
    await clear('receipts'); await clear('offers');
    for (const k of ['limit', 'catLimits']) { S.kv[k] = k === 'limit' ? 0 : {}; await kvSet(k, S.kv[k]); }
    S.receipts = []; S.offers = []; render(); toast('Dane usunięte');
  }
  else if (a === 'savesrv') { S.kv.srvUrl = view.querySelector('#surl').value.trim(); await kvSet('srvUrl', S.kv.srvUrl); const ok = await fetchSrv(true); if (ok) render(); }
  else if (a === 'getsrv') { if (await fetchSrv(true)) render(); }
  else if (a === 'savegem') { S.kv.geminiKey = view.querySelector('#gkey').value.trim(); S.kv.geminiModel = effectiveModel(view.querySelector('#gmodel').value.trim()); await kvSet('geminiKey', S.kv.geminiKey); await kvSet('geminiModel', S.kv.geminiModel); render(); toast('Ustawienia zapisane'); }
});

init();
window.__zakupy = { S, render };
