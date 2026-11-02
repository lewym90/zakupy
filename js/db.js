// Dane tylko w telefonie (IndexedDB). Nic nie wychodzi na serwer.
const NAME = 'zakupy', VER = 1;
let _db;
export function open() {
  if (_db) return _db;
  _db = new Promise((res, rej) => {
    const r = indexedDB.open(NAME, VER);
    r.onupgradeneeded = () => {
      const d = r.result;
      d.createObjectStore('receipts', { keyPath: 'id' });
      d.createObjectStore('offers', { keyPath: 'id' });
      d.createObjectStore('kv');
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  return _db;
}
function run(store, mode, fn) {
  return open().then(d => new Promise((res, rej) => {
    const t = d.transaction(store, mode);
    const req = fn(t.objectStore(store));
    t.oncomplete = () => res(req ? req.result : undefined);
    t.onerror = () => rej(t.error);
    t.onabort = () => rej(t.error);
  }));
}
export const all = s => run(s, 'readonly', st => st.getAll());
export const put = (s, o) => run(s, 'readwrite', st => st.put(o));
export const del = (s, id) => run(s, 'readwrite', st => st.delete(id));
export const clear = s => run(s, 'readwrite', st => st.clear());
export const kvGet = k => run('kv', 'readonly', st => st.get(k));
export const kvSet = (k, v) => run('kv', 'readwrite', st => st.put(v, k));
