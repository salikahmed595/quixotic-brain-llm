/* Quixotic AI — front-end. No mock data: everything below is read from, or written to, the backend API (/v1/...). */
(() => {
'use strict';

/* Opened straight from disk (file://)? That page can never reach the backend, so go to the real address instead. */
if (location.protocol === 'file:') { location.replace('http://localhost:8000/'); return; }

/* ================= helpers ================= */
const API = (window.QB_API || new URLSearchParams(location.search).get('api') || '').replace(/\/$/, '');
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const lsGet = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
const lsSet = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} };
const ssGet = k => { try { return sessionStorage.getItem(k); } catch (e) { return null; } };
const ssSet = (k, v) => { try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch (e) {} };

const P = {
  ask: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/>', book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', doc: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  cloud: '<path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 20 11a3.5 3.5 0 0 1-1 7z"/><path d="M12 12v7M9 14.5l3-3 3 3"/>', check: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
  chart: '<path d="M5 21V10M12 21V4M19 21v-7"/>', alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5h.01"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3.2-5.5 7-5.5s7 2 7 5.5"/><circle cx="17" cy="9" r="2.5"/><path d="M17 14.5c3 0 5 1.5 5 4"/>',
  build: '<rect x="4" y="3" width="12" height="18" rx="1"/><path d="M16 9h4v12h-4M8 7h4M8 11h4M8 15h4"/>', key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>', mic: '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  send: '<path d="M21 3L3 11l7 3 3 7z"/><path d="M10 14l11-11"/>', chevd: '<path d="M6 9l6 6 6-6"/>', chevr: '<path d="M9 6l6 6-6 6"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>', out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  up: '<path d="M7 11v9H4v-9zM7 11l4-8a2 2 0 0 1 3 2l-1 4h6a2 2 0 0 1 2 2l-2 7a2 2 0 0 1-2 1.5H7"/>', down: '<path d="M17 13V4h3v9zM17 13l-4 8a2 2 0 0 1-3-2l1-4H5a2 2 0 0 1-2-2l2-7a2 2 0 0 1 2-1.5H17"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"/>', spark: '<path d="M12 3l2.2 6.3L21 11.5l-6.8 2.2L12 20l-2.2-6.3L3 11.5l6.8-2.2z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>', building: '<rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>',
  pen: '<path d="M4 20l1-5L16 4a2.5 2.5 0 0 1 4 4L9 19z"/>', msg: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/><path d="M8.5 11h7M8.5 14h4"/>',
  dots: '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>', pulse: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  newchat: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>', sidebar: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>', sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9M13 4v6M7 14v6"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>', lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
};
const ic = (n, s) => `<svg class="i" viewBox="0 0 24 24"${s ? ` style="width:${s}px;height:${s}px"` : ''}>${P[n] || ''}</svg>`;
const LOGO = '<svg viewBox="0 0 24 24" width="20" height="20" fill="#fff"><path d="M12 3l2.2 6.3L21 11.5l-6.8 2.2L12 20l-2.2-6.3L3 11.5l6.8-2.2z"/></svg>';

const toast = m => { const t = $('#toast'); t.textContent = m; t.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 3200); };
const fmtDate = iso => { if (!iso) return '—'; const d = new Date(iso); if (isNaN(d)) return '—';
  const s = (Date.now() - d) / 1000; if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + ' min ago'; if (s < 86400) return Math.floor(s / 3600) + ' h ago';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); };
const avatarHTML = (u, size) => { const st = size ? ` style="width:${size}px;height:${size}px;font-size:${Math.round(size * .38)}px"` : '';
  return u && u.avatar ? `<img class="avatar" alt="" src="${esc(u.avatar)}"${st}>` : `<span class="avatar"${st}>${esc(initials(u && u.full_name))}</span>`; };
const initials = n => (n || '?').split(/\s+/).map(x => x[0]).slice(0, 2).join('').toUpperCase();
const RANK = { employee: 0, contributor: 1, manager: 2, administrator: 3 };
const ROLE_LABEL = { employee: 'Employee', contributor: 'Contributor', manager: 'Manager', administrator: 'Administrator' };
const rank = () => RANK[S.me?.role] ?? 0;
const STATUS = { draft: ['Draft', ''], submitted: ['Submitted', 'blue'], pending_review: ['Pending review', 'amber'], approved: ['Approved', 'blue'],
  active: ['Active', 'green'], rejected: ['Rejected', 'red'], archived: ['Archived', ''], expired: ['Expired', ''] };
const statusChip = s => { const [l, c] = STATUS[s] || [s, '']; return `<span class="chip dot ${c}">${l}</span>`; };
const isMobile = () => window.matchMedia('(max-width: 900px)').matches;

/* ================= API ================= */
const S = { requests: 0, me: null, token: lsGet('qb_token'), departments: [], chats: [], chatFilter: '',
  ask: { mode: 'general', scope: null, thread: [], busy: false, convId: null }, timer: null, pending: 0 };

async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {};
  if (S.token) headers.Authorization = 'Bearer ' + S.token;
  let payload;
  if (form) payload = form; else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let res;
  try { res = await fetch(API + path, { method, headers, body: payload }); }
  catch (e) { throw Object.assign(new Error('Cannot reach the server. Check your connection and try again.'), { status: 0 }); }
  if (res.status === 401 && S.token && path !== '/v1/auth/login') { logout(true); throw Object.assign(new Error('Your session has ended. Please sign in again.'), { status: 401 }); }
  if (res.status === 204) return null;
  let data = null; try { data = await res.json(); } catch (e) {}
  if (!res.ok) {
    let msg = data && data.detail; if (Array.isArray(msg)) msg = msg.map(x => x.msg).join('; ');
    throw Object.assign(new Error(msg || `Something went wrong (${res.status}).`), { status: res.status });
  }
  return data;
}

/* ================= UI primitives ================= */
function modal(title, html, { onMount, wide } = {}) {
  const el = document.createElement('div'); el.className = 'modal-scrim';
  el.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}" ${wide ? 'style="width:min(680px,100%)"' : ''}><h3>${esc(title)}</h3>${html}</div>`;
  const close = () => el.remove();
  el.addEventListener('mousedown', e => { if (e.target === el) close(); });
  document.body.append(el); onMount && onMount(el, close);
  const f = $('input,select,textarea', el); f && f.focus();
  return { el, close };
}
function drawer(html, onMount) {
  const el = document.createElement('div'); el.className = 'scrim';
  el.innerHTML = `<aside class="drawer" role="dialog" aria-modal="true">${html}</aside>`;
  const close = () => el.remove();
  el.addEventListener('mousedown', e => { if (e.target === el) close(); });
  document.body.append(el); onMount && onMount(el, close); return { el, close };
}
const emptyState = (icon, title, text, action = '') => `<div class="empty"><div class="ico">${ic(icon, 22)}</div><h3>${esc(title)}</h3><p>${esc(text)}</p>${action ? `<div style="margin-top:14px">${action}</div>` : ''}</div>`;
const errBanner = e => `<div class="banner err">${esc(e.message || e)}</div>`;
const loading = () => '<div class="empty"><div class="typing"><i></i><i></i><i></i></div></div>';
async function busy(btn, fn) { if (!btn) return fn(); const t = btn.innerHTML; btn.disabled = true; try { return await fn(); } finally { btn.disabled = false; btn.innerHTML = t; } }
const deptChecks = (name, depts, sel = []) => depts.length ? depts.map(d => `<label class="check"><input type="checkbox" name="${name}" value="${d.id}" ${sel.includes(d.id) ? 'checked' : ''}> ${esc(d.name)}</label>`).join('')
  : '<p class="hint">No departments are available to you yet. Ask an administrator to assign you to one.</p>';
const checked = (root, name) => $$(`input[name="${name}"]:checked`, root).map(i => i.value);

/* ================= shell: ChatGPT-style sidebar for everyone ================= */
const NAV = [
  { group: 'Knowledge', min: 1 },
  { id: 'knowledge', label: 'Knowledge', icon: 'book', min: 1 },
  { id: 'add', label: 'Add information', icon: 'plus', min: 1 },
  { id: 'documents', label: 'Documents', icon: 'doc', min: 1 },
  { id: 'sales', label: 'Sales memory', icon: 'msg', min: 3 },
  { group: 'Manage', min: 2 },
  { id: 'approvals', label: 'Approvals', icon: 'check', min: 2 },
  { id: 'requests', label: 'Access requests', icon: 'users', min: 2 },
  { id: 'dashboard', label: 'Dashboard', icon: 'chart', min: 2 },
  { id: 'insights', label: 'Insights', icon: 'alert', min: 3 },
  { group: 'Administration', min: 3 },
  { id: 'users', label: 'Users', icon: 'users', min: 3 },
  { id: 'departments', label: 'Departments', icon: 'build', min: 3 },
  { id: 'vocabulary', label: 'Vocabulary', icon: 'spark', min: 3 },
  { id: 'keys', label: 'API keys', icon: 'key', min: 3 },
  { id: 'system', label: 'System', icon: 'pulse', min: 3 },
];
const visibleNav = () => NAV.filter(n => n.min <= rank());
const pageMin = id => (NAV.find(n => n.id === id) || { min: 0 }).min;
function parseRoute() {
  const h = location.hash.replace(/^#\/?/, '').split('?')[0]; const [first, second] = h.split('/');
  if (!first || first === 'ask') return { page: 'ask' };
  if (first === 'chat' && second) return { page: 'ask', chat: second };
  return { page: first };
}
const go = id => { location.hash = '#/' + id; };

function groupChats(chats) {
  const now = new Date(), startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime(), day = 86400000;
  const buckets = [['Today', []], ['Yesterday', []], ['Previous 7 days', []], ['Previous 30 days', []], ['Older', []]];
  chats.forEach(c => { const t = new Date(c.updated_at).getTime();
    (t >= startToday ? buckets[0] : t >= startToday - day ? buckets[1] : t >= startToday - 7 * day ? buckets[2] : t >= startToday - 30 * day ? buckets[3] : buckets[4])[1].push(c); });
  return buckets.filter(b => b[1].length);
}
function chatListHTML() {
  const q = S.chatFilter.trim().toLowerCase(), list = S.chats.filter(c => !q || c.title.toLowerCase().includes(q));
  if (!S.chats.length) return '<p class="sb-empty">Your chats will appear here.</p>';
  if (!list.length) return '<p class="sb-empty">No chats match your search.</p>';
  return groupChats(list).map(([label, items]) => `<div class="sb-label">${label}</div>${items.map(c => `<a class="chat-item ${c.id === S.ask.convId ? 'on' : ''}" href="#/chat/${c.id}" data-chat="${c.id}"><span class="t">${esc(c.title)}</span><button class="dots" data-chatmenu="${c.id}" aria-label="Chat options">${ic('dots', 16)}</button></a>`).join('')}`).join('');
}
function renderChatList() { const el = $('#chatList'); if (el) el.innerHTML = chatListHTML(); }
async function loadChats() { try { S.chats = (await api('/v1/conversations')).conversations; } catch (e) { S.chats = S.chats || []; } renderChatList(); }

function drawShell() {
  $('#app').innerHTML = `<div class="shell2 ${lsGet('qb_sb') === '0' ? 'collapsed' : ''}" id="shell"><div class="sb-scrim" id="sbScrim"></div><aside class="sb" id="sb"></aside>
    <div class="main2"><header class="top2" id="top"></header><div id="view" class="view2"></div></div></div>`;
  $('#sbScrim').onclick = () => setSidebar(false);
}
function setSidebar(open) {
  const sh = $('#shell'); if (!sh) return;
  if (isMobile()) sh.classList.toggle('open', open);
  else { sh.classList.toggle('collapsed', !open); lsSet('qb_sb', open ? '1' : '0'); }
}

function refreshSidebar(cur) {
  const m = S.me, nav = visibleNav(), staff = nav.length > 0, wsOpen = lsGet('qb_ws') !== '0';
  let items = '';
  nav.forEach((n, i) => {
    if (n.group) { if (nav[i + 1] && !nav[i + 1].group) items += `<div class="navlabel">${n.group}</div>`; return; }
    items += `<a class="navitem ${n.id === cur ? 'on' : ''}" href="#/${n.id}">${ic(n.icon)}<span>${n.label}</span>${n.id === 'approvals' && S.pending ? `<span class="count">${S.pending}</span>` : ''}${n.id === 'requests' && S.requests ? `<span class="count">${S.requests}</span>` : ''}</a>`;
  });
  $('#sb').innerHTML = `<div class="sb-head"><a class="brand" href="#/ask" id="homeLink"><span class="brand-mark">${LOGO}</span><span>Quixotic <b>AI</b></span></a><button class="icon-btn" id="sbClose" title="Close sidebar" aria-label="Close sidebar">${ic('sidebar', 20)}</button></div>
    <button class="sb-new" id="newChat">${ic('newchat', 19)}<span>New chat</span></button>
    <label class="sb-search">${ic('search', 18)}<input id="chatQ" placeholder="Search chats" value="${esc(S.chatFilter)}" autocomplete="off"></label>
    ${staff ? `<button class="ws-toggle" id="wsToggle" aria-expanded="${wsOpen}">${ic('chevr', 14)}<span>Workspace</span></button><div class="ws ${wsOpen ? 'open' : ''}" id="ws">${items}</div>` : ''}
    <div class="sb-chats" id="chatList">${chatListHTML()}</div>
    <div class="sb-user" id="meBtn" role="button" tabindex="0">${avatarHTML(m)}<span class="who"><b>${esc(m.full_name)}</b><small>${ROLE_LABEL[m.role]}${m.departments.length ? ' · ' + esc(m.departments.map(d => d.name).join(', ')) : ''}</small></span>${ic('dots', 18)}</div>`;
  $('#sbClose').onclick = () => setSidebar(false);
  $('#newChat').onclick = () => { newChat(); if (isMobile()) setSidebar(false); };
  $('#homeLink').onclick = e => { e.preventDefault(); newChat(); };
  $('#chatQ').oninput = e => { S.chatFilter = e.target.value; renderChatList(); };
  const ws = $('#wsToggle'); if (ws) ws.onclick = () => { const open = !$('#ws').classList.contains('open'); $('#ws').classList.toggle('open', open); ws.setAttribute('aria-expanded', open); lsSet('qb_ws', open ? '1' : '0'); };
  $('#meBtn').onclick = e => { e.stopPropagation(); accountMenu(e.currentTarget); };
  $('#sb').onclick = e => { if (isMobile() && e.target.closest('a')) setSidebar(false); };
}
document.addEventListener('click', e => {
  const dots = e.target.closest('[data-chatmenu]'); if (!dots) return;
  e.preventDefault(); e.stopPropagation(); const id = dots.dataset.chatmenu, chat = S.chats.find(c => c.id === id); if (!chat) return;
  openMenu(dots, [['Rename', 'pen', () => renameChat(chat)], ['Delete', 'trash', () => deleteChat(chat)]]);
}, true);
function openMenu(anchor, items, up) {
  $('.cmenu')?.remove(); const r = anchor.getBoundingClientRect(), m = document.createElement('div'); m.className = 'cmenu';
  m.innerHTML = items.map((it, i) => `<button data-i="${i}" class="${it[1] === 'trash' ? 'danger' : ''}">${ic(it[1], 16)} ${it[0]}</button>`).join('');
  document.body.append(m);
  const h = m.offsetHeight, w = m.offsetWidth;
  m.style.left = Math.min(Math.max(8, up ? r.left : r.right - w + 4), innerWidth - w - 8) + 'px'; m.style.top = (up ? r.top - h - 8 : r.bottom + 4) + 'px';
  m.onclick = e => { const b = e.target.closest('button'); if (!b) return; m.remove(); items[+b.dataset.i][2](); };
}
document.addEventListener('click', e => { if (!e.target.closest('.cmenu,[data-chatmenu],#meBtn')) $('.cmenu')?.remove(); const p = $('.pop'); if (p && !e.target.closest('.pop,[data-pop]')) p.remove(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { $('.cmenu')?.remove(); $('.pop')?.remove(); } });

function renameChat(chat) {
  modal('Rename chat', `<div class="field" style="margin-bottom:16px"><input class="input" id="rn" value="${esc(chat.title)}" maxlength="120"></div><div id="rnErr"></div><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn primary" data-ok>Save</button></div>`,
    { onMount: (el, close) => { const input = $('#rn', el); input.select(); $('[data-x]', el).onclick = close;
      const save = async () => { try { const r = await api(`/v1/conversations/${chat.id}`, { method: 'PATCH', body: { title: input.value } }); chat.title = r.title; close(); renderChatList(); } catch (e) { $('#rnErr', el).innerHTML = errBanner(e); } };
      $('[data-ok]', el).onclick = save; input.onkeydown = e => { if (e.key === 'Enter') save(); }; } });
}
function deleteChat(chat) {
  modal('Delete chat?', `<p style="color:var(--ink-2);margin-bottom:18px">This will delete <b>${esc(chat.title)}</b>. It can’t be undone.</p><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn bad" data-ok>Delete</button></div>`,
    { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = async () => { try { await api(`/v1/conversations/${chat.id}`, { method: 'DELETE' }); close();
      S.chats = S.chats.filter(c => c.id !== chat.id); if (S.ask.convId === chat.id) newChat(); else renderChatList(); toast('Chat deleted'); } catch (e) { toast(e.message); } }; } });
}
function newChat() {
  const A = S.ask; A.thread = []; A.convId = null; S.chatFilter = '';
  if (location.hash === '#/ask' || location.hash === '' || location.hash === '#') renderApp(); else go('ask');
}

function refreshTop(inChat) {
  $('#top').innerHTML = `<button class="icon-btn" id="sbOpen" title="Open sidebar" aria-label="Open sidebar">${ic('menu', 22)}</button>${inChat ? '<span class="ttl">Quixotic AI</span>' : ''}`;
  $('#sbOpen').onclick = () => setSidebar(true);
}

async function renderApp() {
  clearInterval(S.timer);
  const r = parseRoute(); let page = r.page;
  if (page !== 'ask' && !NAV.some(n => n.id === page)) page = 'ask';
  if (pageMin(page) > rank()) { page = 'ask'; history.replaceState(null, '', '#/ask'); }
  if (!$('#shell')) drawShell();
  const view = $('#view'), A = S.ask;
  if (page === 'ask') {
    if (r.chat) { if (A.convId !== r.chat) { view.innerHTML = loading(); await loadChat(r.chat); } }
    else { A.thread = []; A.convId = null; }
  }
  refreshSidebar(page); refreshTop(page === 'ask' && A.thread.length > 0);
  try { await PAGES[page](view); } catch (e) { view.innerHTML = `<div class="page">${errBanner(e)}</div>`; }
  scrollTo(0, 0);
}

/* ================= ACCOUNT: menu, profile, personalization, settings (owner request) ================= */
function accountMenu(anchor) {
  $('.cmenu')?.remove(); const m = S.me, r = anchor.getBoundingClientRect(), el = document.createElement('div'); el.className = 'cmenu acct';
  const items = [['Personalization', 'sliders', personalizationModal], ['Profile', 'user', profileModal], ['Settings', 'gear', settingsModal]];
  el.innerHTML = `<div class="acct-head">${avatarHTML(m, 40)}<div><b>${esc(m.full_name)}</b><small>${esc(m.email)}</small></div></div>
    ${items.map((it, i) => `<button data-i="${i}">${ic(it[1], 17)} ${it[0]}</button>`).join('')}<hr><button data-i="out">${ic('out', 17)} Log out</button>`;
  document.body.append(el);
  const h = el.offsetHeight, w = Math.max(el.offsetWidth, r.width);
  el.style.minWidth = w + 'px'; el.style.left = Math.min(Math.max(8, r.left), innerWidth - w - 8) + 'px'; el.style.top = Math.max(8, r.top - h - 8) + 'px';
  el.onclick = e => { const b = e.target.closest('button'); if (!b) return; el.remove(); if (b.dataset.i === 'out') logout(); else items[+b.dataset.i][2](); };
}
function applyMe(me) { S.me = me; refreshSidebar(parseRoute().page); }

async function toAvatar(file) {
  if (!/^image\//.test(file.type)) throw new Error('Please choose an image file (PNG, JPG or WebP).');
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('That image could not be read. Try a PNG or JPG.')); i.src = url; });
    const size = 256, side = Math.min(img.width, img.height), c = document.createElement('canvas'); c.width = c.height = size;
    c.getContext('2d').drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);       // centred square
    return c.toDataURL('image/jpeg', 0.85);
  } finally { URL.revokeObjectURL(url); }
}
function profileModal() {
  const m = S.me; let avatar = m.avatar, removed = false;
  modal('Profile', `<form id="pf" class="grid" style="gap:18px">
    <div class="row" style="gap:18px"><div id="pfAv">${avatarHTML({ ...m, avatar }, 84)}</div>
      <div class="grid" style="gap:8px"><div class="row" style="flex-wrap:wrap"><label class="btn sm" for="pfFile" style="cursor:pointer">${ic('cloud', 15)} Upload photo</label><input id="pfFile" type="file" accept="image/*" hidden><button type="button" class="btn ghost sm" id="pfRm">Remove</button></div>
      <span class="hint">PNG, JPG or WebP. It is cropped to a small square.</span></div></div>
    <div class="field"><label>Full name</label><input class="input" name="n" required maxlength="80" value="${esc(m.full_name)}"></div>
    <dl class="kv"><dt>Email</dt><dd>${esc(m.email)}</dd><dt>Employee ID</dt><dd>${esc(m.employee_id)}</dd><dt>Role</dt><dd>${ROLE_LABEL[m.role]}</dd>
      <dt>Access</dt><dd>${m.departments.length ? m.departments.map(d => `<span class="chip" style="margin:2px">${esc(d.name)}</span>`).join('') : '<span class="hint">None yet — ask an administrator</span>'}</dd></dl>
    <p class="hint">Your role and access are set by an administrator. They decide which company knowledge your answers can use.</p>
    <div id="pfm"></div><div class="row" style="justify-content:flex-end"><button type="button" class="btn" data-x>Cancel</button><button class="btn primary">Save</button></div></form>`,
    { onMount: (el, close) => {
      const paint = () => { $('#pfAv', el).innerHTML = avatarHTML({ ...m, avatar: removed ? null : avatar }, 84); };
      $('[data-x]', el).onclick = close;
      $('#pfFile', el).onchange = async e => { const f = e.target.files[0]; if (!f) return; try { avatar = await toAvatar(f); removed = false; paint(); $('#pfm', el).innerHTML = ''; } catch (err) { $('#pfm', el).innerHTML = errBanner(err); } };
      $('#pfRm', el).onclick = () => { removed = true; avatar = null; paint(); };
      $('#pf', el).onsubmit = async e => { e.preventDefault(); const body = { full_name: e.target.n.value };
        if (removed) body.avatar = ''; else if (avatar && avatar !== m.avatar) body.avatar = avatar;
        try { const me = await busy(e.submitter, () => api('/v1/auth/profile', { method: 'PATCH', body })); close(); applyMe(me); toast('Profile saved'); } catch (err) { $('#pfm', el).innerHTML = errBanner(err); } };
    } });
}
const PREF_STYLE = [['concise', 'Short and to the point'], ['balanced', 'Balanced'], ['detailed', 'Detailed, step by step']];
const PREF_TONE = [['professional', 'Professional'], ['friendly', 'Friendly'], ['direct', 'Direct']];
const PREF_LANG = [['auto', 'Same language as my question'], ['english', 'Always English'], ['urdu', 'Always Urdu (اردو)'], ['roman_urdu', 'Always Roman Urdu']];
function personalizationModal() {
  const p = S.me.preferences || {}, opts = (list, v) => list.map(o => `<option value="${o[0]}" ${o[0] === v ? 'selected' : ''}>${o[1]}</option>`).join('');
  modal('Personalization', `<form id="pz" class="grid" style="gap:16px">
    <p class="hint">Make Quixotic AI answer the way you like. This changes how answers are written — never what the company knowledge says, and never what you are allowed to see.</p>
    <div class="grid" style="grid-template-columns:1fr 1fr;gap:12px"><div class="field"><label>Answer length</label><select class="select" name="s">${opts(PREF_STYLE, p.answer_style)}</select></div>
      <div class="field"><label>Tone</label><select class="select" name="t">${opts(PREF_TONE, p.tone)}</select></div></div>
    <div class="field"><label>Reply language</label><select class="select" name="l">${opts(PREF_LANG, p.language)}</select></div>
    <div class="field"><label>About you and your work <span class="hint">(optional)</span></label><textarea class="textarea" name="a" maxlength="500" style="min-height:80px" placeholder="e.g. I lead the Karachi sales team and mostly handle price objections.">${esc(p.about_me || '')}</textarea></div>
    <div class="field"><label>How should answers be written? <span class="hint">(optional)</span></label><textarea class="textarea" name="i" maxlength="500" style="min-height:80px" placeholder="e.g. Give me bullet points and one example script I can say to the customer.">${esc(p.instructions || '')}</textarea></div>
    <div class="card" style="box-shadow:none;background:var(--bg);padding:14px"><label class="check"><input type="checkbox" name="lrn" ${p.learn === false ? '' : 'checked'}> <b>Learn from my 👍 / 👎</b></label><div id="lrnBox" class="hint" style="margin-top:8px">Looking at your ratings…</div></div>
    <div id="pzm"></div><div class="row" style="justify-content:flex-end"><button type="button" class="btn" data-x>Cancel</button><button class="btn primary">Save</button></div></form>`,
    { wide: true, onMount: (el, close) => { $('[data-x]', el).onclick = close;
      const fillLearned = () => api('/v1/auth/learned').then(l => { const box = $('#lrnBox', el); if (!box) return;
        const forget = (l.liked || l.disliked) ? '<div style="margin-top:8px"><button type="button" class="btn sm" id="forget">Forget what I learned</button></div>' : '';
        box.innerHTML = (l.hints.length ? `<p>From your ratings (${l.liked} 👍, ${l.disliked} 👎) I noticed you like: <b>${l.hints.map(esc).join('</b>, <b>')}</b>. I use this for your answers.</p>`
          : `<p>Nothing learned yet (${l.liked} 👍, ${l.disliked} 👎 so far). After a few of each I look for patterns, such as short answers or bullet points.</p>`) + forget;
        const f = $('#forget', el); if (f) f.onclick = async () => { try { await api('/v1/auth/learned/reset', { method: 'POST' }); toast('Forgotten. I start fresh from your next rating.'); fillLearned(); } catch (e) { toast(e.message); } }; }).catch(() => { const b = $('#lrnBox', el); if (b) b.textContent = ''; });
      fillLearned();
      $('#pz', el).onsubmit = async e => { e.preventDefault(); const f = e.target;
      try { const prefs = await busy(e.submitter, () => api('/v1/auth/preferences', { method: 'PUT', body: { answer_style: f.s.value, tone: f.t.value, language: f.l.value, about_me: f.a.value, instructions: f.i.value, learn: f.lrn.checked } }));
        S.me.preferences = prefs; close(); toast('Saved. Your next answers will follow this.'); } catch (err) { $('#pzm', el).innerHTML = errBanner(err); } }; } });
}
function settingsModal() {
  modal('Settings', `<div class="grid" style="gap:22px">
    <form id="pw" class="grid" style="gap:12px"><h4 style="font-size:15px">${ic('lock', 16)} Change password</h4>
      <div class="field"><label>Current password</label><input class="input" type="password" name="c" required autocomplete="current-password"></div>
      <div class="grid" style="grid-template-columns:1fr 1fr;gap:12px"><div class="field"><label>New password</label><input class="input" type="password" name="n" required minlength="8" autocomplete="new-password"></div>
        <div class="field"><label>Repeat new password</label><input class="input" type="password" name="r" required minlength="8" autocomplete="new-password"></div></div>
      <span class="hint">At least 8 characters. Use something you don’t use anywhere else.</span><div id="pwm"></div>
      <div class="row" style="justify-content:flex-end"><button class="btn primary">Update password</button></div></form>
    <div class="grid" style="gap:10px;border-top:1px solid var(--line);padding-top:18px"><h4 style="font-size:15px">${ic('msg', 16)} Your chats</h4>
      <p class="hint">Chats are private to you. Deleting them removes the history and what the assistant remembers from it. It can’t be undone.</p>
      <div class="row"><button class="btn bad" id="delAll">${ic('trash', 16)} Delete all my chats</button></div></div>
    <div class="row" style="justify-content:space-between;border-top:1px solid var(--line);padding-top:16px"><span class="hint">Signed in as ${esc(S.me.email)}</span><button class="btn" id="so">${ic('out', 16)} Log out</button></div></div>`,
    { onMount: (el, close) => {
      $('#so', el).onclick = () => { close(); logout(); };
      $('#pw', el).onsubmit = async e => { e.preventDefault(); const f = e.target;
        if (f.n.value !== f.r.value) { $('#pwm', el).innerHTML = errBanner('The two new passwords are not the same.'); return; }
        try { await busy(e.submitter, () => api('/v1/auth/password', { method: 'POST', body: { current_password: f.c.value, new_password: f.n.value } })); f.reset(); $('#pwm', el).innerHTML = '<div class="banner ok">Password updated. Use it the next time you sign in.</div>'; }
        catch (err) { $('#pwm', el).innerHTML = errBanner(err); } };
      $('#delAll', el).onclick = () => { close(); modal('Delete all chats?', `<p style="color:var(--ink-2);margin-bottom:18px">All your chats will be deleted. This can’t be undone.</p><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn bad" data-ok>Delete everything</button></div>`,
        { onMount: (el2, close2) => { $('[data-x]', el2).onclick = close2; $('[data-ok]', el2).onclick = async () => { try { const r = await api('/v1/conversations', { method: 'DELETE' }); close2(); S.chats = []; newChat(); toast(`${r.deleted} chat${r.deleted === 1 ? '' : 's'} deleted`); } catch (err) { toast(err.message); } }; } }); };
    } });
}

/* ================= SIGN UP: people create their own account; an administrator or manager approves it ================= */
async function renderSignup() {
  let depts = []; try { depts = (await api('/v1/auth/signup-options')).departments; } catch (e) {}
  $('#app').innerHTML = `<div class="login"><form class="login-card" id="suForm" style="width:min(460px,100%)">
    <div class="brand"><span class="brand-mark">${LOGO}</span><span>Quixotic <b>AI</b></span></div>
    <p class="sub">Create your account. An administrator or manager approves it and decides which department information you can use.</p>
    <div id="suMsg"></div>
    <div class="grid" style="gap:12px">
      <div class="field"><label>Full name</label><input class="input" name="n" required minlength="2" maxlength="80" autocomplete="name" autofocus></div>
      <div class="grid" style="grid-template-columns:1fr 1fr;gap:12px"><div class="field"><label>Choose a username</label><input class="input" name="u" required minlength="3" maxlength="30" autocomplete="username" autocapitalize="none" placeholder="e.g. nadia.khan"></div>
        <div class="field"><label>Email</label><input class="input" type="email" name="m" required autocomplete="email"></div></div>
      <div class="grid" style="grid-template-columns:1fr 1fr;gap:12px"><div class="field"><label>Password</label><input class="input" type="password" name="p" required minlength="8" autocomplete="new-password"></div>
        <div class="field"><label>Repeat password</label><input class="input" type="password" name="r" required minlength="8" autocomplete="new-password"></div></div>
      <div class="field"><label>Department you work in</label><select class="select" name="d"><option value="">Not sure / not listed</option>${depts.map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select>
        <span class="hint">This is only a request. The person who approves you chooses your access.</span></div>
    </div>
    <button class="btn primary" style="width:100%;height:46px;margin-top:18px" id="suBtn">Request account</button>
    <p class="sub" style="margin:16px 0 0">Already approved? <a href="#" id="toLogin" style="color:var(--orange);font-weight:700">Sign in</a></p></form></div>`;
  $('#toLogin').onclick = e => { e.preventDefault(); renderLogin(); };
  $('#suForm').onsubmit = async e => {
    e.preventDefault(); const f = e.target, msg = $('#suMsg');
    if (f.p.value !== f.r.value) { msg.innerHTML = `<div class="banner err" style="margin-bottom:12px">The two passwords are not the same.</div>`; return; }
    try {
      await busy($('#suBtn'), () => api('/v1/auth/register', { method: 'POST', body: { full_name: f.n.value, username: f.u.value.trim().toLowerCase(), email: f.m.value.trim(), password: f.p.value, department_id: f.d.value || null } }));
      $('#app').innerHTML = `<div class="login"><div class="login-card" style="text-align:center"><div class="brand"><span class="brand-mark">${LOGO}</span><span>Quixotic <b>AI</b></span></div>
        <div class="empty" style="padding:18px 0"><div class="ico">${ic('check', 24)}</div><h3>Request sent</h3><p>An administrator or manager will review it. Once approved, sign in with your username <b>${esc(f.u.value.trim().toLowerCase())}</b> and your password.</p></div>
        <button class="btn primary" style="width:100%;height:46px" id="backLogin">Back to sign in</button></div></div>`;
      $('#backLogin').onclick = () => renderLogin();
    } catch (err) { msg.innerHTML = `<div class="banner err" style="margin-bottom:12px">${esc(err.message)}</div>`; }
  };
}

/* ================= login ================= */
function renderLogin(msg) {
  $('#app').innerHTML = `<div class="login"><form class="login-card" id="loginForm">
    <div class="brand"><span class="brand-mark">${LOGO}</span><span>Quixotic <b>AI</b></span></div>
    <p class="sub">Sign in to ask your company knowledge base.</p>
    ${msg ? `<div class="banner err" style="margin-bottom:14px">${esc(msg)}</div>` : ''}
    <div class="field" style="margin-bottom:14px"><label for="lid">Email or employee ID</label><input class="input" id="lid" autocomplete="username" required autofocus></div>
    <div class="field" style="margin-bottom:20px"><label for="lpw">Password</label><input class="input" id="lpw" type="password" autocomplete="current-password" required></div>
    <button class="btn primary" style="width:100%;height:46px" id="lbtn">Sign in</button>
    <p class="sub" style="margin:18px 0 0">New here? <a href="#" id="toSignup" style="color:var(--orange);font-weight:700">Create an account</a></p></form></div>`;
  $('#toSignup').onclick = e => { e.preventDefault(); renderSignup(); };
  $('#loginForm').onsubmit = async e => {
    e.preventDefault(); const b = $('#lbtn');
    try {
      await busy(b, async () => { b.textContent = 'Signing in…';
        const r = await api('/v1/auth/login', { method: 'POST', body: { identifier: $('#lid').value.trim(), password: $('#lpw').value } });
        S.token = r.access_token; lsSet('qb_token', S.token); await boot(); });
    } catch (err) { renderLogin(err.status === 401 ? 'Those details don’t match. Please try again.' : err.message); }
  };
}
function logout(expired) { S.token = null; S.me = null; S.chats = []; lsSet('qb_token', null); S.ask = { mode: 'general', scope: null, thread: [], busy: false, convId: null }; renderLogin(expired ? 'Your session has ended. Please sign in again.' : ''); }

async function boot() {
  if (!S.token) return renderLogin();
  try {
    S.me = await api('/v1/auth/me');
    const all = await api('/v1/departments');
    S.departments = (S.me.role === 'administrator' ? all.departments.filter(d => d.status === 'active')
      : all.departments.filter(d => S.me.department_ids.includes(d.id) && d.status === 'active')).map(d => ({ id: d.id, name: d.name }));
    if (rank() >= 2) { try { S.requests = (await api('/v1/access-requests')).requests.length; } catch (e) { S.requests = 0; } }
    if (rank() >= 2) { try { S.pending = (await api('/v1/knowledge?status=pending_review&limit=100')).items.length; } catch (e) { S.pending = 0; } }
    try { S.chats = (await api('/v1/conversations')).conversations; } catch (e) { S.chats = []; }
  } catch (e) { if (e.status === 401) return; return renderLogin(e.message); }
  renderApp();
}
window.addEventListener('hashchange', () => S.me && renderApp());

/* ================= ASK (matches the supplied design) ================= */
const MASCOT = `<svg class="mascot" viewBox="0 0 220 220" role="img" aria-label="Quixotic AI assistant"><defs>
  <linearGradient id="gw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#f3ede8"/></linearGradient>
  <linearGradient id="go" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff8f45"/><stop offset="1" stop-color="#ff5a00"/></linearGradient></defs>
  <path d="M58 200c0-26 24-40 52-40s52 14 52 40v20H58z" fill="url(#gw)" stroke="#eadfd6"/><circle cx="110" cy="190" r="9" fill="url(#go)"/>
  <path d="M40 98c0-44 31-68 70-68s70 24 70 68" fill="none" stroke="url(#go)" stroke-width="9" stroke-linecap="round"/>
  <rect x="24" y="84" width="28" height="56" rx="14" fill="url(#go)"/><rect x="168" y="84" width="28" height="56" rx="14" fill="url(#go)"/>
  <rect x="44" y="52" width="132" height="104" rx="48" fill="url(#gw)" stroke="#eadfd6"/><rect x="58" y="68" width="104" height="72" rx="32" fill="#1b1d2b"/>
  <path d="M81 103q9-15 19 0" fill="none" stroke="#ff8f45" stroke-width="6.5" stroke-linecap="round"/><path d="M120 103q9-15 19 0" fill="none" stroke="#ff8f45" stroke-width="6.5" stroke-linecap="round"/>
  <path d="M100 121q10 9 20 0" fill="none" stroke="#ff8f45" stroke-width="4.5" stroke-linecap="round"/>
  <path d="M186 132c0 28-20 42-50 43" fill="none" stroke="url(#go)" stroke-width="6" stroke-linecap="round"/><rect x="120" y="169" width="22" height="13" rx="6.5" fill="url(#go)"/></svg>`;
const WAVES = `<svg class="waves" viewBox="0 0 1000 380" preserveAspectRatio="none" aria-hidden="true"><path d="M0 120C180 40 300 200 500 120S820 40 1000 130"/><path d="M0 170C200 90 320 250 520 170S840 90 1000 180"/><path d="M0 230C220 150 340 310 540 230S860 150 1000 240"/></svg>`;
const SUGGESTIONS = [
  ['msg', 'Customer says too expensive', 'A customer says the price is too expensive. How should I respond?'],
  ['doc', 'Booking script', 'What is the booking script?'],
  ['shield', 'Refund policy', 'What is our refund policy?'],
  ['users', 'Lead qualification', 'How do I qualify a lead?'],
];
const BUBBLES = [['b1', 'l', 'doc', 'Scripts', 'Show me the script for '], ['b2', 'l', 'shield', 'Policies', 'What is our policy on '],
  ['b3', 'r', 'msg', 'Objections', 'How do I handle this objection: '], ['b4', 'r', 'doc', 'SOPs', 'What is the SOP for ']];
const MODES = [['general', 'General', 'Ask anything within your departments'], ['sales_coach', 'Sales coach', 'Objections, strategy and similar past cases'], ['search', 'Search only', 'Show matching knowledge without writing an answer']];

function composer(compact) {
  const A = S.ask, scopeName = A.scope || 'Company Knowledge';
  return `<div class="composer"><textarea id="q" rows="${compact ? 1 : 2}" placeholder="Ask Quixotic AI about scripts, objections, SOPs, and company knowledge..." aria-label="Your question"></textarea>
    <div class="crow"><button class="circle" data-pop="mode" aria-label="Options" title="Mode">${ic('plus', 20)}</button>
      <button class="pill" id="webBtn" title="Web search">${ic('globe', 17)}<span class="lbl">Web Search</span></button>
      <button class="pill ${A.scope ? 'on' : ''}" data-pop="scope">${ic('building', 17)}<span class="lbl">${esc(scopeName)}</span>${ic('chevd', 15)}</button>
      ${A.mode !== 'general' ? `<span class="chip orange">${MODES.find(m => m[0] === A.mode)[1]}</span>` : ''}
      <span class="spacer"></span><button class="circle" id="micBtn" aria-label="Voice input" title="Voice input">${ic('mic', 19)}</button>
      <button class="send" id="sendBtn" aria-label="Send" disabled>${ic('send', 20)}</button></div></div>`;
}
function openPop(kind, anchor) {
  $('.pop')?.remove(); const A = S.ask; const pop = document.createElement('div'); pop.className = 'pop';
  if (kind === 'mode') pop.innerHTML = `<div class="ph">Mode</div>${MODES.map(m => `<button data-mode="${m[0]}" class="${A.mode === m[0] ? 'sel' : ''}"><span>${m[1]}<small>${m[2]}</small></span>${A.mode === m[0] ? `<span class="tick">${ic('check', 16)}</span>` : ''}</button>`).join('')}`;
  else pop.innerHTML = `<div class="ph">Search in</div><button data-scope="" class="${!A.scope ? 'sel' : ''}"><span>Company Knowledge<small>Everything you are allowed to see</small></span>${!A.scope ? `<span class="tick">${ic('check', 16)}</span>` : ''}</button>
    ${S.departments.map(d => `<button data-scope="${esc(d.name)}" class="${A.scope === d.name ? 'sel' : ''}"><span>${esc(d.name)}</span>${A.scope === d.name ? `<span class="tick">${ic('check', 16)}</span>` : ''}</button>`).join('')}`;
  anchor.parentElement.append(pop);
  if (kind === 'scope') pop.style.left = (anchor.offsetLeft) + 'px';
  pop.onclick = e => { const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.mode) A.mode = b.dataset.mode; if ('scope' in b.dataset) A.scope = b.dataset.scope || null; renderAsk($('#view')); };
}
function bindComposer(root, compact) {
  const q = $('#q', root), send = $('#sendBtn', root);
  const grow = () => { q.style.height = 'auto'; q.style.height = Math.min(q.scrollHeight, 200) + 'px'; send.disabled = !q.value.trim() || S.ask.busy; };
  q.addEventListener('input', grow);
  q.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (q.value.trim() && !S.ask.busy) submit(q.value); } });
  send.onclick = () => q.value.trim() && !S.ask.busy && submit(q.value);
  $$('[data-pop]', root).forEach(b => b.onclick = e => { e.stopPropagation(); const had = $('.pop', b.parentElement); $('.pop')?.remove(); if (!had) openPop(b.dataset.pop, b); });
  $('#webBtn', root).onclick = () => toast('Web search isn’t available. Answers come only from your approved company knowledge.');
  $('#micBtn', root).onclick = () => toast('Voice input is planned for a later release.');
  if (!compact) q.focus();
  return q;
}
function renderAsk(view) {
  const A = S.ask;
  if (!A.thread.length) {
    refreshTop(false);
    view.innerHTML = `<div class="ask">${WAVES}<div class="hero">
      <h1>Ask <em>Quixotic AI</em><svg class="spark i" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 1l2.6 8.4L23 12l-8.4 2.6L12 23l-2.6-8.4L1 12l8.4-2.6z"/></svg></h1>
      <p class="lead">Get instant answers from your call center knowledge base — scripts, objections, SOPs, policies and more.</p>
      <div class="mascot-wrap">${BUBBLES.map(b => `<button class="bubble ${b[0]} ${b[1]}" data-fill="${esc(b[4])}">${ic(b[2], 18)}${b[3]}</button>`).join('')}${MASCOT}</div>
      ${composer(false)}
      <div class="try"><p>Try asking about...</p><div class="try-grid">${SUGGESTIONS.map((s, i) => `<button class="tcard" data-sug="${i}"><span class="ti">${ic(s[0], 20)}</span><span>${esc(s[1])}</span><span class="go">${ic('chevr', 18)}</span></button>`).join('')}</div></div></div></div>`;
    const q = bindComposer(view, false);
    $$('[data-sug]', view).forEach(b => b.onclick = () => submit(SUGGESTIONS[b.dataset.sug][2]));
    $$('[data-fill]', view).forEach(b => b.onclick = () => { q.value = b.dataset.fill; q.dispatchEvent(new Event('input')); q.focus(); q.setSelectionRange(q.value.length, q.value.length); });
    return;
  }
  refreshTop(true);
  view.innerHTML = `<div class="ask"><div class="chat"><div class="thread" id="thread">${A.thread.map(msgHTML).join('')}</div>
    <div class="dock">${composer(true)}<p class="fineprint">Answers come only from approved company knowledge.</p></div></div></div>`;
  bindComposer(view, true); bindThread(view);
  const t = $('#thread'); t.lastElementChild && t.lastElementChild.scrollIntoView({ block: 'end' });
  $('#q', view).focus();
}
const REASONS = ['Wrong answer', 'Not what I asked', 'Too long', 'Too short', 'Missing information'];
const reasonsHTML = (i, m) => m.helpful === false ? `<div class="reasons"><span class="hint">What was wrong? <span style="opacity:.8">(optional — it helps me learn)</span></span><div class="row" style="flex-wrap:wrap;gap:6px;margin-top:6px">${REASONS.map(r => `<button class="chipbtn ${(m.reasons || []).includes(r) ? 'on' : ''}" data-reason="${i}" data-r="${esc(r)}">${r}</button>`).join('')}</div></div>` : '';
const hitHTML = (r, k) => `<div class="hit"><div class="t"><span class="chip orange">${k + 1}</span>${esc(r.source)}</div><div style="color:var(--ink-2);font-size:14px">${esc(r.text)}</div></div>`;
const CONF = { high: ['High confidence', 'green'], medium: ['Medium confidence', 'amber'], low: ['Low confidence', 'red'] };
function msgHTML(m, i) {
  if (m.role === 'user') return `<div class="msg-u">${esc(m.text)}</div>`;
  const av = `<span class="av">${LOGO}</span>`;
  if (m.loading) return `<div class="msg-a">${av}<div class="body"><div class="typing"><i></i><i></i><i></i></div></div></div>`;
  if (m.error) return `<div class="msg-a">${av}<div class="body"><div class="banner err">${esc(m.error)}</div></div></div>`;
  if (m.kind === 'search') return `<div class="msg-a">${av}<div class="body">${m.results.length ? `<div class="label" style="margin-bottom:8px">Best match</div>${hitHTML(m.results[0], 0)}${m.results.length > 1 ? `<details class="more"><summary>Show ${m.results.length - 1} more match${m.results.length > 2 ? 'es' : ''}</summary><div class="hits">${m.results.slice(1).map((r, k) => hitHTML(r, k + 1)).join('')}</div></details>` : ''}`
    : `<div class="notice"><b>Nothing found.</b> No approved knowledge matches this search.</div>`}</div></div>`;
  const low = m.confidence === 'low' || m.found === false;
  const [cl, cc] = CONF[m.confidence] || CONF.low;
  let h = `<div class="msg-a">${av}<div class="body">`;
  h += low ? `<div class="notice"><b>${esc(m.answer.split('\n')[0])}</b>${m.answer.includes('\n') ? `<p style="margin-top:6px">${esc(m.answer.split('\n').slice(1).join(' ').trim())}</p>` : ''}</div>`
    : `<div class="answer">${esc(m.answer)}</div>`;
  h += `<div class="meta"><span class="chip ${cc} dot">${cl}</span>${m.historical ? `<span class="chip">${m.historical.similar} similar past cases · ${m.historical.successful} closed</span>` : ''}</div>`;
  if (m.sources?.length) { const one = s => `<span class="src">${ic('doc', 15)}${esc(s.title)}${s.section ? ` <small>· ${esc(s.section)}</small>` : ''} <small>· v${s.version}</small></span>`;
    h += `<div class="srcs">${m.sources.slice(0, 2).map(one).join('')}${m.sources.length > 2 ? `<details class="more inline"><summary>+${m.sources.length - 2} more source${m.sources.length > 3 ? 's' : ''}</summary><div class="srcs">${m.sources.slice(2).map(one).join('')}</div></details>` : ''}</div>`; }
  if (low) h += `<div class="fb" style="margin-top:14px">${rank() >= 1 ? `<button class="btn sm" data-missing="${i}">${ic('plus', 15)} Report missing knowledge</button>` : ''}<button class="btn sm" data-search="${i}">${ic('search', 15)} Search documents</button></div>`;
  else {
    if (m.mode === 'sales_coach') h += `<div class="outcome"><b>Outcome</b>${[['sale_closed', 'Sale closed'], ['sale_lost', 'Sale lost'], ['customer_still_deciding', 'Still deciding'], ['follow_up_required', 'Follow-up required']].map(o => `<label><input type="radio" name="o${i}" data-outcome="${o[0]}" data-i="${i}" ${m.outcome === o[0] ? 'checked' : ''}> ${o[1]}</label>`).join('')}</div>`;
    h += `<div class="fb"><button class="btn ghost sm" data-copy="${i}" title="Copy">${ic('copy', 15)}</button><button class="btn ghost sm" data-fb="up" data-i="${i}" title="Helpful" ${m.helpful === true ? 'style="color:var(--green)"' : ''}>${ic('up', 15)}</button><button class="btn ghost sm" data-fb="down" data-i="${i}" title="Not helpful" ${m.helpful === false ? 'style="color:var(--red)"' : ''}>${ic('down', 15)}</button></div>${reasonsHTML(i, m)}`;
  }
  return h + '</div></div>';
}
function bindThread(view) {
  const A = S.ask;
  view.onclick = async e => {
    const t = e.target.closest('[data-fb],[data-copy],[data-missing],[data-search],[data-outcome],[data-reason]'); if (!t) return;
    const m = A.thread[+(t.dataset.i ?? t.dataset.copy ?? t.dataset.missing ?? t.dataset.search ?? t.dataset.reason)]; if (!m) return;
    try {
      if (t.dataset.copy != null) { await navigator.clipboard?.writeText(m.answer); toast('Copied'); }
      else if (t.dataset.missing != null) { ssSet('qb_prefill', JSON.stringify({ title: m.question })); go('add'); }
      else if (t.dataset.search != null) { submit(m.question, 'search'); }      // one-off: later questions stay normal answers
      else if (t.dataset.fb) { const helpful = t.dataset.fb === 'up'; await api('/v1/feedback', { method: 'POST', body: { query_id: m.query_id, helpful } }); m.helpful = helpful; renderAsk(view); toast(helpful ? 'Thanks! I’ll remember what worked.' : 'Thanks — I’ll avoid this next time.'); }
      else if (t.dataset.reason != null) { const r = t.dataset.r; m.reasons = m.reasons || []; if (!m.reasons.includes(r)) { await api('/v1/feedback', { method: 'POST', body: { query_id: m.query_id, note: r } }); m.reasons.push(r); } renderAsk(view); toast('Noted: ' + r.toLowerCase()); }
      else if (t.dataset.outcome) { await api('/v1/feedback', { method: 'POST', body: { query_id: m.query_id, outcome: t.dataset.outcome } }); m.outcome = t.dataset.outcome; toast('Outcome saved'); }
    } catch (err) { toast(err.message); }
  };
}
function fromStored(c) {
  if (c.kind === 'search') return { role: 'ai', kind: 'search', question: c.question, results: c.results || [] };
  return { role: 'ai', kind: 'ask', mode: c.mode, question: c.question, query_id: c.query_id, answer: c.answer, confidence: c.confidence, sources: c.sources || [], historical: c.historical_cases, found: !c.actions };
}
async function loadChat(id) {
  const A = S.ask;
  try {
    const conv = await api(`/v1/conversations/${id}`);
    A.thread = conv.messages.map(m => m.role === 'user' ? { role: 'user', text: m.content.text } : fromStored(m.content));
    A.convId = conv.id; A.mode = conv.mode === 'sales_coach' ? 'sales_coach' : 'general';      // an old search-only chat never traps later questions in list mode
    const dep = conv.department_id && S.departments.find(d => d.id === conv.department_id); A.scope = dep ? dep.name : null;
  } catch (e) { toast(e.status === 404 ? 'That chat no longer exists.' : e.message); history.replaceState(null, '', '#/ask'); A.thread = []; A.convId = null; }
}
async function submit(text, forceMode) {
  const A = S.ask, q = text.trim(); if (!q || A.busy) return;
  A.busy = true; A.thread.push({ role: 'user', text: q }); A.thread.push({ role: 'ai', loading: true }); renderAsk($('#view'));
  const mode = forceMode || A.mode, body = { question: q, department: A.scope || undefined, conversation_id: A.convId || undefined };
  let m;
  try {
    if (mode === 'search') { const r = await api('/v1/search', { method: 'POST', body }); m = { role: 'ai', kind: 'search', question: q, results: r.results }; afterSaved(r); }
    else { const r = await api('/v1/ask', { method: 'POST', body: { ...body, mode: mode === 'sales_coach' ? 'sales_coach' : 'general' } });
      m = { role: 'ai', kind: 'ask', mode, question: q, query_id: r.query_id, answer: r.answer, confidence: r.confidence, sources: r.sources || [], historical: r.historical_cases, found: !r.actions }; afterSaved(r); }
  } catch (e) { m = { role: 'ai', error: e.message }; }
  A.thread[A.thread.length - 1] = m; A.busy = false;
  if (parseRoute().page === 'ask') renderAsk($('#view'));
}
function afterSaved(r) {      // the server saved the exchange: remember the chat id, update the address and the sidebar list
  if (!r.conversation_id) return; const A = S.ask;
  if (!A.convId) { A.convId = r.conversation_id; history.replaceState(null, '', '#/chat/' + A.convId); }
  loadChats();
}

/* ================= KNOWLEDGE ================= */
function knowledgeActions(v) {
  const r = rank(), mine = v.created_by === S.me.user_id, a = [];
  if (v.status === 'draft' && (mine || r >= 3)) a.push(['Submit for review', 'submit', 'primary']);
  if (v.status === 'pending_review' && r >= 2) { a.push(['Approve', 'approve', 'good']); a.push(['Reject', 'rejected', 'bad']); }
  if (v.status === 'approved' && r >= 2) a.push(['Activate', 'active', 'good']);
  if (r >= 1 && v.status !== 'draft') a.push(['New version', 'newversion', '']);
  if (v.status !== 'archived' && r >= 3) a.push(['Archive', 'archived', '']);
  return a;
}
async function transition(id, to) {
  if (to === 'submit') return api(`/v1/knowledge/${id}/transitions`, { method: 'POST', body: { to: 'submitted' } });
  if (to === 'approve') { await api(`/v1/knowledge/${id}/transitions`, { method: 'POST', body: { to: 'approved' } }); return api(`/v1/knowledge/${id}/transitions`, { method: 'POST', body: { to: 'active' } }); }
  return api(`/v1/knowledge/${id}/transitions`, { method: 'POST', body: { to } });
}
async function openKnowledge(id, refresh) {
  const v = await api(`/v1/knowledge/${id}`);
  const acts = knowledgeActions(v);
  drawer(`<div class="row" style="align-items:flex-start"><div><h2 style="font-size:21px;font-weight:800;letter-spacing:-.01em">${esc(v.title)}</h2><div class="row" style="margin-top:8px;flex-wrap:wrap;gap:6px">${statusChip(v.status)}${v.departments.map(d => `<span class="chip">${esc(d)}</span>`).join('')}</div></div><span class="spacer"></span><button class="btn ghost sm" data-close>${ic('x', 18)}</button></div>
    <h4 style="margin:22px 0 8px;font-size:14px">Information</h4>
    <div style="white-space:pre-wrap;background:var(--bg);border:1px solid var(--line);border-radius:14px;padding:14px;max-height:260px;overflow:auto;color:var(--ink-2)">${v.information ? esc(v.information) : '<span class="hint">This item is an uploaded document.</span>'}</div>
    <h4 style="margin:22px 0 8px;font-size:14px">Details</h4><dl class="kv"><dt>Version</dt><dd>${v.version}</dd><dt>Category</dt><dd>${esc(v.category || '—')}</dd><dt>Type</dt><dd>${esc(v.document_type || '—')}</dd><dt>Access</dt><dd>${esc(v.access_level || '—')}</dd><dt>Created</dt><dd>${fmtDate(v.created_at)}</dd><dt>Last updated</dt><dd>${fmtDate(v.updated_at)}</dd><dt>Reviewed</dt><dd>${v.reviewed_at ? fmtDate(v.reviewed_at) : '—'}</dd></dl>
    <h4 style="margin:22px 0 8px;font-size:14px">History</h4><div class="timeline">${(v.history || []).map(h => `<div class="tl"><i></i><div><b>${(STATUS[h.to_status] || [h.to_status])[0]}</b>${h.note ? ` — ${esc(h.note)}` : ''}<small>${fmtDate(h.at)}</small></div></div>`).join('')}</div>
    ${acts.length ? `<div class="row" style="margin-top:26px;flex-wrap:wrap">${acts.map(a => `<button class="btn ${a[2]}" data-act="${a[1]}">${a[0]}</button>`).join('')}</div>` : ''}
    <div id="dmsg" style="margin-top:12px"></div>`,
    (el, close) => {
      $('[data-close]', el).onclick = close;
      $$('[data-act]', el).forEach(b => b.onclick = async () => {
        const act = b.dataset.act;
        if (act === 'newversion') { close(); return newVersionModal(v, refresh); }
        try { await busy(b, () => transition(id, act)); toast('Done'); close(); refresh && refresh(); } catch (e) { $('#dmsg', el).innerHTML = errBanner(e); }
      });
    });
}
function newVersionModal(v, refresh) {
  modal(`New version of “${v.title}”`, `<div class="field"><label>Updated information</label><textarea class="textarea" id="nvText" style="min-height:200px">${esc(v.information || '')}</textarea></div>
    <p class="hint" style="margin:8px 0 16px">It starts as a draft. When it becomes active, the current version is archived automatically.</p><div id="nvErr"></div>
    <div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn primary" id="nvGo">Create draft</button></div>`,
    { onMount: (el, close) => { $('[data-x]', el).onclick = close;
      $('#nvGo', el).onclick = async e => { try { await busy(e.currentTarget, () => api(`/v1/knowledge/items/${v.item_id}/versions`, { method: 'POST', body: { information: $('#nvText', el).value, access_level: v.access_level } })); toast('Draft created'); close(); refresh && refresh(); } catch (err) { $('#nvErr', el).innerHTML = errBanner(err); } }; } });
}
async function pageKnowledge(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Knowledge</h1><p>Approved and in-progress company knowledge.</p></div>${rank() >= 1 ? `<a class="btn primary" href="#/add" style="text-decoration:none">${ic('plus', 17)} Add information</a>` : ''}</div>
    <div class="row" style="margin-bottom:14px;flex-wrap:wrap"><div style="position:relative;flex:1;min-width:220px"><input class="input" id="kq" placeholder="Search by title…" style="padding-left:40px"><span style="position:absolute;left:13px;top:12px;color:var(--muted)">${ic('search')}</span></div>
    <select class="select" id="ks" style="width:190px"><option value="">All statuses</option>${Object.entries(STATUS).map(([k, v]) => `<option value="${k}">${v[0]}</option>`).join('')}</select></div><div id="klist">${loading()}</div></div>`;
  let items = [];
  const draw = () => {
    const q = $('#kq').value.toLowerCase(), rows = items.filter(i => !q || i.title.toLowerCase().includes(q));
    $('#klist').innerHTML = rows.length ? `<div class="table-wrap"><table><thead><tr><th>Title</th><th>Departments</th><th>Category</th><th>Status</th><th>Version</th><th>Updated</th></tr></thead><tbody>${rows.map(i => `<tr class="click" data-id="${i.id}"><td><b>${esc(i.title)}</b></td><td>${esc(i.departments.join(', ') || '—')}</td><td>${esc(i.category || '—')}</td><td>${statusChip(i.status)}</td><td>v${i.version}</td><td>${fmtDate(i.updated_at)}</td></tr>`).join('')}</tbody></table></div>`
      : emptyState('book', items.length ? 'No matches' : 'No knowledge yet', items.length ? 'Try a different search or status.' : 'Add the first piece of knowledge to get started.', rank() >= 1 && !items.length ? '<a class="btn primary" href="#/add" style="text-decoration:none">Add information</a>' : '');
    $$('tr[data-id]', view).forEach(tr => tr.onclick = () => openKnowledge(tr.dataset.id, load).catch(e => toast(e.message)));
  };
  const load = async () => { try { items = (await api('/v1/knowledge?limit=200' + ($('#ks').value ? '&status=' + $('#ks').value : ''))).items; draw(); } catch (e) { $('#klist').innerHTML = errBanner(e); } };
  $('#kq').oninput = draw; $('#ks').onchange = load; load();
}

/* ================= ADD INFORMATION ================= */
async function pageAdd(view) {
  const pre = (() => { try { return JSON.parse(ssGet('qb_prefill') || 'null'); } catch (e) { return null; } })(); ssSet('qb_prefill', null);
  let tab = 0; const isAdmin = rank() >= 3;
  const draw = () => {
    view.innerHTML = `<div class="page" style="max-width:820px"><div class="page-head"><div><h1>Add information</h1><p>${isAdmin ? 'Add knowledge directly, or send it through review.' : 'Your submission is reviewed before it becomes official.'}</p></div></div>
      <div class="tabs"><button class="${tab === 0 ? 'on' : ''}" data-t="0">Write</button><button class="${tab === 1 ? 'on' : ''}" data-t="1">Upload document</button></div>
      <form class="card grid" id="af" style="gap:18px">
        <div class="field"><label>Title</label><input class="input" name="title" required value="${esc(tab === 0 && pre ? pre.title : '')}" placeholder="e.g. Refund policy"></div>
        <div class="field"><label>Department</label><div>${deptChecks('dept', S.departments)}</div></div>
        <div class="grid" style="grid-template-columns:1fr 1fr;gap:14px"><div class="field"><label>Category</label><input class="input" name="category" placeholder="e.g. Pricing"></div>
          <div class="field"><label>Type <span class="hint">(optional)</span></label><input class="input" name="document_type" placeholder="e.g. policy, sop, script"></div></div>
        <div class="field"><label>Access</label><input class="input" name="access" placeholder="e.g. Sales + Managers"><span class="hint">Who this is meant for. Visibility follows the departments you pick.</span></div>
        ${tab === 0 ? `<div class="field"><label>Information</label><textarea class="textarea" name="info" required style="min-height:220px" placeholder="Write the knowledge here…"></textarea></div>`
        : `<div class="field"><label>File</label><label class="card" id="drop" style="border:2px dashed var(--orange);box-shadow:none;text-align:center;background:var(--orange-50);cursor:pointer;display:block"><div style="color:var(--orange)">${ic('cloud', 34)}</div><b id="dropName">Choose a file or drop it here</b><div class="hint">PDF, DOCX, TXT, Markdown, JSON or CSV</div><input type="file" name="file" id="fileIn" accept=".pdf,.docx,.txt,.md,.markdown,.json,.csv" hidden required></label></div>`}
        ${isAdmin && tab === 1 ? `<div class="field"><label>Status</label><select class="select" name="status"><option value="draft">Send for review</option><option value="active">Publish now</option></select></div>` : ''}
        <div id="afMsg"></div>
        <div class="row" style="justify-content:flex-end;flex-wrap:wrap">${tab === 0 ? `<button type="submit" class="btn" data-mode="draft">Save as draft</button><button type="submit" class="btn primary" data-mode="submit">${isAdmin ? 'Send for review' : 'Submit for review'}</button>${isAdmin ? '<button type="submit" class="btn good" data-mode="publish">Publish now</button>' : ''}` : `<button type="submit" class="btn primary" data-mode="upload">${ic('cloud', 17)} Upload</button>`}</div></form></div>`;
    $$('[data-t]', view).forEach(b => b.onclick = () => { tab = +b.dataset.t; draw(); });
    const f = $('#fileIn'); if (f) { f.onchange = () => { $('#dropName').textContent = f.files[0]?.name || 'Choose a file or drop it here'; };
      const d = $('#drop'); d.ondragover = e => { e.preventDefault(); }; d.ondrop = e => { e.preventDefault(); f.files = e.dataTransfer.files; f.onchange(); }; }
    let mode = ''; $$('#af button[type=submit]').forEach(b => b.onclick = () => mode = b.dataset.mode);
    $('#af').onsubmit = async e => {
      e.preventDefault(); const form = e.target, btn = e.submitter || $('#af button[type=submit]'), dept = checked(form, 'dept'), msg = $('#afMsg');
      if (!dept.length) { msg.innerHTML = errBanner('Pick at least one department.'); return; }
      try {
        await busy(btn, async () => {
          if (tab === 1) {
            const fd = new FormData(); fd.append('file', form.file.files[0]); fd.append('department_ids', dept.join(',')); fd.append('title', form.title.value);
            ['category', 'document_type'].forEach(k => form[k].value && fd.append(k, form[k].value)); if (form.access.value) fd.append('access_level', form.access.value);
            fd.append('status', form.status ? form.status.value : 'draft'); await api('/v1/documents', { method: 'POST', form: fd });
            msg.innerHTML = `<div class="banner ok">Uploaded. It is being processed in the background — see <a href="#/documents">Documents</a>.</div>`; form.reset(); $('#dropName').textContent = 'Choose a file or drop it here';
          } else {
            const r = await api('/v1/knowledge', { method: 'POST', body: { title: form.title.value, department_ids: dept, category: form.category.value || null, document_type: form.document_type.value || null, access_level: form.access.value || null, information: form.info.value } });
            if (mode !== 'draft') await api(`/v1/knowledge/${r.version_id}/transitions`, { method: 'POST', body: { to: 'submitted' } });
            if (mode === 'publish') { await api(`/v1/knowledge/${r.version_id}/transitions`, { method: 'POST', body: { to: 'approved' } }); await api(`/v1/knowledge/${r.version_id}/transitions`, { method: 'POST', body: { to: 'active' } }); }
            msg.innerHTML = `<div class="banner ok">${mode === 'draft' ? 'Saved as a draft.' : mode === 'publish' ? 'Published.' : 'Submitted for review.'} <a href="#/knowledge">View in Knowledge</a></div>`; form.reset();
          }
        });
      } catch (err) { msg.innerHTML = errBanner(err); }
    };
  };
  draw();
}

/* ================= DOCUMENTS ================= */
async function pageDocuments(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Documents</h1><p>Uploaded files and whether they are ready to answer questions.</p></div><a class="btn primary" href="#/add" style="text-decoration:none" id="up">${ic('cloud', 17)} Upload document</a></div><div id="dl">${loading()}</div></div>`;
  const PS = { pending: ['Waiting', 'amber'], processing: ['Processing', 'blue'], ready: ['Ready', 'green'], failed: ['Failed', 'red'] };
  const load = async () => {
    try {
      const docs = (await api('/v1/documents?limit=200')).documents; if (parseRoute().page !== 'documents') return clearInterval(S.timer);
      $('#dl').innerHTML = docs.length ? `<div class="table-wrap"><table><thead><tr><th>File</th><th>Departments</th><th>Status</th><th>Processing</th><th>Size</th><th>Updated</th>${rank() >= 3 ? '<th></th>' : ''}</tr></thead><tbody>${docs.map(d => { const [pl, pc] = PS[d.processing_status] || [d.processing_status, ''];
        return `<tr><td><b>${esc(d.title)}</b><div class="hint">${esc(d.filename)}</div></td><td>${esc(d.departments.join(', '))}</td><td>${statusChip(d.status)}</td><td><span class="chip ${pc} dot">${pl}</span>${d.processing_error ? `<div class="hint" style="color:var(--red)">${esc(d.processing_error)}</div>` : ''}</td><td>${d.size_bytes ? (d.size_bytes / 1048576).toFixed(1) + ' MB' : '—'}</td><td>${fmtDate(d.updated_at)}</td>${rank() >= 3 ? `<td><button class="btn ghost sm" data-del="${d.id}" title="Delete">${ic('trash', 16)}</button></td>` : ''}</tr>`; }).join('')}</tbody></table></div>`
        : emptyState('doc', 'No documents yet', 'Upload a PDF, Word, text, Markdown, JSON or CSV file.', '<a class="btn primary" href="#/add">Upload document</a>');
      $$('[data-del]', view).forEach(b => b.onclick = () => modal('Delete this document?', `<p style="color:var(--ink-2);margin-bottom:18px">The file, its text and its place in answers are removed. This cannot be undone.</p><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn bad" data-ok>Delete</button></div>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = async () => { try { await api(`/v1/documents/${b.dataset.del}`, { method: 'DELETE' }); close(); toast('Deleted'); load(); } catch (e) { toast(e.message); } }; } }));
      if (docs.some(d => ['pending', 'processing'].includes(d.processing_status))) { clearInterval(S.timer); S.timer = setInterval(load, 4000); } else clearInterval(S.timer);
    } catch (e) { $('#dl').innerHTML = errBanner(e); }
  };
  load();
}

/* ================= SALES MEMORY (PRD §16-§17: past sales chats, imported per department) ================= */
async function pageSales(view) {
  view.innerHTML = `<div class="page" style="max-width:980px"><div class="page-head"><div><h1>Sales memory</h1><p>Past sales chats the AI learns from. Each file is used only by people in the department you choose.</p></div></div>
    <form class="card grid" id="sf" style="gap:18px;margin-bottom:22px">
      <div class="field"><label>Department</label><select class="select" name="dept" required><option value="">Choose who these chats are for…</option>${S.departments.map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Chats file (JSON)</label><label class="card" id="sdrop" style="border:2px dashed var(--orange);box-shadow:none;text-align:center;background:var(--orange-50);cursor:pointer;display:block"><div style="color:var(--orange)">${ic('cloud', 34)}</div><b id="sName">Choose a JSON file or drop it here</b><div class="hint" id="sDetect">One object per message: customer_message, agent_response, scenario, outcome…</div><input type="file" name="file" id="sIn" accept=".json" hidden required></label></div>
      <div id="sMsg"></div>
      <div class="row" style="justify-content:flex-end"><button type="submit" class="btn primary">${ic('cloud', 17)} Process conversations</button></div></form>
    <h3 style="margin-bottom:10px">Imports</h3><div id="sl">${loading()}</div></div>`;
  const f = $('#sIn');
  f.onchange = async () => {
    const file = f.files[0]; $('#sName').textContent = file ? file.name : 'Choose a JSON file or drop it here'; if (!file) return;
    try { const d = JSON.parse(await file.text()); const recs = Array.isArray(d) ? d : [];
      $('#sDetect').textContent = recs.length ? `Detected: ${new Set(recs.map(r => r.conversation_id)).size.toLocaleString()} conversations, ${recs.length.toLocaleString()} messages` : 'This file is not a list of chat records.';
    } catch (e) { $('#sDetect').textContent = 'This file is not valid JSON.'; }
  };
  const d = $('#sdrop'); d.ondragover = e => e.preventDefault(); d.ondrop = e => { e.preventDefault(); f.files = e.dataTransfer.files; f.onchange(); };
  $('#sf').onsubmit = async e => {
    e.preventDefault(); const form = e.target, btn = e.submitter, msg = $('#sMsg');
    try { await busy(btn, async () => {
      const fd = new FormData(); fd.append('file', form.file.files[0]); fd.append('department_id', form.dept.value);
      await api('/v1/sales-memory/imports', { method: 'POST', form: fd });
      msg.innerHTML = '<div class="banner ok">Uploaded. The chats are being processed below; large files take a few minutes.</div>'; form.reset();
      $('#sName').textContent = 'Choose a JSON file or drop it here'; $('#sDetect').textContent = ''; load(); }); } catch (err) { msg.innerHTML = errBanner(err); }
  };
  const ST = { queued: ['Waiting', 'amber'], running: ['Processing', 'blue'], succeeded: ['Ready', 'green'], failed: ['Failed', 'red'] };
  const load = async () => {
    try {
      const rows = (await api('/v1/sales-memory/imports')).imports; if (parseRoute().page !== 'sales') return clearInterval(S.timer);
      $('#sl').innerHTML = rows.length ? `<div class="table-wrap"><table><thead><tr><th>File</th><th>Department</th><th>Status</th><th>Chats learned</th><th>Uploaded</th><th></th></tr></thead><tbody>${rows.map(r => { const [l, c] = ST[r.status] || [r.status, ''];
        const prog = r.status === 'running' && r.progress_total ? ` ${Math.round(100 * r.progress_done / r.progress_total)}%` : '';
        return `<tr><td><b>${esc(r.filename || 'chats.json')}</b></td><td>${esc(r.department || '—')}</td><td><span class="chip ${c} dot">${l}${prog}</span>${r.error ? `<div class="hint" style="color:var(--red)">${esc(r.error)}</div>` : ''}</td><td>${Number(r.stored).toLocaleString()}</td><td>${fmtDate(r.created_at)}</td><td>${['succeeded', 'failed'].includes(r.status) && r.stored > 0 ? `<button class="btn ghost sm" data-del="${r.id}" title="Remove these chats">${ic('trash', 16)}</button>` : ''}</td></tr>`; }).join('')}</tbody></table></div>`
        : emptyState('msg', 'No chats imported yet', 'Upload a JSON file of past sales chats and choose the department that should learn from it.');
      $$('[data-del]', view).forEach(b => b.onclick = () => modal('Remove these chats?', `<p style="color:var(--ink-2);margin-bottom:18px">The AI stops using the chats from this file. You can upload the file again later.</p><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn bad" data-ok>Remove</button></div>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = async () => { try { await api(`/v1/sales-memory/imports/${b.dataset.del}`, { method: 'DELETE' }); close(); toast('Removed'); load(); } catch (e) { toast(e.message); } }; } }));
      if (rows.some(r => ['queued', 'running'].includes(r.status))) { clearInterval(S.timer); S.timer = setInterval(load, 4000); } else clearInterval(S.timer);
    } catch (e) { $('#sl').innerHTML = errBanner(e); }
  };
  load();
}

/* ================= APPROVALS ================= */
async function pageApprovals(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Approvals</h1><p>Review knowledge before it becomes official.</p></div></div><div id="al">${loading()}</div></div>`;
  const load = async () => {
    try {
      const items = (await api('/v1/knowledge?status=pending_review&limit=200')).items; S.pending = items.length; const nb = $('.navitem[href="#/approvals"]');
      if (nb) { $('.count', nb)?.remove(); if (items.length) nb.insertAdjacentHTML('beforeend', `<span class="count">${items.length}</span>`); }
      $('#al').innerHTML = items.length ? `<div class="grid">${items.map(i => `<div class="card"><div class="row" style="align-items:flex-start;flex-wrap:wrap"><div style="flex:1;min-width:220px"><b style="font-size:16px">${esc(i.title)}</b><div class="row" style="gap:6px;margin:6px 0;flex-wrap:wrap">${i.departments.map(d => `<span class="chip">${esc(d)}</span>`).join('')}<span class="hint">v${i.version} · submitted ${fmtDate(i.updated_at)}</span></div>
        <p style="color:var(--ink-2);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden">${esc(i.information || 'Uploaded document')}</p></div>
        <div class="row"><button class="btn sm" data-view="${i.id}">View</button><button class="btn good sm" data-ok="${i.id}">${ic('check', 15)} Approve</button><button class="btn bad sm" data-no="${i.id}">${ic('x', 15)} Reject</button></div></div></div>`).join('')}</div>`
        : emptyState('check', 'All caught up', 'There is nothing waiting for your review.');
      $$('[data-view]', view).forEach(b => b.onclick = () => openKnowledge(b.dataset.view, load).catch(e => toast(e.message)));
      $$('[data-ok]', view).forEach(b => b.onclick = async () => { try { await busy(b, () => transition(b.dataset.ok, 'approve')); toast('Approved and active'); load(); } catch (e) { toast(e.message); } });
      $$('[data-no]', view).forEach(b => b.onclick = async () => { try { await busy(b, () => transition(b.dataset.no, 'rejected')); toast('Rejected'); load(); } catch (e) { toast(e.message); } });
    } catch (e) { $('#al').innerHTML = errBanner(e); }
  };
  load();
}

/* ================= ACCESS REQUESTS: approve people who created their own account ================= */
async function pageRequests(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Access requests</h1><p>People who created their own account. Decide their role and which departments’ information they can use.</p></div></div><div id="rl">${loading()}</div></div>`;
  const isAdmin = rank() >= 3;
  const load = async () => {
    try {
      const [rq, ds] = await Promise.all([api('/v1/access-requests').then(r => r.requests), api('/v1/departments').then(r => r.departments.filter(d => d.status === 'active'))]);
      S.requests = rq.length; const nb = $('.navitem[href="#/requests"]'); if (nb) { $('.count', nb)?.remove(); if (rq.length) nb.insertAdjacentHTML('beforeend', `<span class="count">${rq.length}</span>`); }
      const grantable = isAdmin ? ds : ds.filter(d => S.me.department_ids.includes(d.id)), byId = Object.fromEntries(rq.map(r => [r.id, r]));
      $('#rl').innerHTML = rq.length ? `<div class="table-wrap"><table><thead><tr><th>Person</th><th>Username</th><th>Asked for</th><th>Requested</th><th></th></tr></thead><tbody>${rq.map(r => `<tr><td><b>${esc(r.full_name)}</b><div class="hint">${esc(r.email)}</div></td><td>${esc(r.username)}</td><td>${r.requested_department ? `<span class="chip">${esc(r.requested_department)}</span>` : '<span class="hint">No department chosen</span>'}</td><td>${fmtDate(r.created_at)}</td>
        <td><div class="row" style="justify-content:flex-end"><button class="btn good sm" data-ok="${r.id}">${ic('check', 15)} Approve</button><button class="btn bad sm" data-no="${r.id}">${ic('x', 15)} Reject</button></div></td></tr>`).join('')}</tbody></table></div>`
        : emptyState('check', 'No requests waiting', 'When someone creates an account, it appears here for approval.');
      $$('[data-no]', view).forEach(b => b.onclick = () => modal('Reject this request?', `<p style="color:var(--ink-2);margin-bottom:18px"><b>${esc(byId[b.dataset.no].full_name)}</b> will not be able to sign in.</p><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn bad" data-ok>Reject</button></div>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = async () => { try { await api(`/v1/access-requests/${b.dataset.no}/reject`, { method: 'POST' }); close(); toast('Rejected'); load(); } catch (e) { toast(e.message); } }; } }));
      $$('[data-ok]', view).forEach(b => b.onclick = () => { const r = byId[b.dataset.ok];
        modal(`Approve ${r.full_name}`, `<form id="af2" class="grid" style="gap:16px"><div class="field"><label>Role</label><select class="select" name="r">${(isAdmin ? Object.keys(ROLE_LABEL) : ['employee', 'contributor']).map(x => `<option value="${x}">${ROLE_LABEL[x]}</option>`).join('')}</select></div>
          <div class="field"><label>Can see knowledge of <span class="hint">(at least one)</span></label><div>${deptChecks('d', grantable, r.requested_department_id && grantable.some(d => d.id === r.requested_department_id) ? [r.requested_department_id] : [])}</div>
          ${isAdmin ? '' : '<span class="hint">You can only give access to departments you belong to.</span>'}</div><div id="am"></div>
          <div class="row" style="justify-content:flex-end"><button type="button" class="btn" data-x>Cancel</button><button class="btn good">Approve</button></div></form>`,
          { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('#af2', el).onsubmit = async e => { e.preventDefault(); const ids = checked(el, 'd');
            if (!ids.length) { $('#am', el).innerHTML = errBanner('Tick at least one department.'); return; }
            try { await busy(e.submitter, () => api(`/v1/access-requests/${r.id}/approve`, { method: 'POST', body: { role: e.target.r.value, department_ids: ids } })); close(); toast(`${r.full_name} can now sign in`); load(); } catch (err) { $('#am', el).innerHTML = errBanner(err); } }; } }); });
    } catch (e) { $('#rl').innerHTML = errBanner(e); }
  };
  load();
}

/* ================= DASHBOARD ================= */
async function pageDashboard(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Dashboard</h1><p>${rank() >= 3 ? 'Company-wide activity.' : 'Activity in the departments you manage.'}</p></div></div><div id="dd">${loading()}</div></div>`;
  try {
    const d = await api('/v1/dashboard');
    const tiles = [['Knowledge sections', d.knowledge_chunks], ['Departments', d.departments], ['Questions this week', d.questions_this_week], ['Answers found', d.retrieval_success == null ? '—' : Math.round(d.retrieval_success * 100) + '%'], ['Pending approvals', d.pending_approvals]];
    const list = (arr, empty, fn) => arr.length ? arr.map(fn).join('') : `<p class="hint" style="padding:10px 0">${empty}</p>`;
    $('#dd').innerHTML = `<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr))">${tiles.map(t => `<div class="card stat"><span class="n">${t[1]}</span><span class="l">${t[0]}</span></div>`).join('')}</div>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:16px">
      <div class="card"><b>Recent questions</b><div style="margin-top:8px">${list(d.recent_questions, 'No questions yet.', q => `<div class="row" style="padding:10px 0;border-top:1px solid var(--line)"><span style="flex:1">${esc(q.original_query)}</span><span class="chip ${q.knowledge_found ? 'green' : 'red'}">${q.knowledge_found ? 'Answered' : 'Not found'}</span><span class="hint">${fmtDate(q.created_at)}</span></div>`)}</div></div>
      <div class="card"><b>Recently updated knowledge</b><div style="margin-top:8px">${list(d.recently_updated_knowledge, 'Nothing active yet.', k => `<div class="row" style="padding:10px 0;border-top:1px solid var(--line)"><span style="flex:1">${esc(k.title)} <span class="hint">v${k.version}</span></span><span class="hint">${fmtDate(k.updated_at)}</span></div>`)}</div></div>
      <div class="card"><b>Most used sources</b><div style="margin-top:8px">${list(d.most_used_sources, 'Sources appear once questions are answered.', s => `<div class="row" style="padding:10px 0;border-top:1px solid var(--line)"><span style="flex:1">${esc(s.title)}</span><span class="chip">${s.uses} uses</span></div>`)}</div></div></div>`;
  } catch (e) { $('#dd').innerHTML = errBanner(e); }
}

/* ================= INSIGHTS ================= */
async function qualityTab(el) {
  const q = await api('/v1/answer-quality?days=30'), n = q.up + q.down, pct = (u, d) => (u + d) ? Math.round(100 * u / (u + d)) + '%' : '—';
  const label = { high: 'High', medium: 'Medium', low: 'Low' };
  const tbl = (title, rows, first) => `<div class="card"><b>${title}</b>${rows.length ? `<div class="table-wrap" style="border:0;margin-top:8px"><table style="min-width:0;width:100%"><thead><tr><th>${first}</th><th>Rated</th><th>Helpful</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.k)}</td><td>${r.up + r.down}</td><td>${pct(r.up, r.down)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="hint" style="margin-top:8px">Nothing rated yet.</p>'}</div>`;
  const srcs = (title, rows) => `<div class="card"><b>${title}</b>${rows.length ? `<div style="margin-top:8px">${rows.map(r => `<div class="row" style="padding:9px 0;border-top:1px solid var(--line)"><span style="flex:1">${esc(r.title || '—')}${r.section ? ` <span class="hint">· ${esc(r.section)}</span>` : ''}</span><span class="chip green">${r.up} 👍</span><span class="chip red">${r.down} 👎</span></div>`).join('')}</div>` : '<p class="hint" style="margin-top:8px">Nothing yet.</p>'}</div>`;
  el.innerHTML = `${q.learning_enabled ? '' : '<div class="banner err" style="margin-bottom:14px">Learning from ratings is switched off (QB_FEEDBACK_LEARNING=false). Ratings are still collected.</div>'}
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr))"><div class="card stat"><span class="n">${n}</span><span class="l">Rated answers (30 days)</span></div><div class="card stat"><span class="n">${pct(q.up, q.down)}</span><span class="l">Rated helpful</span></div><div class="card stat"><span class="n">${q.up}</span><span class="l">👍 Helpful</span></div><div class="card stat"><span class="n">${q.down}</span><span class="l">👎 Not helpful</span></div></div>
    <div class="card" style="margin-top:16px"><b>How the system learns from 👍 / 👎</b><p class="hint" style="margin-top:6px">Passages that keep getting 👍 rank a little higher; passages that keep getting 👎 rank a little lower (at least 3 ratings, only a few places, nothing is ever hidden). Each person’s own ratings also teach the assistant their style. It never edits your knowledge and never trains a model — you decide what to fix, using the lists below.</p>
      <div class="row" style="margin-top:10px"><button class="btn sm" id="rstLearn">Reset what it has learned</button></div></div>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:16px">${tbl('Does the confidence label match reality?', q.by_confidence.map(r => ({ ...r, k: (label[r.k] || r.k) + ' confidence' })), 'Label shown')}${tbl('By language', q.by_language.map(r => ({ ...r, k: (r.k || '').replace('_', ' ') })), 'Language')}</div>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:16px">${srcs('Sources people rate down — review these first', q.weakest_sources)}${srcs('Sources people rate up', q.best_sources)}</div>
    <div class="card" style="margin-top:16px"><b>Recent 👎 answers</b>${q.recent_not_helpful.length ? q.recent_not_helpful.map(b => `<div style="padding:12px 0;border-top:1px solid var(--line);margin-top:8px"><div class="row" style="flex-wrap:wrap"><b style="flex:1;min-width:200px">${esc(b.original_query)}</b><span class="chip">${esc(label[b.confidence] || b.confidence || '')} confidence</span><span class="hint">${fmtDate(b.created_at)}</span></div>
        <p class="hint" style="margin-top:4px">${esc(b.answer)}${b.answer.length >= 240 ? '…' : ''}</p>${b.note ? `<p style="margin-top:4px;color:var(--red)">Reason: ${esc(b.note)}</p>` : ''}<div class="row" style="margin-top:6px"><button class="btn sm" data-add="${esc(b.original_query)}">Add missing knowledge</button></div></div>`).join('') : '<p class="hint" style="margin-top:8px">No 👎 yet.</p>'}</div>`;
  $$('[data-add]', el).forEach(b => b.onclick = () => { ssSet('qb_prefill', JSON.stringify({ title: b.dataset.add })); go('add'); });
  $('#rstLearn', el).onclick = () => modal('Reset what the system has learned?', `<p style="color:var(--ink-2);margin-bottom:18px">Ratings given until now stop influencing the order of passages. Nothing is deleted and nobody’s account changes. People can still rate answers from now on.</p><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn bad" data-ok>Reset</button></div>`,
    { onMount: (m, close) => { $('[data-x]', m).onclick = close; $('[data-ok]', m).onclick = async () => { try { await api('/v1/learning/reset', { method: 'POST' }); close(); toast('Learning reset'); qualityTab(el); } catch (e) { toast(e.message); } }; } });
}
async function pageInsights(view) {
  let tab = 0;
  const draw = async () => {
    view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Insights</h1><p>Find the gaps in your knowledge.</p></div></div><div class="tabs"><button class="${tab === 0 ? 'on' : ''}" data-t="0">Failed questions</button><button class="${tab === 1 ? 'on' : ''}" data-t="1">Knowledge health</button><button class="${tab === 2 ? 'on' : ''}" data-t="2">Answer quality</button></div><div id="ib">${loading()}</div></div>`;
    $$('[data-t]', view).forEach(b => b.onclick = () => { tab = +b.dataset.t; draw(); });
    try {
      if (tab === 2) { await qualityTab($('#ib')); return; }
      if (tab === 0) {
        const f = (await api('/v1/failed-questions')).failed_questions;
        $('#ib').innerHTML = f.length ? `<div class="table-wrap"><table><thead><tr><th>Question</th><th>Language</th><th>Confidence</th><th>Asked</th><th></th></tr></thead><tbody>${f.map(q => `<tr><td><b>${esc(q.original_query)}</b></td><td>${esc((q.language || '').replace('_', ' '))}</td><td><span class="chip red">${esc(q.confidence || 'low')}</span></td><td>${fmtDate(q.created_at)}</td><td><div class="row"><button class="btn sm" data-add="${esc(q.original_query)}">Add missing knowledge</button><button class="btn sm" data-teach="${esc(q.original_query)}">Teach a word</button></div></td></tr>`).join('')}</tbody></table></div>`
          : emptyState('check', 'No failed questions', 'Every question so far found an answer.');
        $$('[data-add]', view).forEach(b => b.onclick = () => { ssSet('qb_prefill', JSON.stringify({ title: b.dataset.add })); go('add'); });
        $$('[data-teach]', view).forEach(b => b.onclick = () => teachModal(b.dataset.teach, null));
      } else {
        const h = await api('/v1/knowledge-health');
        const rows = [['Active documents', h.active_documents], ['Outdated (expired)', h.outdated_documents], ['Not reviewed in 6 months', h.not_reviewed_over_6_months], ['No owner assigned', h.no_owner_assigned], ['Potential duplicates', h.potential_duplicates], ['Conflicting policies', h.conflicting_policies]];
        $('#ib').innerHTML = `<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">${rows.map(r => `<div class="card stat"><span class="n">${r[1] == null ? '—' : r[1]}</span><span class="l">${r[0]}</span>${r[1] == null ? '<span class="hint">Not tracked yet</span>' : ''}</div>`).join('')}</div>`;
      }
    } catch (e) { $('#ib').innerHTML = errBanner(e); }
  };
  draw();
}

/* ================= USERS ================= */
async function pageUsers(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Users</h1><p>Who can sign in, and which knowledge each person can see — access follows departments.</p></div><button class="btn primary" id="inv">${ic('plus', 17)} Add user</button></div>
    <div class="row" style="margin-bottom:12px;flex-wrap:wrap"><div style="position:relative;flex:1;min-width:220px"><input class="input" id="uq" placeholder="Search by name, email or employee ID…" style="padding-left:40px"><span style="position:absolute;left:13px;top:12px;color:var(--muted)">${ic('search')}</span></div>
      <select class="select" id="ur" style="width:160px"><option value="">All roles</option>${Object.keys(ROLE_LABEL).map(r => `<option value="${r}">${ROLE_LABEL[r]}</option>`).join('')}</select>
      <select class="select" id="ud" style="width:200px"></select></div>
    <div id="bulk"></div><div id="ul">${loading()}</div></div>`;
  let users = [], depts = [], byId = {}; const sel = new Set(); let q = '', role = '', dept = '';
  const shown = () => users.filter(u => (!role || u.role === role)
    && (!dept || (dept === '_none' ? !u.department_ids.length : u.department_ids.includes(dept)))
    && (!q || [u.full_name, u.email, u.employee_id].some(x => String(x).toLowerCase().includes(q))));
  const bulkBar = () => {
    const n = sel.size;
    $('#bulk').innerHTML = n ? `<div class="card row" style="padding:10px 14px;margin-bottom:12px;flex-wrap:wrap;gap:10px;border-color:var(--orange)"><b>${n} selected</b><span class="spacer"></span>
      <button class="btn sm primary" id="bAdd">Give access to a department…</button><button class="btn sm" id="bRem">Remove access…</button><button class="btn ghost sm" id="bClr">Clear</button></div>` : '';
    if (!n) return;
    $('#bClr').onclick = () => { sel.clear(); draw(); };
    $('#bAdd').onclick = () => bulkModal(true); $('#bRem').onclick = () => bulkModal(false);
  };
  const bulkModal = add => modal(add ? `Give ${sel.size} people access` : `Remove access from ${sel.size} people`,
    `<p class="hint" style="margin-bottom:12px">${add ? 'They will be able to see the knowledge of the departments you tick (their answers use it right away).' : 'They will no longer see the knowledge of the departments you tick.'}</p>
     <div style="margin-bottom:16px">${deptChecks('bd', depts)}</div><div id="bm"></div><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn primary" data-ok>${add ? 'Give access' : 'Remove access'}</button></div>`,
    { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = async e => { const ids = checked(el, 'bd');
      if (!ids.length) { $('#bm', el).innerHTML = errBanner('Tick at least one department.'); return; }
      try { await busy(e.currentTarget, () => api('/v1/users/bulk-departments', { method: 'POST', body: { user_ids: [...sel], [add ? 'add' : 'remove']: ids } }));
        close(); toast('Access updated'); sel.clear(); load(); } catch (err) { $('#bm', el).innerHTML = errBanner(err); } }; } });
  const draw = () => {
    const rows = shown(); bulkBar();
    $('#ul').innerHTML = rows.length ? `<div class="hint" style="margin:0 0 8px">Showing ${rows.length} of ${users.length} people</div><div class="table-wrap"><table><thead><tr><th style="width:36px"><input type="checkbox" id="selAll" aria-label="Select everyone shown" ${rows.every(u => sel.has(u.id)) ? 'checked' : ''}></th><th>Name</th><th>ID</th><th>Role</th><th>Can see knowledge of</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(u => `<tr><td><input type="checkbox" data-sel="${u.id}" ${sel.has(u.id) ? 'checked' : ''} aria-label="Select ${esc(u.full_name)}"></td><td><div class="row">${avatarHTML(u, 32)}<div><b>${esc(u.full_name)}</b><div class="hint">${esc(u.email)}</div></div></div></td><td>${esc(u.employee_id)}</td>
        <td><select class="select" style="height:36px;width:132px" data-role="${u.id}">${Object.keys(ROLE_LABEL).map(r => `<option value="${r}" ${u.role === r ? 'selected' : ''}>${ROLE_LABEL[r]}</option>`).join('')}</select></td>
        <td>${u.role === 'administrator' ? '<span class="chip orange">Everything (administrator)</span>' : u.departments.length ? u.departments.map(d => `<span class="chip" style="margin:2px">${esc(d)}</span>`).join('') : '<span class="hint">Nothing yet</span>'}</td>
        <td><span class="chip dot ${u.is_active ? 'green' : ''}">${u.is_active ? 'Active' : 'Disabled'}</span></td>
        <td><div class="row"><button class="btn sm" data-dep="${u.id}">Access</button><button class="btn ghost sm" data-act="${u.id}">${u.is_active ? 'Disable' : 'Enable'}</button></div></td></tr>`).join('')}</tbody></table></div>`
      : emptyState('users', users.length ? 'No one matches' : 'No users', users.length ? 'Try a different search or filter.' : 'Add the first user.');
    const all = $('#selAll'); if (all) all.onchange = () => { rows.forEach(u => all.checked ? sel.add(u.id) : sel.delete(u.id)); draw(); };
    $$('[data-sel]', view).forEach(c => c.onchange = () => { c.checked ? sel.add(c.dataset.sel) : sel.delete(c.dataset.sel); bulkBar(); const a = $('#selAll'); if (a) a.checked = rows.every(u => sel.has(u.id)); });
    $$('[data-role]', view).forEach(s => s.onchange = async () => { try { await api(`/v1/users/${s.dataset.role}`, { method: 'PATCH', body: { role: s.value } }); byId[s.dataset.role].role = s.value; toast('Role updated'); draw(); } catch (e) { toast(e.message); load(); } });
    $$('[data-act]', view).forEach(b => b.onclick = async () => { const u = byId[b.dataset.act]; try { await api(`/v1/users/${u.id}`, { method: 'PATCH', body: { is_active: !u.is_active } }); load(); } catch (e) { toast(e.message); } });
    $$('[data-dep]', view).forEach(b => b.onclick = () => { const u = byId[b.dataset.dep];
      modal(`What can ${u.full_name} see?`, `<p class="hint" style="margin-bottom:12px">Tick the departments whose knowledge this person may use. Their answers never use anything else.</p><div style="margin-bottom:16px">${deptChecks('d', depts, u.department_ids || [])}</div><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn primary" data-ok>Save</button></div>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = async () => { try { await api(`/v1/users/${u.id}`, { method: 'PATCH', body: { department_ids: checked(el, 'd') } }); close(); toast('Saved'); load(); } catch (e) { toast(e.message); } }; } }); });
  };
  const load = async () => {
    try {
      [users, depts] = await Promise.all([api('/v1/users').then(r => r.users), api('/v1/departments').then(r => r.departments.filter(d => d.status === 'active'))]);
      byId = Object.fromEntries(users.map(u => [u.id, u]));
      $('#ud').innerHTML = `<option value="">Any department</option>${depts.map(d => `<option value="${d.id}" ${dept === d.id ? 'selected' : ''}>${esc(d.name)}</option>`).join('')}<option value="_none" ${dept === '_none' ? 'selected' : ''}>No department</option>`;
      draw();
    } catch (e) { $('#ul').innerHTML = errBanner(e); }
  };
  $('#uq').oninput = e => { q = e.target.value.trim().toLowerCase(); draw(); };
  $('#ur').onchange = e => { role = e.target.value; draw(); };
  $('#ud').onchange = e => { dept = e.target.value; draw(); };
  $('#inv').onclick = () => {
    modal('Add user', `<form id="uf" class="grid" style="gap:14px"><div class="grid" style="grid-template-columns:1fr 1fr;gap:12px"><div class="field"><label>Full name</label><input class="input" name="n" required></div><div class="field"><label>Employee ID</label><input class="input" name="e" required></div></div>
      <div class="field"><label>Email</label><input class="input" type="email" name="m" required></div><div class="grid" style="grid-template-columns:1fr 1fr;gap:12px"><div class="field"><label>Temporary password</label><input class="input" name="p" type="password" required minlength="8" autocomplete="new-password"></div>
      <div class="field"><label>Role</label><select class="select" name="r">${Object.keys(ROLE_LABEL).map(r => `<option value="${r}">${ROLE_LABEL[r]}</option>`).join('')}</select></div></div>
      <div class="field"><label>Can see knowledge of</label><div>${deptChecks('d', depts)}</div></div><div id="um"></div><div class="row" style="justify-content:flex-end"><button type="button" class="btn" data-x>Cancel</button><button class="btn primary">Add user</button></div></form>`,
      { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('#uf', el).onsubmit = async e => { e.preventDefault(); const f = e.target;
        try { await busy(e.submitter, () => api('/v1/users', { method: 'POST', body: { full_name: f.n.value, employee_id: f.e.value, email: f.m.value, password: f.p.value, role: f.r.value, department_ids: checked(el, 'd') } })); close(); toast('User added'); load(); } catch (err) { $('#um', el).innerHTML = errBanner(err); } }; } });
  };
  load();
}

/* ================= DEPARTMENTS ================= */
async function pageDepartments(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Departments</h1><p>Knowledge and people are organised by department.</p></div></div>
    <form class="row card" id="df" style="margin-bottom:16px;padding:14px"><input class="input" name="n" placeholder="New department name" required><button class="btn primary" style="flex:none">${ic('plus', 16)} Create</button></form><div id="dl">${loading()}</div></div>`;
  const load = async () => {
    try {
      const [ds, us] = await Promise.all([api('/v1/departments'), api('/v1/users')]); const users = us.users, name = id => users.find(u => u.id === id)?.full_name;
      $('#dl').innerHTML = `<div class="table-wrap"><table><thead><tr><th>Department</th><th>Manager</th><th>Status</th><th></th></tr></thead><tbody>${ds.departments.map(d => `<tr><td><b>${esc(d.name)}</b></td><td>${esc(name(d.manager_id) || '—')}</td><td><span class="chip dot ${d.status === 'active' ? 'green' : ''}">${d.status === 'active' ? 'Active' : 'Archived'}</span></td>
        <td><div class="row" style="justify-content:flex-end"><button class="btn sm" data-ren="${d.id}">Rename</button><button class="btn sm" data-mgr="${d.id}">Set manager</button><button class="btn ghost sm" data-arc="${d.id}">${d.status === 'active' ? 'Archive' : 'Restore'}</button></div></td></tr>`).join('')}</tbody></table></div>`;
      const byId = Object.fromEntries(ds.departments.map(d => [d.id, d])), patch = async (id, body) => { try { await api(`/v1/departments/${id}`, { method: 'PATCH', body }); load(); } catch (e) { toast(e.message); } };
      $$('[data-arc]', view).forEach(b => b.onclick = () => patch(b.dataset.arc, { status: byId[b.dataset.arc].status === 'active' ? 'archived' : 'active' }));
      $$('[data-ren]', view).forEach(b => b.onclick = () => modal('Rename department', `<div class="field" style="margin-bottom:16px"><input class="input" id="rn" value="${esc(byId[b.dataset.ren].name)}"></div><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn primary" data-ok>Save</button></div>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = () => { const v = $('#rn', el).value.trim(); if (v) { close(); patch(b.dataset.ren, { name: v }); } }; } }));
      $$('[data-mgr]', view).forEach(b => b.onclick = () => modal('Set department manager', `<div class="field" style="margin-bottom:16px"><select class="select" id="mg"><option value="">No manager</option>${users.filter(u => u.is_active).map(u => `<option value="${u.id}" ${byId[b.dataset.mgr].manager_id === u.id ? 'selected' : ''}>${esc(u.full_name)} (${ROLE_LABEL[u.role]})</option>`).join('')}</select></div><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn primary" data-ok>Save</button></div>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = () => { const v = $('#mg', el).value; close(); patch(b.dataset.mgr, v ? { manager_id: v } : { clear_manager: true }); }; } }));
    } catch (e) { $('#dl').innerHTML = errBanner(e); }
  };
  $('#df').onsubmit = async e => { e.preventDefault(); try { await api('/v1/departments', { method: 'POST', body: { name: e.target.n.value.trim() } }); e.target.reset(); load(); } catch (err) { toast(err.message); } };
  load();
}

/* ================= API KEYS (like an LLM provider's keys: secret shown once, optional expiry) ================= */
const EXPIRY = [['never', 'Never — until I revoke it'], ['1h', '1 hour'], ['24h', '24 hours'], ['1w', '1 week'], ['1m', '1 month'], ['1y', '1 year']];
function keyState(k) {
  if (k.status !== 'active') return ['Revoked', ''];
  if (k.expires_at && new Date(k.expires_at) <= new Date()) return ['Expired', 'red'];
  return ['Active', 'green'];
}
const expiresText = iso => { if (!iso) return 'Never'; const d = new Date(iso), ms = d - Date.now(); if (ms <= 0) return 'Expired ' + fmtDate(iso);
  const m = ms / 60000; return m < 90 ? `in ${Math.round(m)} min` : m < 2880 ? `in ${Math.round(m / 60)} h` : `in ${Math.round(m / 1440)} days · ${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`; };
async function pageKeys(view) {
  let fresh = null;
  const draw = async () => {
    view.innerHTML = `<div class="page"><div class="page-head"><div><h1>API keys</h1><p>Let other Quixotic apps use your knowledge base. Keep keys secret — treat them like passwords.</p></div><button class="btn primary" id="nk">${ic('plus', 17)} Create new key</button></div>
      ${fresh ? `<div class="card" style="border-color:var(--green);margin-bottom:16px"><b>Your new key${fresh.name ? ` “${esc(fresh.name)}”` : ''}</b><div class="keybox" style="margin:10px 0">${esc(fresh.key)}</div><p class="hint">Copy it now and store it somewhere safe. You won’t be able to see it again.</p>
        <div class="row" style="margin:10px 0 14px;flex-wrap:wrap"><button class="btn sm" id="cpk">${ic('copy', 15)} Copy key</button><span class="chip ${fresh.expires ? 'amber' : 'green'}">${fresh.expires ? 'Expires ' + expiresText(fresh.expires) : 'Never expires'}</span></div>
        <div class="label" style="margin-bottom:6px">Try it</div><pre class="keybox" style="white-space:pre-wrap;border-style:solid;border-color:var(--line-2)">curl ${esc(location.origin)}/v1/ask \\\n  -H "X-API-Key: ${esc(fresh.key)}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"question": "What is our refund policy?"}'</pre></div>` : ''}<div id="kl">${loading()}</div></div>`;
    if (fresh) $('#cpk').onclick = () => { navigator.clipboard?.writeText(fresh.key); toast('Copied'); };
    try {
      const [ks, ds] = await Promise.all([api('/v1/api-keys'), api('/v1/departments')]); const dn = id => ds.departments.find(d => d.id === id)?.name || '—';
      $('#kl').innerHTML = ks.api_keys.length ? `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Key</th><th>Permissions</th><th>Access</th><th>Expires</th><th>Last used</th><th>Created</th><th>Status</th><th></th></tr></thead><tbody>${ks.api_keys.map(k => { const [sl, sc] = keyState(k);
        return `<tr><td><b>${esc(k.app_name)}</b></td><td><code>${esc(k.key_prefix)}••••${esc(k.last4 || '')}</code></td><td>${k.permissions.map(p => `<span class="chip" style="margin:2px">${esc(p.replace('_', ' '))}</span>`).join('')}</td><td>${k.allowed_department_ids.length ? esc(k.allowed_department_ids.map(dn).join(', ')) : 'All departments'}</td><td>${esc(expiresText(k.expires_at))}</td><td>${k.last_used_at ? fmtDate(k.last_used_at) : 'Never'}</td><td>${fmtDate(k.created_at)}</td><td><span class="chip dot ${sc}">${sl}</span></td><td>${k.status === 'active' ? `<button class="btn ghost sm" data-rev="${k.id}">Revoke</button>` : ''}</td></tr>`; }).join('')}</tbody></table></div>`
        : emptyState('key', 'No API keys yet', 'Create a key so another app can use your company knowledge.');
      $$('[data-rev]', view).forEach(b => b.onclick = () => modal('Revoke this key?', `<p style="color:var(--ink-2);margin-bottom:18px">Any app using it stops working immediately. This can’t be undone.</p><div class="row" style="justify-content:flex-end"><button class="btn" data-x>Cancel</button><button class="btn bad" data-ok>Revoke</button></div>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('[data-ok]', el).onclick = async () => { try { await api(`/v1/api-keys/${b.dataset.rev}`, { method: 'DELETE' }); close(); draw(); } catch (e) { toast(e.message); } }; } }));
      $('#nk').onclick = () => modal('Create new API key', `<form id="kf" class="grid" style="gap:16px">
        <div class="field"><label>Name <span class="hint">(just for you — it isn’t part of the key)</span></label><input class="input" name="a" required placeholder="e.g. Call center app"></div>
        <div class="field"><label>This key works for</label><select class="select" name="x">${EXPIRY.map(e => `<option value="${e[0]}">${e[1]}</option>`).join('')}</select></div>
        <div class="field"><label>Permissions</label><div>${['ask', 'search', 'documents', 'sales_memory', 'feedback'].map(p => `<label class="check"><input type="checkbox" name="p" value="${p}" ${p === 'ask' || p === 'search' ? 'checked' : ''}> ${p.replace('_', ' ')}</label>`).join('')}</div></div>
        <div class="field"><label>Access</label><label class="check"><input type="checkbox" id="allDepts" checked> All departments</label><div id="deptBox" hidden style="margin-top:6px">${deptChecks('d', ds.departments.filter(d => d.status === 'active'))}</div></div>
        <div id="km"></div><div class="row" style="justify-content:flex-end"><button type="button" class="btn" data-x>Cancel</button><button class="btn primary">Create key</button></div></form>`,
        { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('#allDepts', el).onchange = e => { $('#deptBox', el).hidden = e.target.checked; };
          $('#kf', el).onsubmit = async e => { e.preventDefault(); const f = e.target, all = $('#allDepts', el).checked;
            if (!all && !checked(el, 'd').length) { $('#km', el).innerHTML = errBanner('Pick at least one department, or choose “All departments”.'); return; }
            try { const r = await busy(e.submitter, () => api('/v1/api-keys', { method: 'POST', body: { name: f.a.value, permissions: checked(el, 'p'), department_ids: all ? [] : checked(el, 'd'), expires_in: f.x.value } }));
              fresh = { name: f.a.value, key: r.api_key, expires: r.expires_at }; close(); draw(); } catch (err) { $('#km', el).innerHTML = errBanner(err); } }; } });
    } catch (e) { $('#kl').innerHTML = errBanner(e); }
  };
  draw();
}

/* ================= SYSTEM ================= */
async function pageSystem(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>System</h1><p>Background work and the audit trail.</p></div><span id="hl"></span></div>
    <div class="card" style="margin-bottom:16px"><b>Background jobs</b><div id="jl" style="margin-top:10px">${loading()}</div></div>
    <div class="card"><div class="row" style="margin-bottom:10px;flex-wrap:wrap"><b style="flex:1">Audit log</b><select class="select" id="ev" style="width:220px;height:38px"><option value="">All events</option>${['user_login', 'failed_authentication', 'document_upload', 'knowledge_submission', 'approval', 'rejection', 'archive_event', 'permission_change', 'api_key_creation', 'model_change', 'admin_action', 'sensitive_access_event'].map(e => `<option value="${e}">${e.replace(/_/g, ' ')}</option>`).join('')}</select></div><div id="au">${loading()}</div></div></div>`;
  api('/v1/health').then(() => { $('#hl').innerHTML = '<span class="chip green dot">Service healthy</span>'; }).catch(() => { $('#hl').innerHTML = '<span class="chip red dot">Service unreachable</span>'; });
  const JS = { queued: ['Queued', 'amber'], running: ['Running', 'blue'], succeeded: ['Done', 'green'], failed: ['Failed', 'red'] };
  const jobs = async () => { try { const j = (await api('/v1/jobs')).jobs; if (parseRoute().page !== 'system') return clearInterval(S.timer);
    $('#jl').innerHTML = j.length ? `<div class="table-wrap" style="border:0"><table><thead><tr><th>Job</th><th>Status</th><th style="width:240px">Progress</th><th>Started</th></tr></thead><tbody>${j.map(x => { const [l, c] = JS[x.status] || [x.status, '']; const pct = x.progress_total ? Math.round(100 * x.progress_done / x.progress_total) : (x.status === 'succeeded' ? 100 : 0);
      return `<tr><td><b>${esc(x.type.replace(/[._]/g, ' '))}</b>${x.error ? `<div class="hint" style="color:var(--red)">${esc(x.error)}</div>` : ''}</td><td><span class="chip ${c} dot">${l}</span></td><td>${x.progress_total ? `<div class="bar"><i style="width:${pct}%"></i></div><div class="hint">${x.progress_done.toLocaleString()} / ${x.progress_total.toLocaleString()}</div>` : '<span class="hint">—</span>'}</td><td>${fmtDate(x.created_at)}</td></tr>`; }).join('')}</tbody></table></div>` : '<p class="hint">No background jobs yet.</p>';
    clearInterval(S.timer); if (j.some(x => x.status === 'queued' || x.status === 'running')) S.timer = setInterval(jobs, 4000); } catch (e) { $('#jl').innerHTML = errBanner(e); } };
  const audit = async () => { try { const a = (await api('/v1/audit-logs?limit=100' + ($('#ev').value ? '&event=' + $('#ev').value : ''))).audit_logs;
    $('#au').innerHTML = a.length ? `<div class="table-wrap" style="border:0"><table><thead><tr><th>When</th><th>Who</th><th>Event</th><th>Detail</th></tr></thead><tbody>${a.map(x => `<tr><td>${fmtDate(x.at)}</td><td>${esc(x.actor_label || '—')}</td><td><span class="chip">${esc(x.event.replace(/_/g, ' '))}</span></td><td class="hint" style="max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(Object.entries(x.detail || {}).filter(([, v]) => v != null).map(([k, v]) => k.replace(/_/g, ' ') + ': ' + v).join(' · '))}</td></tr>`).join('')}</tbody></table></div>` : '<p class="hint">No events yet.</p>'; } catch (e) { $('#au').innerHTML = errBanner(e); } };
  $('#ev').onchange = audit; jobs(); audit();
}

/* ================= VOCABULARY: teach the system Urdu / Roman Urdu words (owner request) ================= */
function teachModal(prefill, done) {
  modal('Teach the system a word', `<form id="vf" class="grid" style="gap:14px">
    <p class="hint">Write a word or phrase the way your staff type it, and what it means in English — the words your documents use. From then on, questions containing it also search for that meaning.</p>
    <div class="field"><label>Staff write (Roman Urdu or Urdu)</label><input class="input" name="p" required maxlength="80" value="${esc(prefill || '')}" placeholder="e.g. ghar se kaam   or   چھٹی"></div>
    <div class="field"><label>It means (English, as in your documents)</label><input class="input" name="m" required maxlength="120" placeholder="e.g. work from home"></div>
    <div id="vm"></div><div class="row" style="justify-content:flex-end"><button type="button" class="btn" data-x>Cancel</button><button class="btn primary">Teach</button></div></form>`,
    { onMount: (el, close) => { $('[data-x]', el).onclick = close; $('#vf', el).onsubmit = async e => { e.preventDefault(); const f = e.target;
      try { await busy(e.submitter, () => api('/v1/vocabulary', { method: 'POST', body: { phrase: f.p.value, meaning: f.m.value } })); close(); toast('Learned. Questions with this phrase now find it.'); done && done(); } catch (err) { $('#vm', el).innerHTML = errBanner(err); } }; } });
}
async function pageVocabulary(view) {
  view.innerHTML = `<div class="page"><div class="page-head"><div><h1>Vocabulary</h1><p>Teach the system the Urdu and Roman Urdu words your staff really use.</p></div><button class="btn primary" id="tw">${ic('plus', 17)} Teach a word</button></div>
    <div class="card" style="margin-bottom:16px"><b>How it works</b><p class="hint" style="margin-top:6px">Your documents are mostly English, but people ask in Urdu and Roman Urdu. When someone writes <code>ghar se kaam</code>, the system also searches for <code>work from home</code>. Add the words that fail for you — the <b>Insights → Failed questions</b> list shows which ones. Changes work immediately.</p></div>
    <div id="vl">${loading()}</div></div>`;
  const load = async () => {
    try {
      const rows = (await api('/v1/vocabulary')).entries;
      $('#vl').innerHTML = rows.length ? `<div class="table-wrap"><table><thead><tr><th>Staff write</th><th>Means</th><th>Added</th><th></th></tr></thead><tbody>${rows.map(r => `<tr><td><b>${esc(r.phrase)}</b></td><td>${esc(r.meaning)}</td><td>${fmtDate(r.created_at)}</td><td><button class="btn ghost sm" data-del="${r.id}" title="Forget">${ic('trash', 16)}</button></td></tr>`).join('')}</tbody></table></div>`
        : emptyState('spark', 'No words taught yet', 'Add a few of the Roman Urdu or Urdu phrases your staff use, with their English meaning.', '<button class="btn primary" id="tw2">Teach a word</button>');
      $$('[data-del]', view).forEach(b => b.onclick = async () => { try { await api(`/v1/vocabulary/${b.dataset.del}`, { method: 'DELETE' }); load(); } catch (e) { toast(e.message); } });
      const t2 = $('#tw2'); if (t2) t2.onclick = () => teachModal('', load);
    } catch (e) { $('#vl').innerHTML = errBanner(e); }
  };
  $('#tw').onclick = () => teachModal('', load); load();
}

const PAGES = { ask: renderAsk, knowledge: pageKnowledge, add: pageAdd, documents: pageDocuments, sales: pageSales, approvals: pageApprovals, requests: pageRequests, dashboard: pageDashboard, insights: pageInsights, users: pageUsers, departments: pageDepartments, keys: pageKeys, vocabulary: pageVocabulary, system: pageSystem };
boot();
})();
