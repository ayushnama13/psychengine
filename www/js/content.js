/* Read-only book content bundled in the APK (www/content/*.json). */
const Content = (() => {
  let index = null;
  const chapterCache = new Map();

  async function loadIndex() {
    if (index) return index;
    index = await (await fetch('content/index.json')).json();
    index.byUid = new Map(index.books.map((b) => [b.uid, b]));
    return index;
  }

  const book = (uid) => index.byUid.get(uid);

  async function chapter(bookUid, idx) {
    const key = bookUid + '/' + idx;
    if (!chapterCache.has(key)) {
      const r = await fetch(`content/${bookUid}/${idx}.json`);
      if (!r.ok) throw new Error('chapter missing: ' + key);
      chapterCache.set(key, await r.json());
    }
    return chapterCache.get(key);
  }

  // Fraction (0..1) of a book read, from chapter + paragraph position.
  function bookFraction(b, chapterIdx, paraIdx) {
    const total = b.chapters.reduce((s, c) => s + c.chars, 0) || 1;
    let before = 0;
    for (const c of b.chapters) {
      if (c.idx >= chapterIdx) break;
      before += c.chars;
    }
    const cur = b.chapters.find((c) => c.idx === chapterIdx);
    const within = cur && cur.n ? (paraIdx / cur.n) * cur.chars : 0;
    return Math.min(1, (before + within) / total);
  }

  /* ---- search (MiniSearch, index cached in IndexedDB per content version) ---- */
  let searchP = null;
  const SEARCH_OPTS = { fields: ['t'], storeFields: ['b', 'c', 'i'], idField: 'u',
    searchOptions: { prefix: true, fuzzy: 0.15, combineWith: 'AND' } };

  function searchIndex(onProgress) {
    if (searchP) return searchP;
    searchP = (async () => {
      const cacheKey = 'cache:search:' + index.version;
      const cached = await Store.getKV(cacheKey);
      if (cached) return MiniSearch.loadJSON(cached, SEARCH_OPTS);
      const ms = new MiniSearch(SEARCH_OPTS);
      const jobs = index.books.flatMap((b) => b.chapters.map((c) => [b, c]));
      let done = 0;
      for (const [b, c] of jobs) {
        const paras = await chapter(b.uid, c.idx);
        ms.addAll(paras.filter((p) => !p.h).map((p, i) => ({ u: p.u, t: p.t, b: b.uid, c: c.idx, i })));
        if (onProgress) onProgress(++done / jobs.length);
      }
      try { await Store.setKV(cacheKey, JSON.stringify(ms), true); } catch (e) { /* cache is optional */ }
      return ms;
    })();
    return searchP;
  }

  /* ---- topics across books (www/content/topics.json, built by tools/build_topics.py) ---- */
  let topicsP = null;
  function topics() {
    if (!topicsP) topicsP = fetch('content/topics.json').then((r) => (r.ok ? r.json() : [])).catch(() => []);
    return topicsP;
  }

  async function search(query, limit = 40) {
    const ms = await searchIndex();
    return ms.search(query).slice(0, limit);
  }

  /* ---- highlight re-anchoring after a content update ---- */
  // Try to find the highlight's quote at its stored position; failing that, in the same
  // paragraph, then anywhere in the book. Returns the (possibly moved) highlight, or null.
  async function reanchor(h) {
    const b = book(h.bookUid);
    if (!b) return null;
    const fits = (t) => t.slice(h.start, h.end) === h.quote;
    try {
      const paras = await chapter(h.bookUid, h.chapterIdx);
      const p = paras.find((x) => x.u === h.paraUid);
      if (p && fits(p.t)) return h;
      if (p && p.t.includes(h.quote)) {
        const s = p.t.indexOf(h.quote);
        return { ...h, start: s, end: s + h.quote.length };
      }
    } catch (e) { /* chapter gone; search the book */ }
    for (const c of b.chapters) {
      const paras = await chapter(h.bookUid, c.idx);
      for (const p of paras) {
        const s = p.t.indexOf(h.quote);
        if (s >= 0) return { ...h, chapterIdx: c.idx, paraUid: p.u, start: s, end: s + h.quote.length };
      }
    }
    return null;
  }

  // Find a paragraph whose text starts with `snip`; nearest chapter to `hint` wins. -> {chapterIdx, paraUid} | null
  async function locate(bookUid, snip, hint = 0) {
    const b = book(bookUid);
    if (!b || !snip) return null;
    const order = [...b.chapters].sort((x, y) => Math.abs(x.idx - hint) - Math.abs(y.idx - hint));
    for (const c of order) {
      const p = (await chapter(bookUid, c.idx)).find((x) => x.t.startsWith(snip));
      if (p) return { chapterIdx: c.idx, paraUid: p.u };
    }
    return null;
  }

  async function stillThere(bookUid, chapterIdx, paraUid, snip) {
    try {
      const p = (await chapter(bookUid, chapterIdx)).find((x) => x.u === paraUid);
      return !!p && p.t.startsWith(snip);
    } catch (e) { return false; }
  }

  // Run once whenever the bundled content version changes (new APK with more/updated books).
  async function reconcile() {
    const last = await Store.getKV('contentVersion');
    if (last === index.version) return null;
    const hs = await Store.all('highlights');
    let moved = 0, orphaned = 0;
    for (const h of hs) {
      if (!index.byUid.has(h.bookUid)) continue; // book not in this build: leave untouched
      const r = await reanchor(h);
      if (!r) { if (!h.orphan) { await Store.put('highlights', { ...h, orphan: true, updated: Date.now() }); orphaned++; } continue; }
      const changed = r.paraUid !== h.paraUid || r.start !== h.start || r.chapterIdx !== h.chapterIdx || h.orphan;
      if (changed) { await Store.put('highlights', { ...r, orphan: false, updated: Date.now() }); moved++; }
    }
    // bookmarks and reading positions: follow their text to wherever it lives now
    for (const bm of await Store.all('bookmarks')) {
      if (!index.byUid.has(bm.bookUid) || await stillThere(bm.bookUid, bm.chapterIdx, bm.paraUid, bm.label)) continue;
      const at = await locate(bm.bookUid, bm.label, bm.chapterIdx);
      if (at) { await Store.put('bookmarks', { ...bm, ...at, updated: Date.now() }); moved++; }
    }
    for (const b of index.books) {
      const pr = await Store.getKV('progress:' + b.uid);
      if (!pr || !pr.snip || await stillThere(b.uid, pr.chapterIdx, pr.paraUid, pr.snip)) continue;
      const at = await locate(b.uid, pr.snip, pr.chapterIdx);
      if (at) {
        const i = (await chapter(b.uid, at.chapterIdx)).findIndex((x) => x.u === at.paraUid);
        await Store.setKV('progress:' + b.uid, { ...pr, ...at, frac: bookFraction(b, at.chapterIdx, i) }, true);
      } else await Store.setKV('progress:' + b.uid, { ...pr, chapterIdx: 0, paraUid: null, frac: 0 }, true);
    }
    await Store.setKV('contentVersion', index.version, true);
    return { moved, orphaned };
  }

  return { loadIndex, book, chapter, bookFraction, topics, search, searchIndex, reanchor, reconcile,
    get index() { return index; } };
})();
