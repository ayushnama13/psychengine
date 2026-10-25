/* PsychEngine Reader — views, reader, highlights, review. No framework, no build step. */
const $ = (s, r = document) => r.querySelector(s);
const view = $('#view');
const COLORS = ['y', 'v', 'b', 'p']; // 'g' (green) still renders for highlights made before v2
const DEFAULTS = { theme: null, size: 19, lh: 1.7, font: 'serif', width: 34, goal: 20 };
const CPM = 1100; // characters read per minute (~200 wpm)
let settings = { ...DEFAULTS };
let cur = null; // reader state

/* ---------- helpers ---------- */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
const PATHS = {
  back: '<path d="M15 18l-6-6 6-6"/>', next: '<path d="M9 18l6-6-6-6"/>', down: '<path d="M6 9l6 6 6-6"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>', check: '<path d="M5 12l5 5 9-10"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>', play: '<path d="M8 5v14l11-7z"/>',
  bookmark: '<path d="M6 3h12v18l-6-4-6 4z"/>', note: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  card: '<rect x="3" y="6" width="14" height="14" rx="2"/><path d="M7 3h12a2 2 0 0 1 2 2v12"/>',
  export: '<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M5 21h14"/>',
  flame: '<path d="M12 2c1 4 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-6 1-9z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
};
const ic = (name) => { const t = document.createElement('template'); t.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${PATHS[name]}</svg>`; return t.content.firstChild; };
const shortTitle = (t) => t.replace(/\s*\(.*$/, '').replace(/^The-48/, 'The 48').replace(/-/g, ' ').replace(/ Robert Greene$/, '').trim();
const splitBook = (b) => { const s = shortTitle(b.title), m = s.match(/^(.+?)\s+(The\s.+)$/); return m ? { main: m[1], sub: m[2] } : { main: s, sub: '' }; };
const chipName = (b) => splitBook(b).main.replace(/^The /, '');
const mins = (chars) => Math.max(1, Math.round(chars / CPM));
const fmtDur = (m) => (m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`);
const pctOf = (prog) => Math.round(100 * (prog ? prog.frac : 0));
function ago(ts) {
  const d = (Date.now() - ts) / 1000;
  if (d < 3600) return Math.max(1, Math.round(d / 60)) + ' min ago';
  if (d < 86400) return Math.round(d / 3600) + 'h ago';
  const days = Math.round(d / 86400);
  return days === 1 ? 'yesterday' : days < 7 ? days + ' days ago' : days < 30 ? Math.round(days / 7) + (days < 14 ? ' week ago' : ' weeks ago') : new Date(ts).toLocaleDateString();
}

let toastT;
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(() => (t.hidden = true), 2200);
}

/* ---------- chapters grouped from parts ---------- */
// Parts are titled "Parent (2/5)" or "Parent · Sub heading"; consecutive parts with the same parent form one chapter.
const titleFix = (s) => (s === s.toUpperCase() && /[A-Z]{3}/.test(s) ? s.toLowerCase().replace(/(^|[\s"'—–-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase()) : s);
const sameGroup = (a, b) => {
  a = a.toLowerCase(); b = b.toLowerCase();
  const [s, l] = a.length <= b.length ? [a, b] : [b, a];
  return l.startsWith(s) && !/[\p{L}\d]/u.test(l[s.length] || '');
};
const FRONT = /^(front matter|preface|introduction|foreword|acknowledg|contents|notes|index|bibliograph|about the author)/i;
function groups(b) {
  if (b._groups) return b._groups;
  const gs = [];
  for (const c of b.chapters) {
    const i = c.title.indexOf(' · ');
    const parent = titleFix((i >= 0 ? c.title.slice(0, i) : c.title).replace(/\s*\(\d+\/\d+\)\s*$/, '').trim());
    let g = gs[gs.length - 1];
    if (!g || !sameGroup(g.title, parent)) gs.push((g = { title: parent, parts: [] }));
    else if (parent.length > g.title.length) g.title = parent;
    c._sub = i >= 0 ? c.title.slice(i + 3) : '';
    c._g = g; c._pi = g.parts.length; g.parts.push(c);
  }
  let n = 0;
  for (const g of gs) { g.front = FRONT.test(g.title); g.num = g.front ? null : ++n; g.chars = g.parts.reduce((s, c) => s + c.chars, 0); }
  return (b._groups = gs);
}
const partOf = (b, idx) => { groups(b); return b.chapters.find((c) => c.idx === idx); };
const partName = (c) => c._sub || (c._g.parts.length > 1 ? `Part ${c._pi + 1}` : c._g.title);
const partLine = (c) => (c._g.parts.length > 1 ? `Part ${c._pi + 1} of ${c._g.parts.length}` : '');

/* ---------- what has actually been read ---------- */
// reads:<uid> = { <part idx>: { sec, max, p } }: active seconds spent in the part, furthest point reached
// (0..1 of its paragraphs) and the last paragraph seen. Opening a part only to look never counts.
const READ_AT = 0.9, READ_SHARE = 0.4, SPOT_SEC = 20;
const partCredit = (c, e) => {
  if (!e) return 0;
  const t = Math.min(1, e.sec / Math.max(20, mins(c.chars) * 60 * READ_SHARE));
  return e.max >= READ_AT && t >= 1 ? 1 : Math.min(0.99, e.max, t);
};
const bookFrac = (b, reads) => {
  const total = b.chapters.reduce((s, c) => s + c.chars, 0) || 1;
  return b.chapters.reduce((s, c) => s + c.chars * partCredit(c, reads[c.idx]), 0) / total;
};
async function getReads(b) {
  const saved = await Store.getKV('reads:' + b.uid);
  if (saved) return saved;
  // first run after the update: everything before the old position counts as read
  const reads = {}, prog = await Store.getKV('progress:' + b.uid);
  if (prog && prog.chapterIdx != null) {
    const total = b.chapters.reduce((s, c) => s + c.chars, 0) || 1;
    let before = 0;
    for (const c of b.chapters) {
      const need = Math.max(20, mins(c.chars) * 60 * READ_SHARE);
      if (c.idx < prog.chapterIdx) reads[c.idx] = { sec: need, max: 1, p: null };
      else if (c.idx === prog.chapterIdx) {
        const w = Math.min(1, Math.max(0, ((prog.frac || 0) * total - before) / (c.chars || 1)));
        reads[c.idx] = { sec: w * need, max: w, p: prog.paraUid };
      }
      before += c.chars;
    }
  }
  await Store.setKV('reads:' + b.uid, reads, true);
  return reads;
}

/* ---------- covers ---------- */
const COVER_BG = ['#23286a', '#17121f', '#3a1d45', '#14342f', '#3b2416', '#1f2a44'];
function cover(b, size) {
  const i = Content.index.books.indexOf(b), { main } = splitBook(b);
  const au = (b.author || '').split(/\s+/).pop();
  const num = main.match(/\d+/);
  const plain = Content.index.books.slice(0, i).filter((x) => !/\d/.test(splitBook(x).main)).length;
  const style = `background:${COVER_BG[i % COVER_BG.length]}`;
  if (num) return h('div', { class: `cover ${size} v-num`, style }, h('span', { class: 'big' }, num[0]), h('span', { class: 'au' }, au));
  if (plain % 2) return h('div', { class: `cover ${size} v-it`, style }, h('span', { class: 'ti' }, main), h('span', { class: 'au' }, au));
  return h('div', { class: `cover ${size}`, style }, h('span', { class: 'au' }, au), h('span', { class: 'ti' }, main), h('i', { class: 'rule' }));
}

/* ---------- reading time per day (for streak and daily goal) ---------- */
const dayKey = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
let lastAct = 0;
['scroll', 'touchstart', 'pointerdown', 'keydown'].forEach((e) => addEventListener(e, () => (lastAct = Date.now()), { passive: true }));
setInterval(async () => {
  if (!cur || document.hidden || Date.now() - lastAct > 120e3) return;
  const a = await Store.getKV('activity', {}), k = dayKey();
  a[k] = (a[k] || 0) + 15;
  await Store.setKV('activity', a, true);
  if (cur) { cur.reads[cur.ci].sec += 15; cur.visitSec += 15; saveProgress(); }
}, 15e3);
async function readingStats() {
  const a = await Store.getKV('activity', {});
  const minsOn = (d) => Math.floor((a[dayKey(d)] || 0) / 60);
  const d = new Date();
  let streak = 0;
  if (minsOn(d) < 1) d.setDate(d.getDate() - 1); // today not started yet: the streak is still alive
  while (minsOn(d) >= 1) { streak++; d.setDate(d.getDate() - 1); }
  const week = [];
  for (let i = 6; i >= 0; i--) { const x = new Date(); x.setDate(x.getDate() - i); week.push({ d: x, m: minsOn(x) }); }
  const total = Math.floor(Object.values(a).reduce((s, x) => s + x, 0) / 60);
  return { today: minsOn(new Date()), streak, week, total };
}

function applySettings() {
  const r = document.documentElement;
  const theme = settings.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  r.dataset.theme = theme;
  r.style.setProperty('--fs', settings.size + 'px');
  r.style.setProperty('--lh', settings.lh);
  r.style.setProperty('--measure', settings.width + 'rem');
  document.body.classList.toggle('sans', settings.font === 'sans');
  const meta = $('meta[name=theme-color]');
  if (meta) meta.content = getComputedStyle(r).getPropertyValue('--bg').trim();
}
async function saveSettings() { applySettings(); await Store.setKV('settings', settings); }

/* ---------- sheets (back button closes them) ---------- */
let sheetEl = null;
function openSheet(...kids) {
  closeSheet(true);
  sheetEl = h('div', { class: 'backdrop', onclick: (e) => { if (e.target === sheetEl) history.back(); } }, h('div', { class: 'sheet' }, kids));
  $('#sheetRoot').append(sheetEl);
  history.pushState({ sheet: 1 }, '');
}
function closeSheet(silent) {
  if (!sheetEl) return;
  sheetEl.remove(); sheetEl = null;
  if (!silent && history.state && history.state.sheet) history.back();
}
window.addEventListener('popstate', () => { if (sheetEl) { sheetEl.remove(); sheetEl = null; } });
// close a sheet programmatically after an action
const done = () => { if (sheetEl) history.back(); };

/* ---------- router ---------- */
const routes = [];
const route = (re, fn, tab) => routes.push({ re, fn, tab });
// renders run one at a time so quick navigation can't interleave two views
let renderQ = Promise.resolve();
const render = () => (renderQ = renderQ.catch(() => {}).then(doRender));
async function doRender() {
  hideSelBar();
  const hash = location.hash.slice(1) || '/';
  const [path, qs] = hash.split('?');
  const q = new URLSearchParams(qs || '');
  for (const r of routes) {
    const m = path.match(r.re);
    if (!m) continue;
    document.body.classList.toggle('reading', r.tab === 'reader');
    document.body.classList.remove('focus');
    document.querySelectorAll('#tabs a').forEach((a) => a.classList.toggle('on', a.dataset.tab === r.tab));
    view.replaceChildren();
    cur = null;
    window.scrollTo(0, 0);
    try { await r.fn(m, q); } catch (e) { view.replaceChildren(h('div', { class: 'page' }, h('h1', {}, 'Something broke'), h('pre', { class: 'dim small' }, String(e && e.stack || e)))); }
    refreshBadge();
    return;
  }
  location.hash = '#/';
}
window.addEventListener('hashchange', () => { if (!sheetEl) render(); });

async function refreshBadge() {
  const n = (await dueCards()).length, b = $('#dueBadge');
  b.hidden = !n; b.textContent = n;
}

/* ---------- Library ---------- */
route(/^\/$/, async () => {
  const idx = Content.index;
  const [last, st, due, hls] = await Promise.all([Store.getKV('lastRead'), readingStats(), dueCards(), Store.all('highlights')]);
  const page = h('div', { class: 'page' },
    h('div', { class: 'lhead' },
      h('div', {}, h('span', { class: 'eyebrow' }, new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'short' })), h('h1', {}, 'Library')),
      h('a', { class: 'iconbtn round', href: '#/search', 'aria-label': 'Search', style: 'display:flex;align-items:center;justify-content:center;color:var(--fg)' }, ic('search'))));

  if (last && Content.book(last.bookUid)) {
    const b = Content.book(last.bookUid);
    const prog = await Store.getKV('progress:' + b.uid);
    const c = partOf(b, prog ? prog.chapterIdx : 0) || b.chapters[0];
    let left = c.chars;
    if (prog && prog.paraUid && prog.chapterIdx === c.idx) {
      const paras = await Content.chapter(b.uid, c.idx), i = paras.findIndex((p) => p.u === prog.paraUid);
      if (i >= 0) left = paras.slice(i).reduce((s, p) => s + p.t.length, 0);
    }
    page.append(h('a', { class: 'cont', href: `#/read/${b.uid}/${c.idx}` },
      cover(b, 'sm'),
      h('div', { style: 'min-width:0' },
        h('span', { class: 'lbl' }, 'CONTINUE READING'),
        h('div', { class: 'ti ell' }, c._g.title),
        h('div', { class: 'dim small ell' }, [partLine(c), `${mins(left)} min left`].filter(Boolean).join(' · ')),
        h('div', { class: 'row', style: 'gap:8px;margin-top:10px' }, h('div', { class: 'bar grow', style: 'margin:0' }, h('div', { style: `width:${pctOf(prog)}%` })), h('span', { class: 'dim small' }, pctOf(prog) + '%'))),
      h('span', { class: 'play' }, ic('play'))));
  }

  page.append(h('div', { class: 'stats' },
    h('a', { class: 'stat hot', href: '#/you' }, ic('flame'), h('b', {}, st.streak), h('span', {}, st.streak === 1 ? 'day streak' : 'day streak')),
    h('a', { class: 'stat', href: '#/you' }, ic('clock'), h('b', {}, st.today, h('small', {}, `/${settings.goal}m`)), h('span', {}, 'today')),
    h('a', { class: 'stat vio', href: '#/review' }, ic('card'), h('b', {}, due.length), h('span', {}, 'cards due'))));

  page.append(h('div', { class: 'sec' }, h('h2', {}, 'Your shelf'), h('span', { class: 'dim' }, `${idx.books.length} books`)));
  const shelf = h('div', { class: 'shelf' });
  for (const b of idx.books) {
    const prog = await Store.getKV('progress:' + b.uid);
    shelf.append(h('a', { href: `#/book/${b.uid}` }, cover(b, 'md'), h('span', { class: 't' }, splitBook(b).main),
      prog && prog.frac > 0 ? h('div', { class: 'bar' }, h('div', { style: `width:${Math.max(2, pctOf(prog))}%` })) : h('span', { class: 'dim small', style: 'font-size:.72rem' }, 'Not started')));
  }
  page.append(shelf);

  const tops = await Content.topics();
  if (tops.length) {
    page.append(h('div', { class: 'sec' }, h('h2', {}, 'Topics'), h('a', { href: '#/topics', class: 'small' }, 'All topics')),
      h('div', { class: 'tchips' }, ...tops.slice(0, 6).map((t) => h('a', { href: `#/topic/${t.id}` }, t.name, h('small', {}, t.n)))));
  }

  const pool =hls.filter((x) => !x.orphan && Content.book(x.bookUid));
  if (pool.length) {
    const x = pool[Math.floor(Date.now() / 864e5) % pool.length]; // a different note each day
    const b = Content.book(x.bookUid), c = partOf(b, x.chapterIdx);
    page.append(h('div', { class: 'sec' }, h('h2', {}, 'From your notes'), h('a', { href: '#/notes', class: 'small' }, 'All notes')),
      h('a', { class: 'quote', href: `#/read/${x.bookUid}/${x.chapterIdx}?p=${x.paraUid}` },
        h('p', {}, '“' + x.quote + '”'), x.note ? h('p', { class: 'note' }, x.note) : null,
        h('div', { class: 'dim small', style: 'margin-top:10px' }, `${splitBook(b).main}${c ? ' · ' + c._g.title : ''}`)));
  }
  view.append(page);
}, 'home');

/* ---------- Topics: one idea, passages from every book ---------- */
const bookCounts = (t) => Content.index.books.filter((b) => t.books[b.uid]).map((b) => `${chipName(b)} ${t.books[b.uid]}`).join(' · ');
const backBtn = (href, label) => h('a', { class: 'iconbtn', href, 'aria-label': label, style: 'display:flex;align-items:center;justify-content:center;color:var(--fg);margin-left:-12px' }, ic('back'));

route(/^\/topics$/, async () => {
  const tops = await Content.topics();
  view.append(h('div', { class: 'page' },
    h('div', { class: 'row', style: 'padding-top:12px' }, backBtn('#/', 'Back to library'), h('h1', {}, 'Topics')),
    h('div', { class: 'dim small', style: 'margin-top:6px' }, `${tops.length} topics across ${Content.index.books.length} books`),
    h('div', { class: 'tlist' }, ...tops.map((t) => h('a', { href: `#/topic/${t.id}` },
      h('div', { style: 'min-width:0' }, h('b', {}, t.name), h('span', {}, t.desc), h('span', { class: 'cnt' }, `${t.n} passages · ${bookCounts(t)}`)),
      ic('next'))))));
}, 'home');

route(/^\/topic\/([\w-]+)$/, async (m) => {
  const t = (await Content.topics()).find((x) => x.id === m[1]);
  if (!t) { location.hash = '#/topics'; return; } // e.g. a topic dropped from a newer build
  const nb = Object.keys(t.books).length;
  const page = h('div', { class: 'page' },
    h('div', { style: 'padding-top:12px' }, backBtn('#/topics', 'All topics')),
    h('span', { class: 'eyebrow' }, `Topic · ${nb} book${nb === 1 ? '' : 's'}`), h('h1', {}, t.name),
    h('p', { class: 'tdesc' }, t.desc),
    h('div', { class: 'dim small' }, `${t.n} passages · ${bookCounts(t)}`));
  let lastKey = null;
  for (const x of t.hits) {
    const b = Content.book(x.b), c = b && partOf(b, x.c);
    if (!c) continue;
    const key = x.b + '/' + c._g.title;
    if (key !== lastKey) { page.append(h('span', { class: 'glabel' }, `${splitBook(b).main} · ${c._g.title}`)); lastKey = key; }
    page.append(h('a', { class: 'tpass', href: `#/read/${x.b}/${x.c}?p=${x.u}` }, h('p', {}, '“' + x.s + '”'),
      h('div', { class: 'w' }, h('span', {}, partLine(c)), h('span', {}, 'Open ›'))));
  }
  view.append(page);
}, 'home');

/* ---------- Book (chapters grouped, parts inside) ---------- */
route(/^\/book\/([\w-]+)$/, async (m, q) => {
  const b = Content.book(m[1]);
  if (!b) throw new Error('Unknown book');
  const gs = groups(b);
  const prog = await Store.getKV('progress:' + b.uid);
  const reads = await getReads(b), frac = bookFrac(b, reads);
  const curC = prog ? partOf(b, prog.chapterIdx) : null;
  const hlN = (await Store.byBook('highlights', b.uid)).filter((x) => !x.orphan).length;
  const total = b.chapters.reduce((s, c) => s + c.chars, 0);
  const { main, sub } = splitBook(b);
  const first = curC || b.chapters.find((c) => !c._g.front) || b.chapters[0];
  const bookDue = (await dueCards()).filter((c) => c.bookUid === b.uid).length, warmN = Math.min(5, bookDue);
  const warm = bookDue ? h('a', { class: 'warm', href: `#/review?b=${b.uid}&n=5&then=${encodeURIComponent(`/read/${b.uid}/${first.idx}`)}` },
    ic('flame'), h('div', { class: 'grow' }, h('b', {}, `Warm up: ${warmN} card${warmN === 1 ? '' : 's'}`), h('span', {}, bookDue > warmN ? `${bookDue} due from this book` : 'due from this book')),
    h('span', { class: 'pillbtn' }, 'Start')) : null;
  view.append(h('div', { class: 'bhead' },
    h('a', { class: 'iconbtn', href: '#/', 'aria-label': 'Back to library', style: 'display:flex;align-items:center;justify-content:center' }, ic('back')),
    h('div', { class: 'top' }, cover(b, 'lg'), h('div', { style: 'min-width:0' }, h('h1', {}, main), sub ? h('div', { class: 'sub' }, sub) : null, h('div', { class: 'sub' }, b.author || ''))),
    h('div', { class: 'bstats' },
      h('div', {}, h('b', {}, Math.round(100 * frac) + '%'), h('span', {}, 'read')),
      h('div', {}, h('b', {}, fmtDur(mins(total * (1 - frac)))), h('span', {}, 'left')),
      h('div', {}, h('b', {}, hlN), h('span', {}, hlN === 1 ? 'highlight' : 'highlights'))),
    warm,
    h('button', { class: 'go', onclick: () => (location.hash = `#/read/${b.uid}/${first.idx}`) }, ic('play'), curC ? 'Continue · ' + partName(curC) : 'Start reading')));

  const page = h('div', { class: 'page', style: 'padding-top:4px' },
    h('div', { class: 'sec', style: 'margin-top:20px' }, h('h2', {}, 'Chapters'), h('span', { class: 'dim' }, `${gs.filter((g) => !g.front).length} chapters · ${b.chapters.length} parts`)));
  const open = new Set(q.get('g') ? [+q.get('g')] : curC ? [gs.indexOf(curC._g)] : []);
  gs.forEach((g, gi) => {
    const isCur = curC && curC._g === g;
    const fin = g.parts.every((c) => partCredit(c, reads[c.idx]) === 1);
    const gc = g.parts.reduce((s, c) => s + c.chars * partCredit(c, reads[c.idx]), 0) / (g.chars || 1);
    const single = g.parts.length === 1;
    const lead = single ? '' : g.parts.length + ' parts · ';
    const status = fin ? `${lead}finished` : isCur ? `Reading${single ? '' : ' · ' + partLine(curC).toLowerCase()}` : gc >= 0.01 ? `${lead}${Math.round(100 * gc)}% read` : `${lead}${fmtDur(mins(g.chars))}`;
    const numEl = h('span', { class: 'num' }, fin ? ic('check') : g.num != null ? String(g.num) : '·');
    const head = h(single ? 'a' : 'button', { class: 'gh', href: single ? `#/read/${b.uid}/${g.parts[0].idx}` : null },
      numEl, h('div', { style: 'min-width:0' }, h('span', { class: 'nm' }, g.title), h('span', { class: 'st' }, status)), ic(single || !open.has(gi) ? 'next' : 'down'));
    const box = h('div', { class: 'grp' + (fin ? ' fin' : isCur ? ' cur' : '') }, head);
    if (!single) {
      const list = h('div', { class: 'parts', hidden: !open.has(gi) },
        ...g.parts.map((c) => h('a', { href: `#/read/${b.uid}/${c.idx}`, class: partCredit(c, reads[c.idx]) === 1 ? 'done' : curC && c === curC ? 'on' : '' }, partName(c), h('span', {}, mins(c.chars) + ' min'))));
      box.append(list);
      head.addEventListener('click', () => { list.hidden = !list.hidden; head.lastChild.replaceWith(ic(list.hidden ? 'next' : 'down')); });
    }
    page.append(box);
  });
  view.append(page);
}, 'home');

/* ---------- Reader ---------- */
function renderPara(el, text, hls) {
  el.replaceChildren();
  if (!hls.length) { el.textContent = text; return; }
  const cuts = new Set([0, text.length]);
  hls.forEach((x) => { cuts.add(x.start); cuts.add(Math.min(x.end, text.length)); });
  const pts = [...cuts].sort((a, b) => a - b);
  for (let i = 0; i < pts.length - 1; i++) {
    const [a, b] = [pts[i], pts[i + 1]];
    if (a === b) continue;
    const top = hls.filter((x) => x.start <= a && x.end >= b).sort((p, q) => p.created - q.created).pop();
    const s = text.slice(a, b);
    el.append(top ? h('mark', { 'data-id': top.id, 'data-c': top.color, class: top.note ? 'hasnote' : '' }, s) : s);
  }
}

route(/^\/read\/([\w-]+)\/(\d+)$/, async (m, q) => {
  const b = Content.book(m[1]), ci = +m[2];
  const chap = b && partOf(b, ci);
  if (!chap) throw new Error('Chapter not found');
  const paras = await Content.chapter(b.uid, ci);
  const allHl = (await Store.byBook('highlights', b.uid)).filter((x) => x.chapterIdx === ci && !x.orphan);
  const bms = (await Store.byBook('bookmarks', b.uid)).filter((x) => x.chapterIdx === ci);
  cur = { b, ci, chap, paras, hls: allHl, bms, pending: null, reads: await getReads(b), visitSec: 0 };
  cur.reads[ci] = cur.reads[ci] || { sec: 0, max: 0, p: null };
  // characters from each paragraph to the end of the part, for "min left"
  let acc = 0; cur.tail = paras.map((p) => p.t.length).reverse().map((n) => (acc += n)).reverse();

  const g = chap._g;
  const text = h('article', { id: 'text' },
    h('span', { class: 'eyebrow' }, g.num != null ? `Chapter ${g.num}` : g.title),
    h('h1', {}, chap._sub || g.title));
  const els = new Map();
  for (const p of paras) {
    const el = h('p', { 'data-u': p.u, class: p.h ? 'h' : '' });
    renderPara(el, p.t, allHl.filter((x) => x.paraUid === p.u));
    els.set(p.u, el); text.append(el);
  }
  cur.els = els;
  const prev = b.chapters.find((c) => c.idx === ci - 1), next = b.chapters.find((c) => c.idx === ci + 1);
  text.append(next
    ? h('a', { class: 'next', href: `#/read/${b.uid}/${next.idx}` }, h('div', {}, h('small', {}, next._g === g ? 'Next part' : 'Next chapter'), next._sub || next._g.title), ic('next'))
    : h('div', { class: 'next' }, h('div', {}, h('small', {}, 'Finished'), 'End of book'), ic('check')));

  cur.bmBtn = h('button', { class: 'iconbtn bm', 'aria-label': 'Bookmark', onclick: toggleBookmark }, ic('bookmark'));
  cur.pct = h('div', { class: 'prog' }, '');
  cur.line = h('div', {});
  view.append(
    h('div', { id: 'rhead' },
      h('div', { class: 'g' },
        h('button', { class: 'iconbtn', onclick: () => (location.hash = `#/book/${b.uid}`), 'aria-label': 'Chapters' }, ic('back')),
        h('div', { class: 't' }, h('b', { class: 'ell' }, g.title), h('span', { class: 'ell' }, [splitBook(b).main, partLine(chap)].filter(Boolean).join(' · '))),
        cur.bmBtn,
        h('button', { class: 'iconbtn aa', onclick: openAppearance, 'aria-label': 'Appearance' }, 'Aa')),
      h('div', { id: 'rline' }, cur.line)),
    text,
    h('div', { id: 'rfoot' },
      h('button', { class: 'iconbtn', 'aria-label': 'Previous part', disabled: !prev, onclick: () => (location.hash = `#/read/${b.uid}/${ci - 1}`) }, ic('back')),
      cur.pct,
      h('button', { class: 'iconbtn', 'aria-label': 'Next part', disabled: !next, onclick: () => (location.hash = `#/read/${b.uid}/${ci + 1}`) }, ic('next'))));

  text.addEventListener('click', (e) => {
    const mk = e.target.closest('mark[data-id]');
    if (mk && getSelection().isCollapsed) editHighlight(mk.dataset.id);
  });

  // where to start: explicit target > saved position in this part > top
  let target = q.get('p') || cur.reads[ci].p;
  if (target && els.has(target)) {
    await new Promise((r) => requestAnimationFrame(r));
    els.get(target).scrollIntoView({ block: 'start' });
    window.scrollBy(0, -(($('#rhead').offsetHeight) + 6));
    if (q.get('p')) { els.get(target).classList.add('flash'); }
  }
  lastAct = Date.now();
  trackScroll();
}, 'reader');

let scrollT;
function trackScroll() {
  const onScroll = () => { clearTimeout(scrollT); scrollT = setTimeout(saveProgress, 350); updateTop(); };
  window.removeEventListener('scroll', window._rs);
  window._rs = onScroll;
  window.addEventListener('scroll', onScroll, { passive: true });
  updateTop();
}
function topPara() {
  if (!cur) return null;
  const limit = ($('#rhead') ? $('#rhead').offsetHeight : 48) + 8;
  for (const p of cur.paras) {
    const el = cur.els.get(p.u);
    if (el.getBoundingClientRect().bottom > limit) return p;
  }
  return cur.paras[cur.paras.length - 1];
}
// furthest paragraph on screen: how far into the part the reader has got
function botPara() {
  for (let i = cur.paras.length - 1; i >= 0; i--) if (cur.els.get(cur.paras[i].u).getBoundingClientRect().top < innerHeight) return i;
  return 0;
}
function updateTop() {
  if (!cur) return;
  const p = topPara(); if (!p) return;
  const i = cur.paras.indexOf(p), e = cur.reads[cur.ci];
  e.p = p.u; e.max = Math.max(e.max, (botPara() + 1) / cur.paras.length);
  const frac = bookFrac(cur.b, cur.reads);
  cur.pct.textContent = `${mins(cur.tail[i] || 0)} min left in part · ${Math.round(100 * frac)}% of book read`;
  cur.line.style.width = (100 * frac).toFixed(1) + '%';
  cur.bmBtn.classList.toggle('on', cur.bms.some((x) => x.paraUid === p.u));
}
async function saveProgress() {
  if (!cur) return;
  const p = topPara(); if (!p) return;
  updateTop();
  const uid = cur.b.uid, frac = bookFrac(cur.b, cur.reads);
  await Store.setKV('reads:' + uid, cur.reads, true);
  const prog = (await Store.getKV('progress:' + uid)) || {};
  // "continue" only moves once this part has really been read for a bit
  if (cur.visitSec >= SPOT_SEC) {
    Object.assign(prog, { chapterIdx: cur.ci, paraUid: p.u, snip: p.t.slice(0, 80), ts: Date.now() });
    await Store.setKV('lastRead', { bookUid: uid, ts: Date.now() }, true);
  }
  await Store.setKV('progress:' + uid, { ...prog, frac }, true);
}
window.addEventListener('pagehide', saveProgress);
document.addEventListener('visibilitychange', () => { if (document.hidden) saveProgress(); });

async function toggleBookmark() {
  const p = topPara(); if (!p) return;
  const have = cur.bms.find((x) => x.paraUid === p.u);
  if (have) { await Store.del('bookmarks', have.id); cur.bms = cur.bms.filter((x) => x !== have); toast('Bookmark removed'); }
  else {
    const bm = { id: Store.uid(), bookUid: cur.b.uid, chapterIdx: cur.ci, paraUid: p.u, label: p.t.slice(0, 120), created: Date.now(), updated: Date.now() };
    await Store.put('bookmarks', bm); cur.bms.push(bm); toast('Bookmarked');
  }
  updateTop();
}

function openAppearance() {
  const opt = (key, val, label) => h('button', { class: settings[key] === val ? 'on' : '', onclick: async (e) => {
    settings[key] = val; await saveSettings(); e.target.parentNode.querySelectorAll('button').forEach((b) => b.classList.remove('on')); e.target.classList.add('on'); } }, label);
  const range = (key, min, max, step) => h('input', { type: 'range', min, max, step, value: settings[key], style: 'width:100%',
    oninput: (e) => { settings[key] = +e.target.value; applySettings(); }, onchange: saveSettings });
  openSheet(h('h3', {}, 'Appearance'),
    h('label', {}, 'Theme'), h('div', { class: 'opts' }, opt('theme', 'dark', 'Midnight'), opt('theme', 'light', 'Daylight'), opt('theme', 'sepia', 'Sepia')),
    h('label', {}, 'Font'), h('div', { class: 'opts' }, opt('font', 'serif', 'Serif'), opt('font', 'sans', 'Sans')),
    h('label', {}, 'Text size'), range('size', 14, 30, 1),
    h('label', {}, 'Line spacing'), range('lh', 1.3, 2.1, 0.05),
    h('label', {}, 'Line width'), range('width', 24, 44, 1));
}

/* ---------- selection → highlight ---------- */
function paraOf(node) {
  const el = node.nodeType === 1 ? node : node.parentElement;
  return el && el.closest ? el.closest('#text p[data-u]') : null;
}
function readSelection() {
  if (!cur) return null;
  const sel = getSelection();
  if (!sel.rangeCount || sel.isCollapsed) return null;
  const r = sel.getRangeAt(0);
  const pe = paraOf(r.startContainer);
  if (!pe) return null;
  const p = cur.paras.find((x) => x.u === pe.dataset.u);
  const pre = document.createRange();
  pre.selectNodeContents(pe); pre.setEnd(r.startContainer, r.startOffset);
  let start = pre.toString().length, end;
  if (paraOf(r.endContainer) === pe) { const e2 = document.createRange(); e2.selectNodeContents(pe); e2.setEnd(r.endContainer, r.endOffset); end = e2.toString().length; }
  else end = p.t.length;
  const raw = p.t.slice(start, end);
  start += raw.length - raw.trimStart().length; end -= raw.length - raw.trimEnd().length;
  if (end - start < 2) return null;
  return { paraUid: p.u, start, end, quote: p.t.slice(start, end), prefix: p.t.slice(Math.max(0, start - 30), start), suffix: p.t.slice(end, end + 30) };
}
function hideSelBar() { const s = $('#selbar'); s.hidden = true; if (cur) cur.pending = null; }
document.addEventListener('selectionchange', () => {
  if (!cur || sheetEl) return;
  const s = readSelection();
  if (!s) { $('#selbar').hidden = true; return; }
  cur.pending = s;
  const keep = (e) => e.preventDefault();
  const bar = $('#selbar'); bar.replaceChildren(
    ...COLORS.map((c) => h('button', { class: 'dot', 'data-c': c, 'aria-label': 'Highlight', onpointerdown: keep, onclick: () => createHighlight(c) }, h('i'))),
    h('span', { class: 'sep' }),
    h('button', { class: 'act', onpointerdown: keep, onclick: () => createHighlight('y', 'note') }, ic('note'), 'Note'),
    h('button', { class: 'act', onpointerdown: keep, onclick: () => createHighlight('y', 'card') }, ic('card'), 'Card'));
  bar.hidden = false;
});

async function createHighlight(color, then) {
  const s = cur && cur.pending; if (!s) return;
  const hl = { id: Store.uid(), bookUid: cur.b.uid, chapterIdx: cur.ci, ...s, color, note: '', created: Date.now(), updated: Date.now() };
  await Store.put('highlights', hl);
  cur.hls.push(hl);
  getSelection().removeAllRanges(); $('#selbar').hidden = true; cur.pending = null;
  repaint(hl.paraUid);
  if (then === 'note') editHighlight(hl.id);
  else if (then === 'card') cardSheet(hl);
  else toast('Highlighted');
}
function repaint(paraUid) {
  const p = cur.paras.find((x) => x.u === paraUid);
  renderPara(cur.els.get(paraUid), p.t, cur.hls.filter((x) => x.paraUid === paraUid));
}

async function editHighlight(id, afterChange) {
  const hl = (cur && cur.hls.find((x) => x.id === id)) || await Store.get('highlights', id);
  if (!hl) return;
  const note = h('textarea', { placeholder: 'Your note…' }); note.value = hl.note || '';
  const after = async () => { if (cur && cur.b.uid === hl.bookUid) repaint(hl.paraUid); if (afterChange) afterChange(); };
  openSheet(h('h3', {}, 'Highlight'), h('blockquote', { 'data-c': hl.color }, hl.quote),
    h('div', { class: 'opts' }, ...COLORS.map((c) => h('button', { class: 'dot', 'data-c': c, 'aria-label': 'Colour', style: hl.color === c ? 'outline:2px solid var(--fg);outline-offset:3px' : '',
      onclick: async () => { hl.color = c; hl.updated = Date.now(); await Store.put('highlights', hl); await after(); done(); } }))),
    h('label', {}, 'Note'), note,
    h('div', { class: 'btns' },
      h('button', { class: 'primary', onclick: async () => { hl.note = note.value.trim(); hl.updated = Date.now(); await Store.put('highlights', hl); await after(); done(); toast('Saved'); } }, 'Save note'),
      h('button', { onclick: () => { done(); setTimeout(() => cardSheet(hl), 60); } }, ic('card'), 'Make card'),
      h('button', { class: 'danger', onclick: async () => {
        await Store.del('highlights', hl.id);
        if (cur) cur.hls = cur.hls.filter((x) => x.id !== hl.id);
        await after(); done(); toast('Deleted'); } }, 'Delete')));
}

/* ---------- flashcards (simple spaced repetition) ---------- */
async function dueCards() { const now = Date.now(); return (await Store.all('cards')).filter((c) => c.due <= now).sort((a, b) => a.due - b.due); }

function cardSheet(hl) {
  const b = Content.book(hl.bookUid), ctx = b && hl.chapterIdx != null ? partOf(b, hl.chapterIdx) : null;
  const front = h('textarea', { placeholder: 'Question / prompt' }); front.value = (hl.note ? hl.note : 'Explain: ' + hl.quote.split(/\s+/).slice(0, 8).join(' ') + '…');
  const back = h('textarea'); back.value = hl.quote;
  openSheet(h('h3', {}, 'New flashcard'), h('div', { class: 'dim small' }, ctx ? ctx._g.title : ''),
    h('label', {}, 'Front'), front, h('label', {}, 'Back'), back,
    h('div', { class: 'btns' }, h('button', { class: 'primary', onclick: async () => {
      if (!front.value.trim() || !back.value.trim()) return toast('Both sides needed');
      await Store.put('cards', { id: Store.uid(), bookUid: hl.bookUid, hlId: hl.id, front: front.value.trim(), back: back.value.trim(),
        due: Date.now(), interval: 0, ease: 2.5, reps: 0, created: Date.now(), updated: Date.now() });
      done(); toast('Card added'); refreshBadge(); } }, 'Add card')));
}

function grade(card, g) { // g: 0 again, 1 good, 2 easy
  const DAY = 864e5;
  if (g === 0) { card.reps = 0; card.interval = 0; card.ease = Math.max(1.3, card.ease - 0.2); card.due = Date.now() + 10 * 60e3; }
  else {
    card.interval = card.reps === 0 ? (g === 2 ? 3 : 1) : card.reps === 1 ? (g === 2 ? 6 : 3) : Math.round(card.interval * card.ease * (g === 2 ? 1.3 : 1));
    card.reps++; if (g === 2) card.ease += 0.1;
    card.due = Date.now() + card.interval * DAY;
  }
  card.updated = Date.now();
  return card;
}
const fmtIn = (ms) => { const m = Math.round(ms / 60e3); if (m < 60) return m + ' min'; const d = Math.round(m / 1440); return d < 1 ? Math.round(m / 60) + 'h' : d === 1 ? '1 day' : d + ' days'; };

// Where each card comes from: its book and chapter group (via the highlight it was made from).
async function cardPlaces(cards) {
  const hls = new Map((await Store.all('highlights')).map((x) => [x.id, x]));
  return cards.map((c) => {
    const hl = c.hlId ? hls.get(c.hlId) : null, b = Content.book(c.bookUid), p = b && hl ? partOf(b, hl.chapterIdx) : null;
    return { c, b, gi: p ? groups(b).indexOf(p._g) : -1 };
  });
}

// Review tab landing: review everything, or pick one book / one chapter.
async function reviewPicker(due) {
  const page = h('div', { class: 'page' },
    h('div', { class: 'lhead' }, h('div', {}, h('h1', {}, 'Review'), h('div', { class: 'dim small', style: 'margin-top:6px' }, `${due.length} card${due.length === 1 ? '' : 's'} due`))),
    h('a', { class: 'rvall', href: '#/review?all=1' }, ic('play'), h('span', { class: 'grow' }, 'Review all'), h('b', {}, due.length)));
  const byBook = new Map();
  for (const x of await cardPlaces(due)) {
    if (!x.b) continue;
    const e = byBook.get(x.b.uid) || { b: x.b, n: 0, gs: new Map() };
    e.n++; e.gs.set(x.gi, (e.gs.get(x.gi) || 0) + 1);
    byBook.set(x.b.uid, e);
  }
  if (byBook.size) page.append(h('span', { class: 'glabel' }, 'By book'));
  for (const { b, n, gs } of byBook.values()) {
    const chs = [...gs].filter(([gi]) => gi >= 0).sort((p, q) => p[0] - q[0]);
    const list = h('div', { class: 'parts', hidden: true },
      h('a', { href: `#/review?b=${b.uid}` }, 'All from this book', h('span', {}, n)),
      ...chs.map(([gi, k]) => h('a', { href: `#/review?b=${b.uid}&g=${gi}` }, groups(b)[gi].title, h('span', {}, k))));
    const head = h('button', { class: 'gh' }, h('span', { class: 'num' }, String(n)),
      h('div', { style: 'min-width:0' }, h('span', { class: 'nm' }, splitBook(b).main), h('span', { class: 'st' }, chs.length ? `${chs.length} chapter${chs.length === 1 ? '' : 's'}` : 'all chapters')), ic('next'));
    head.addEventListener('click', () => { list.hidden = !list.hidden; head.lastChild.replaceWith(ic(list.hidden ? 'next' : 'down')); });
    page.append(h('div', { class: 'grp rv' }, head, list));
  }
  view.append(page);
}

// /review            picker
// /review?all=1      every due card
// /review?b=&g=      one book, optionally one chapter group
// &n=5&then=/read/…  warm-up: at most n cards, then straight on to the reader
route(/^\/review$/, async (m, q) => {
  const due = await dueCards();
  const then = /^\/read\/[\w-]+\/\d+$/.test(q.get('then') || '') ? '#' + q.get('then') : null;
  const bq = q.get('b'), gq = q.get('g');
  if (!due.length) {
    if (then) { location.hash = then; return; }
    const total = (await Store.all('cards')).length;
    view.append(h('div', { class: 'page' }, h('div', { class: 'lhead' }, h('h1', {}, 'Review')),
      h('div', { class: 'empty' }, total ? `All caught up. ${total} card${total === 1 ? '' : 's'} scheduled for later.` : 'No cards yet. Select text in a book and tap Card.')));
    return;
  }
  if (!bq && !q.get('all')) return reviewPicker(due);
  let queue = bq ? (await cardPlaces(due)).filter((x) => x.c.bookUid === bq && (gq == null || x.gi === +gq)).map((x) => x.c) : due;
  if (+q.get('n') > 0) queue = queue.slice(0, +q.get('n'));
  if (!queue.length) { location.hash = then || '#/review'; return; }
  const exit = then || '#/review';
  document.body.classList.add('focus');
  const size = queue.length;
  let n = 0;
  const step = async () => {
    const c = queue[0];
    if (!c) {
      if (then) { toast(`Warm-up done: ${n} card${n === 1 ? '' : 's'}`); location.hash = then; return; }
      document.body.classList.remove('focus');
      const left = (await dueCards()).length;
      view.replaceChildren(h('div', { class: 'page' }, h('div', { class: 'lhead' }, h('h1', {}, 'Review')),
        h('div', { class: 'empty' }, `Done. ${n} card${n === 1 ? '' : 's'} reviewed.`,
          left ? h('div', { style: 'margin-top:16px' }, h('a', { href: '#/review' }, `${left} more due · Pick another set`)) : null)));
      refreshBadge(); return;
    }
    const hl = c.hlId ? await Store.get('highlights', c.hlId) : null;
    const b = Content.book(c.bookUid), part = b && hl ? partOf(b, hl.chapterIdx) : null;
    const chip = b ? splitBook(b).main + (part ? ' · ' + part._g.title : '') : 'Card';
    const ans = h('div', { class: 'ans', hidden: true }, h('span', { class: 'eyebrow' }, 'Answer'), h('p', {}, c.back),
      hl && hl.note && hl.note !== c.front ? h('p', { class: 'note' }, 'Your note: ' + hl.note) : null);
    const grades = h('div', { hidden: true },
      h('span', { class: 'rvq' }, 'How well did you remember?'),
      h('div', { class: 'grades' }, ...[['Again', 0], ['Good', 1], ['Easy', 2]].map(([l, g]) => h('button', { class: 'g' + g, onclick: async () => {
        await Store.put('cards', grade(c, g)); queue.shift(); if (g === 0) queue.push(c); else n++; step(); } },
        h('b', {}, l), h('span', {}, fmtIn(grade({ ...c }, g).due - Date.now()))))));
    const reveal = h('button', { class: 'primary reveal', onclick: () => { ans.hidden = false; grades.hidden = false; reveal.hidden = true; } }, 'Show answer');
    view.replaceChildren(
      h('div', { class: 'rvhead' }, h('a', { class: 'iconbtn', href: exit, 'aria-label': then ? 'Skip warm-up' : 'Close review', style: 'display:flex;align-items:center;justify-content:center;color:var(--fg)' }, ic('close')),
        h('div', { class: 'bar' }, h('div', { style: `width:${Math.round((100 * n) / size)}%` })), h('span', { class: 'n' }, `${Math.min(n + 1, size)} / ${size}`)),
      h('div', { class: 'fc' }, h('span', { class: 'chip ell' }, chip), h('p', { class: 'qn' }, c.front), ans),
      reveal, grades);
  };
  await step();
}, 'review');

/* ---------- Notes: highlights / bookmarks / re-attach ---------- */
const placeOf = (x) => { const b = Content.book(x.bookUid); const c = b && partOf(b, x.chapterIdx); return { b, c }; };
const readingOrder = (a, b) => {
  const ia = Content.index.books.findIndex((x) => x.uid === a.bookUid), ib = Content.index.books.findIndex((x) => x.uid === b.bookUid);
  return (ia - ib) || (a.chapterIdx - b.chapterIdx) || String(a.paraUid).localeCompare(String(b.paraUid)) || ((a.start || 0) - (b.start || 0));
};
function groupedList(page, items, card) {
  let lastLabel = null;
  for (const x of items) {
    const { b, c } = placeOf(x);
    const label = b ? `${splitBook(b).main} · ${c ? c._g.title : ''}` : 'Book not in this build';
    if (label !== lastLabel) { page.append(h('span', { class: 'glabel' }, label)); lastLabel = label; }
    page.append(card(x, c));
  }
}
async function notesMarkdown() {
  const hls = (await Store.all('highlights')).sort(readingOrder);
  const bms = (await Store.all('bookmarks')).sort(readingOrder);
  let md = `# PsychEngine notes\n\nExported ${new Date().toLocaleString()}\n`, lastB, lastC;
  for (const x of hls) {
    const { b, c } = placeOf(x);
    const bt = b ? shortTitle(b.title) : 'Book not in this build';
    if (bt !== lastB) { md += `\n## ${bt}\n`; lastB = bt; lastC = null; }
    const ct = c ? `${c._g.title}${c._g.parts.length > 1 ? ' — ' + partName(c) : ''}` : '';
    if (ct && ct !== lastC) { md += `\n### ${ct}\n`; lastC = ct; }
    md += `\n> ${x.quote.replace(/\n/g, '\n> ')}\n`;
    if (x.note) md += `\n${x.note}\n`;
  }
  if (bms.length) {
    md += '\n## Bookmarks\n\n';
    for (const x of bms) { const { b, c } = placeOf(x); md += `- ${b ? splitBook(b).main : '?'} · ${c ? c._g.title : ''}: ${x.label}…\n`; }
  }
  return md;
}

route(/^\/notes$/, async (m, q) => {
  const tab = q.get('t') || 'hl', bf = q.get('b') || '';
  const nav = (o) => { const p = new URLSearchParams({ t: tab, b: bf, ...o }); if (!p.get('b')) p.delete('b'); location.hash = '#/notes?' + p; };
  const allHl = await Store.all('highlights');
  const orphans = allHl.filter((x) => x.orphan);
  const bmsAll = await Store.all('bookmarks');
  const carded = new Set((await Store.all('cards')).map((c) => c.hlId));
  const page = h('div', { class: 'page' },
    h('div', { class: 'lhead' }, h('h1', {}, 'Notes'),
      h('button', { class: 'pill', onclick: async () => shareFile(`psychengine-notes-${dayKey()}.md`, await notesMarkdown(), 'text/markdown', 'Export notes') }, ic('export'), 'Export')),
    h('div', { class: 'seg', role: 'tablist' }, ...[['hl', `Highlights ${allHl.length - orphans.length}`], ['bm', `Bookmarks ${bmsAll.length}`], ['or', `Re-attach ${orphans.length}`]]
      .map(([k, l]) => h('button', { role: 'tab', class: tab === k ? 'on' : '', onclick: () => nav({ t: k }) }, l))));
  if (tab !== 'or') page.append(h('div', { class: 'chips' },
    h('button', { class: bf ? '' : 'on', onclick: () => nav({ b: '' }) }, 'All books'),
    ...Content.index.books.map((b) => h('button', { class: bf === b.uid ? 'on' : '', onclick: () => nav({ b: b.uid }) }, chipName(b)))));
  const inBook = (x) => !bf || x.bookUid === bf;
  const go = (x) => (location.hash = `#/read/${x.bookUid}/${x.chapterIdx}?p=${x.paraUid}`);
  const metaPart = (c) => (c && c._g.parts.length > 1 ? partName(c) + ' · ' : '');
  if (tab === 'hl') {
    const list = allHl.filter((x) => !x.orphan && inBook(x)).sort(readingOrder);
    if (!list.length) page.append(h('div', { class: 'empty' }, 'Long-press text while reading to highlight it.'));
    groupedList(page, list, (x, c) => h('article', { class: 'nitem', onclick: () => go(x) },
      h('div', { class: 'q' }, h('i', { 'data-c': x.color }), h('p', {}, x.quote)),
      x.note ? h('p', { class: 'note' }, x.note) : null,
      h('div', { class: 'meta' }, h('span', {}, metaPart(c) + ago(x.created)), carded.has(x.id) ? h('span', { class: 'cd' }, ic('card'), 'Card') : null)));
  } else if (tab === 'bm') {
    const list = bmsAll.filter(inBook).sort(readingOrder);
    if (!list.length) page.append(h('div', { class: 'empty' }, 'Tap the bookmark icon in the reader to save your place.'));
    groupedList(page, list, (x, c) => h('article', { class: 'nitem', onclick: () => go(x) },
      h('div', { class: 'q' }, h('i', {}), h('p', {}, x.label + '…')),
      h('div', { class: 'meta' }, h('span', {}, metaPart(c) + ago(x.created)),
        h('button', { class: 'ghost', onclick: async (e) => { e.stopPropagation(); await Store.del('bookmarks', x.id); render(); } }, 'Remove'))));
  } else {
    if (!orphans.length) page.append(h('div', { class: 'empty' }, 'Nothing to re-attach. If a book update moves text you highlighted and it can’t be found again, it shows up here.'));
    else page.append(h('p', { class: 'dim small', style: 'margin-top:16px' }, 'These highlights could not be found after a content update. Your text is kept — copy it, or delete it.'));
    groupedList(page, orphans, (x) => h('article', { class: 'nitem' },
      h('div', { class: 'q' }, h('i', { 'data-c': x.color }), h('p', {}, x.quote)), x.note ? h('p', { class: 'note' }, x.note) : null,
      h('div', { class: 'meta' }, h('span', {}, ago(x.created)), h('button', { class: 'ghost danger', onclick: async () => { await Store.del('highlights', x.id); render(); } }, 'Delete'))));
  }
  view.append(page);
}, 'notes');

/* ---------- Search ---------- */
route(/^\/search$/, async (m, q) => {
  const input = h('input', { type: 'search', placeholder: 'Search all books…', value: q.get('q') || '', autocomplete: 'off', 'aria-label': 'Search all books' });
  const out = h('div', {});
  const status = h('div', { class: 'dim small', style: 'margin:12px 0' });
  view.append(h('div', { class: 'page' },
    h('div', { class: 'row', style: 'padding-top:12px' }, h('a', { class: 'iconbtn', href: '#/', 'aria-label': 'Back', style: 'display:flex;align-items:center;justify-content:center;color:var(--fg);margin-left:-12px' }, ic('back')), h('h1', {}, 'Search')),
    h('label', { class: 'sbox' }, ic('search'), input), status, out));
  let ready = false, t;
  const run = async () => {
    const term = input.value.trim(); out.replaceChildren();
    if (term.length < 2) { status.textContent = ''; return; }
    if (!ready) status.textContent = 'Preparing search (first time only)…';
    const res = await Content.search(term); ready = true;
    status.textContent = res.length ? `${res.length}${res.length === 40 ? '+' : ''} results` : 'No results';
    const words = term.toLowerCase().split(/\s+/).filter(Boolean);
    for (const r of res) {
      const paras = await Content.chapter(r.b, r.c);
      const p = paras.find((x) => x.u === r.id); if (!p) continue;
      const lower = p.t.toLowerCase();
      let at = Math.min(...words.map((w) => lower.indexOf(w)).filter((i) => i >= 0), p.t.length);
      if (!isFinite(at)) at = 0;
      const s = Math.max(0, at - 60), snip = h('div', { class: 'snip' });
      const piece = (s > 0 ? '…' : '') + p.t.slice(s, s + 220) + '…';
      const re = new RegExp('(' + words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'ig');
      piece.split(re).forEach((seg, i) => snip.append(i % 2 ? h('mark', {}, seg) : seg));
      const b = Content.book(r.b), c = partOf(b, r.c);
      out.append(h('a', { class: 'card', href: `#/read/${r.b}/${r.c}?p=${r.id}` }, snip,
        h('div', { class: 'dim small', style: 'margin-top:8px' }, splitBook(b).main + ' · ' + c._g.title)));
    }
  };
  input.addEventListener('input', () => { clearTimeout(t); t = setTimeout(run, 300); });
  if (input.value) run(); else input.focus();
}, 'home');

/* ---------- You: stats, goal, backup, appearance, about ---------- */
async function shareFile(name, text, type, title) {
  const cap = window.Capacitor && window.Capacitor.Plugins;
  try {
    if (cap && cap.Filesystem && cap.Share) {
      const r = await cap.Filesystem.writeFile({ path: name, directory: 'CACHE', data: text, encoding: 'utf8' });
      await cap.Share.share({ title, url: r.uri, dialogTitle: title });
      return;
    }
  } catch (e) { if (String(e && e.message).includes('cancel')) return; }
  const a = h('a', { href: URL.createObjectURL(new Blob([text], { type })), download: name });
  document.body.append(a); a.click(); a.remove();
}
async function shareBackup() {
  shareFile(`psychengine-backup-${dayKey()}.json`, JSON.stringify(await Store.exportAll(), null, 1), 'application/json', 'Save backup to…');
}
async function importFile(file) {
  try {
    const res = await Store.importAll(JSON.parse(await file.text()));
    toast(`Imported: ${res.added} new, ${res.updated} updated`);
    refreshBadge(); render();
  } catch (e) { toast('Import failed: ' + e.message); }
}

route(/^\/(you|more)$/, async () => {
  const [hls, bms, cards, auto, st] = await Promise.all([Store.all('highlights'), Store.all('bookmarks'), Store.all('cards'), Store.getKV('lastAutoBackup'), readingStats()]);
  const file = h('input', { type: 'file', accept: '.json,application/json', hidden: true, onchange: (e) => e.target.files[0] && importFile(e.target.files[0]) });
  const top = Math.max(settings.goal, ...st.week.map((x) => x.m));
  const goalBtn = (v) => h('button', { class: settings.goal === v ? 'on' : '', onclick: async () => { settings.goal = v; await saveSettings(); render(); } }, v + ' min');
  view.append(h('div', { class: 'page' },
    h('div', { class: 'lhead' }, h('h1', {}, 'You')),
    h('div', { class: 'stats', style: 'margin-top:20px' },
      h('div', { class: 'stat hot' }, ic('flame'), h('b', {}, st.streak), h('span', {}, 'day streak')),
      h('div', { class: 'stat' }, ic('clock'), h('b', {}, fmtDur(st.total)), h('span', {}, 'read in total')),
      h('div', { class: 'stat vio' }, ic('card'), h('b', {}, cards.length), h('span', {}, 'cards'))),
    h('div', { class: 'sec' }, h('h2', {}, 'This week'), h('span', { class: 'dim' }, `goal ${settings.goal} min a day`)),
    h('div', { class: 'card', style: 'margin:0' },
      h('div', { class: 'week' }, ...st.week.map((x) => h('div', {}, h('span', {}, x.m || ''), h('i', { class: x.m >= settings.goal ? 'met' : '', style: `height:${Math.round((70 * x.m) / top)}px` }),
        x.d.toLocaleDateString(undefined, { weekday: 'narrow' })))),
      h('div', { class: 'dim small', style: 'margin:14px 0 8px' }, 'Daily goal'), h('div', { class: 'opts', style: 'display:grid;grid-template-columns:repeat(4,1fr)' }, goalBtn(10), goalBtn(20), goalBtn(30), goalBtn(45))),
    h('div', { class: 'sec' }, h('h2', {}, 'Your data')),
    h('div', { class: 'card', style: 'margin:0' },
      h('div', {}, `${hls.length} highlights · ${bms.length} bookmarks · ${cards.length} cards`),
      h('p', { class: 'dim small' }, 'Stored on this phone, separate from the books. Installing a new version of the app keeps it.'),
      h('div', { class: 'row' }, h('button', { class: 'primary grow', onclick: shareBackup }, 'Export backup'), h('button', { class: 'grow', onclick: () => file.click() }, 'Import backup'), file),
      h('p', { class: 'dim small' }, 'Import merges into what is already here — it never deletes. Keep an exported copy somewhere safe (Drive, email to yourself): clearing app data or uninstalling erases the on-phone copy.'),
      h('p', { class: 'dim small', style: 'margin-bottom:0' }, auto ? (auto.ok ? 'Automatic copy saved to Documents/PsychEngine/backup.json at ' + new Date(auto.at).toLocaleString() : 'Automatic copy to Documents not available on this phone (use Export).') : 'Automatic copy runs after your next edit.')),
    h('div', { class: 'sec' }, h('h2', {}, 'Settings')),
    h('div', { class: 'card', style: 'margin:0;padding:4px 16px' },
      h('button', { class: 'lnk', onclick: openAppearance }, 'Theme, font, text size', ic('next')),
      h('button', { class: 'lnk', onclick: async () => shareFile(`psychengine-notes-${dayKey()}.md`, await notesMarkdown(), 'text/markdown', 'Export notes') }, 'Export notes as Markdown', ic('next'))),
    h('div', { class: 'dim small', style: 'margin-top:20px;text-align:center' }, `${Content.index.books.length} books · content version ${Content.index.version}`, h('br'), 'Fully offline. No account, no network.')));
}, 'you');

/* ---------- boot ---------- */
async function boot() {
  await Store.init();
  settings = { ...DEFAULTS, ...(await Store.getKV('settings', {})) };
  applySettings();
  await Content.loadIndex();
  const r = await Content.reconcile();
  if (r && (r.moved || r.orphaned)) toast(`Library updated: ${r.moved} highlights re-anchored, ${r.orphaned} need attention`);
  await render();
}
boot().catch((e) => { view.textContent = 'Failed to start: ' + (e && e.stack || e); });
