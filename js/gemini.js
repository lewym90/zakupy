// Odczyt zdjęcia paragonu przez Gemini. Model tylko "czyta"; wynik trafia do formularza
// jako PROPOZYCJA i jest sprawdzany kodem (suma pozycji = suma na paragonie).
// Klucz jest tylko w tym telefonie (IndexedDB), nigdy w repozytorium.
import { STORES } from './cats.js';

export const DEFAULT_MODEL = 'gemini-3.8-flash';
// Modele wycofane przez Google (zapisane wcześniej w telefonie traktujemy jak "domyślny").
const RETIRED = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-2.0-flash-001', 'gemini-1.5-flash-latest'];
export const effectiveModel = m => (!m || RETIRED.includes(m) ? DEFAULT_MODEL : m);

// Z listy modeli Google wybiera najnowszy zwykły model "flash" umiejący generateContent.
export function pickFlash(models) {
  const cand = [];
  for (const m of models || []) {
    const name = String(m.name || '').replace(/^models\//, '');
    const mm = /^gemini-(\d+(?:\.\d+)?)-flash$/.exec(name);
    if (!mm) continue;
    if (m.supportedGenerationMethods && !m.supportedGenerationMethods.includes('generateContent')) continue;
    cand.push({ name, v: parseFloat(mm[1]) });
  }
  cand.sort((a, b) => b.v - a.v);
  return cand.length ? cand[0].name : null;
}

export async function listModels(key) {
  const r = await fetch('https://generativelanguage.googleapis.com/v1beta/models?pageSize=200', { headers: { 'x-goog-api-key': key } });
  if (!r.ok) throw await apiError(r);
  const j = await r.json();
  return j.models || [];
}

// Po polsku, krótko, z informacją co zrobić.
async function apiError(r) {
  let raw = '';
  try { const j = await r.json(); raw = (j.error && j.error.message) || ''; } catch (_) {}
  const e = new Error(
    r.status === 404 ? 'Google wycofał ten model. Spróbuję znaleźć działający.' :
    r.status === 400 && /API key/i.test(raw) ? 'Google odrzuca klucz. Sprawdź, czy skopiowałeś go w całości (Ustawienia).' :
    r.status === 403 ? 'Klucz nie ma dostępu do tej usługi. Sprawdź go w Ustawieniach.' :
    r.status === 429 ? 'Przekroczony darmowy limit Gemini. Poczekaj chwilę i spróbuj ponownie.' :
    'Błąd Google ' + r.status + (raw ? ': ' + raw.slice(0, 120) : ''));
  e.status = r.status; e.raw = raw;
  return e;
}

const PROMPT = `Odczytaj paragon ze zdjęcia. Zwróć wyłącznie JSON w formacie:
{"sklep": string|null, "data": "RRRR-MM-DD"|null, "suma": number|null, "pozycje": [{"nazwa": string, "ilosc": number, "jednostka": "szt"|"kg"|"l", "wartosc": number}]}
Zasady: kwoty w złotych jako liczby (kropka dziesiętna). "suma" to kwota do zapłaty z paragonu. "wartosc" to kwota pozycji po jej rabacie. Rabat podany osobną linią zapisz jako osobną pozycję z ujemną wartością i nazwą "Rabat". Dla towarów na wagę podaj masę w "ilosc" i jednostkę "kg". Nie zgaduj: gdy coś jest nieczytelne, wpisz null. Nie dodawaj pozycji, których nie widać na zdjęciu.`;

export function shrinkImage(file, max = 1600) {
  return new Promise((res, rej) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const k = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement('canvas');
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      res(c.toDataURL('image/jpeg', 0.85).split(',')[1]);
    };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('Nie udało się otworzyć zdjęcia.')); };
    img.src = url;
  });
}

async function callModel(b64, key, model) {
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/' + encodeURIComponent(model) + ':generateContent';
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key },
    body: JSON.stringify({
      contents: [{ parts: [{ text: PROMPT }, { inline_data: { mime_type: 'image/jpeg', data: b64 } }] }],
      generationConfig: { responseMimeType: 'application/json', temperature: 0 },
    }),
  });
  if (!r.ok) throw await apiError(r);
  return r.json();
}

// Zwraca odczyt + `usedModel`. Gdy model nie istnieje (404), pobiera listę modeli i próbuje najnowszego "flash".
export async function readReceipt(file, key, model) {
  const b64 = await shrinkImage(file);
  let used = effectiveModel(model), j;
  try { j = await callModel(b64, key, used); }
  catch (e) {
    if (e.status !== 404) throw e;
    const next = pickFlash(await listModels(key));
    if (!next || next === used) throw new Error('Nie znalazłem działającego modelu Gemini dla tego klucza. Sprawdź klucz w Ustawieniach.');
    used = next; j = await callModel(b64, key, used);
  }
  const txt = j.candidates && j.candidates[0] && j.candidates[0].content && j.candidates[0].content.parts.map(p => p.text || '').join('');
  if (!txt) throw new Error('Pusta odpowiedź modelu.');
  let o;
  try { o = JSON.parse(txt); } catch (_) { throw new Error('Odpowiedź nie jest poprawnym JSON-em.'); }
  return { ...cleanRead(o), usedModel: used };
}

// Czyszczenie odpowiedzi: tylko poprawne typy, nic nie "dopowiadamy".
export function cleanRead(o) {
  const num = v => (typeof v === 'number' && isFinite(v) ? v : null);
  const store = (() => {
    const s = String(o.sklep || '').toLowerCase();
    return STORES.find(x => x !== 'Inny' && s.includes(x.toLowerCase())) || (o.sklep ? 'Inny' : null);
  })();
  const date = /^\d{4}-\d{2}-\d{2}$/.test(o.data || '') ? o.data : null;
  const lines = (Array.isArray(o.pozycje) ? o.pozycje : []).map(p => ({
    name: String(p.nazwa || '').trim(),
    qty: num(p.ilosc) > 0 ? p.ilosc : 1,
    unit: ['szt', 'kg', 'l'].includes(p.jednostka) ? p.jednostka : 'szt',
    total: num(p.wartosc) === null ? null : Math.round(p.wartosc * 100),
  })).filter(l => l.name && l.total !== null);
  return { store, date, declared: num(o.suma) === null ? null : Math.round(o.suma * 100), lines };
}
