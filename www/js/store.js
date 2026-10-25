/* User data store (IndexedDB). Lives in the app's private storage, completely separate from
   the book content shipped in the APK, so installing a new APK never touches it. */
const Store = (() => {
  const DB_NAME = 'psychengine-user';
  const STORES = ['highlights', 'bookmarks', 'cards', 'kv'];
  let dbp = null;

  function open() {
    if (dbp) return dbp;
    dbp = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        for (const s of STORES) {
          if (db.objectStoreNames.contains(s)) continue;
          const os = db.createObjectStore(s, { keyPath: s === 'kv' ? 'key' : 'id' });
          if (s !== 'kv') os.createIndex('bookUid', 'bookUid');
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbp;
  }

  async function tx(store, mode, fn) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const t = db.transaction(store, mode);
      const res = fn(t.objectStore(store));
      t.oncomplete = () => resolve(res && 'result' in res ? res.result : undefined);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
  }

  const get = (s, k) => tx(s, 'readonly', (os) => os.get(k));
  const all = (s) => tx(s, 'readonly', (os) => os.getAll());
  const put = async (s, obj) => { await tx(s, 'readwrite', (os) => os.put(obj)); scheduleBackup(); return obj; };
  const del = async (s, k) => { await tx(s, 'readwrite', (os) => os.delete(k)); scheduleBackup(); };
  const byBook = (s, bookUid) => tx(s, 'readonly', (os) => os.index('bookUid').getAll(bookUid));

  const getKV = async (key, dflt) => { const r = await get('kv', key); return r ? r.value : dflt; };
  const setKV = (key, value, quiet) => tx('kv', 'readwrite', (os) => os.put({ key, value })).then(() => { if (!quiet) scheduleBackup(); });

  const uid = () => (crypto.randomUUID ? crypto.randomUUID() : 'id' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10));

  /* ---- backup / restore ---- */
  // Derived caches (search index) are not user data and are not backed up.
  const isUserKV = (k) => !k.startsWith('cache:');

  async function exportAll() {
    const kv = (await all('kv')).filter((r) => isUserKV(r.key));
    return {
      app: 'psychengine-reader', format: 1, exportedAt: new Date().toISOString(),
      highlights: await all('highlights'), bookmarks: await all('bookmarks'),
      cards: await all('cards'), kv,
    };
  }

  // Merge: records are matched by id; the one with the newer `updated` stamp wins. Never deletes.
  async function importAll(data) {
    if (!data || data.app !== 'psychengine-reader') throw new Error('Not a PsychEngine backup file');
    let added = 0, updated = 0;
    for (const s of ['highlights', 'bookmarks', 'cards']) {
      const have = new Map((await all(s)).map((r) => [r.id, r]));
      for (const r of data[s] || []) {
        const cur = have.get(r.id);
        if (!cur) { await tx(s, 'readwrite', (os) => os.put(r)); added++; }
        else if ((r.updated || 0) > (cur.updated || 0)) { await tx(s, 'readwrite', (os) => os.put(r)); updated++; }
      }
    }
    for (const r of data.kv || []) {
      if (!isUserKV(r.key)) continue;
      if (r.key.startsWith('progress:')) {
        const cur = await getKV(r.key);
        if (cur && (cur.ts || 0) >= (r.value.ts || 0)) continue;
      } else if (r.key.startsWith('reads:')) { // per-part reading credit: keep the larger of each value
        const cur = (await getKV(r.key)) || {};
        for (const [i, e] of Object.entries(r.value || {})) {
          const c = cur[i];
          cur[i] = c ? { sec: Math.max(c.sec, e.sec), max: Math.max(c.max, e.max), p: e.sec > c.sec ? e.p : c.p } : e;
        }
        await setKV(r.key, cur, true);
        continue;
      } else if (r.key === 'activity') { // reading seconds per day: keep the larger count for each day
        const cur = (await getKV(r.key)) || {};
        for (const [d, s] of Object.entries(r.value || {})) cur[d] = Math.max(cur[d] || 0, s);
        await setKV(r.key, cur, true);
        continue;
      } else if (await get('kv', r.key)) continue; // keep this device's settings
      await setKV(r.key, r.value, true);
    }
    scheduleBackup();
    return { added, updated };
  }

  /* ---- best-effort automatic copy into the phone's Documents folder ---- */
  let timer = null;
  function scheduleBackup() {
    clearTimeout(timer);
    timer = setTimeout(autoBackup, 4000);
  }
  async function autoBackup() {
    const fs = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Filesystem;
    if (!fs) return;
    try {
      await fs.writeFile({
        path: 'PsychEngine/backup.json', directory: 'DOCUMENTS', encoding: 'utf8', recursive: true,
        data: JSON.stringify(await exportAll()),
      });
      await setKV('lastAutoBackup', { ok: true, at: Date.now() }, true);
    } catch (e) {
      await setKV('lastAutoBackup', { ok: false, at: Date.now(), err: String(e && e.message || e) }, true);
    }
  }

  async function init() {
    await open();
    try { if (navigator.storage && navigator.storage.persist) await navigator.storage.persist(); } catch (e) { /* optional */ }
  }

  return { init, get, all, put, del, byBook, getKV, setKV, uid, exportAll, importAll, autoBackup };
})();
