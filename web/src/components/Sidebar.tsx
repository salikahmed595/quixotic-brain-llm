import { useState } from 'react';
import { api, storage } from '../api';
import { Brand, Icon } from '../icons';
import { useApp, useRoute } from '../state';
import { Avatar, Banner, openMenu, openModal, ROLE_LABEL, scopeLabel, toast, useAction } from '../ui';
import type { Chat } from '../types';
import { personalizationModal, profileModal, settingsModal } from './Account';

/* PRD §4.3 — admin sidebar, exact groups and order. `min` is the role rank allowed to see the page; the server checks
   every call regardless (§3 "not only by hiding sidebar links"). Employees (rank 0) see no workspace at all (§4.2). */
export const NAV: { group: string; items: { id: string; label: string; icon: string; min: number }[] }[] = [
  { group: 'Knowledge', items: [
    { id: 'knowledge', label: 'Knowledge', icon: 'book', min: 1 },
    { id: 'add', label: 'Add information', icon: 'plus', min: 1 },
    { id: 'documents', label: 'Documents', icon: 'doc', min: 1 },
    { id: 'sales', label: 'Sales memory', icon: 'msg', min: 3 },
  ] },
  { group: 'Manage', items: [
    { id: 'approvals', label: 'Approvals', icon: 'check', min: 2 },
    { id: 'requests', label: 'Access requests', icon: 'users', min: 2 },
    { id: 'dashboard', label: 'Dashboard', icon: 'chart', min: 2 },
    { id: 'insights', label: 'Insights', icon: 'alert', min: 3 },
  ] },
  { group: 'Administration', items: [
    { id: 'users', label: 'Users', icon: 'users', min: 3 },
    { id: 'departments', label: 'Departments', icon: 'building', min: 3 },
    { id: 'vocabulary', label: 'Vocabulary', icon: 'spark', min: 3 },
    { id: 'keys', label: 'API keys', icon: 'key', min: 3 },
    { id: 'system', label: 'System', icon: 'pulse', min: 3 },
  ] },
];
export const pageMin = (id: string) => NAV.flatMap(g => g.items).find(i => i.id === id)?.min ?? 0;

/* PRD §6 FR-CHAT-01 "recent history grouping" */
function groupChats(chats: Chat[]) {
  const now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime(), day = 86400000;
  const buckets: [string, Chat[]][] = [['Today', []], ['Yesterday', []], ['Previous 7 days', []], ['Previous 30 days', []], ['Older', []]];
  chats.forEach(c => {
    const t = new Date(c.updated_at).getTime();
    (t >= today ? buckets[0] : t >= today - day ? buckets[1] : t >= today - 7 * day ? buckets[2] : t >= today - 30 * day ? buckets[3] : buckets[4])[1].push(c);
  });
  return buckets.filter(b => b[1].length);
}

export function Sidebar({ onClose, onNewChat }: { onClose: () => void; onNewChat: () => void }) {
  const app = useApp(); const { me, rank, chats, counts } = app;
  const route = useRoute();
  const [filter, setFilter] = useState('');
  const [wsOpen, setWsOpen] = useState(storage.get('qb_ws') !== '0');
  const groups = NAV.map(g => ({ ...g, items: g.items.filter(i => i.min <= rank) })).filter(g => g.items.length);
  const q = filter.trim().toLowerCase();
  const shown = chats.filter(c => !q || c.title.toLowerCase().includes(q));
  const count = (id: string) => (id === 'approvals' ? counts.pending : id === 'requests' ? counts.requests : 0);

  const chatMenu = (e: React.MouseEvent<HTMLButtonElement>, chat: Chat) => {
    e.preventDefault(); e.stopPropagation();
    openMenu(e.currentTarget, [
      { label: 'Rename', icon: 'pen', onClick: () => renameChat(chat, app.reloadChats) },
      { label: 'Delete', icon: 'trash', danger: true, onClick: () => deleteChat(chat, () => { app.setChats(chats.filter(c => c.id !== chat.id)); if (route.chat === chat.id) onNewChat(); }) },
    ]);
  };
  const accountMenu = (e: React.SyntheticEvent<HTMLElement>) => {
    e.stopPropagation();
    openMenu(e.currentTarget, [
      { label: 'Personalization', icon: 'sliders', onClick: () => personalizationModal(app) },
      { label: 'Profile', icon: 'user', onClick: () => profileModal(app) },
      { label: 'Settings', icon: 'gear', onClick: () => settingsModal(app, onNewChat) },
      { label: 'Log out', icon: 'out', onClick: app.logout },
    ], {
      up: true, minWidth: 260,
      header: <div className="flex items-center gap-3 px-2 pt-2 pb-2.5 mb-1.5 border-b border-line"><Avatar user={me} size={40} />
        <div className="min-w-0 leading-tight"><b className="block text-sm truncate">{me.full_name}</b><small className="block text-xs text-muted truncate">{me.email}</small></div></div>,
    });
  };

  return (
    <nav aria-label="Main" className="flex flex-col h-full w-full bg-side px-2.5 pt-2.5">
      {/* PRD §4.4: 44 × 44 px touch targets in the mobile drawer; desktop keeps the §4 screenshot sizes */}
      <div className="flex items-center justify-between pl-0.5 pr-1 h-10 max-[900px]:h-11">
        <a href="#/ask" onClick={e => { e.preventDefault(); onNewChat(); }} className="no-underline max-[900px]:h-11 max-[900px]:inline-flex max-[900px]:items-center"><Brand /></a>
        <button className="w-10 h-10 max-[900px]:w-11 max-[900px]:h-11 grid place-items-center rounded-[10px] text-ink-2 hover:bg-orange-100 hover:text-orange" onClick={onClose} aria-label="Close sidebar" title="Close sidebar">
          <Icon name="sidebar" size={20} />
        </button>
      </div>
      <button className="sb-row mt-[7px] font-semibold text-ink" onClick={onNewChat}><Icon name="newchat" size={19} />New chat</button>
      <label className="sb-row text-muted cursor-text hover:bg-white focus-within:bg-white">
        <Icon name="search" size={18} />
        <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Search chats" aria-label="Search chats" autoComplete="off"
          className="flex-1 min-w-0 bg-transparent outline-none text-ink placeholder:text-muted" />
      </label>

      {groups.length > 0 && (<>
        <button className="flex items-center gap-2.5 h-8 max-[900px]:h-11 px-3 mt-2.5 text-[12.5px] font-bold tracking-[.06em] uppercase text-muted hover:text-orange rounded-lg"
          aria-expanded={wsOpen} onClick={() => { setWsOpen(!wsOpen); storage.set('qb_ws', wsOpen ? '0' : '1'); }}>
          <Icon name="chevd" size={14} className={`transition-transform ${wsOpen ? '' : '-rotate-90'}`} />Workspace
        </button>
        {wsOpen && (
          <div className="scroll-thin overflow-y-auto max-h-[calc(100vh-330px)] min-h-[120px] px-2 pt-2.5 pb-1 flex-none">
            {groups.map(g => (
              <div key={g.group} className="ws-group">
                <div className="ws-label">{g.group}</div>
                <div className="flex flex-col gap-0">
                  {g.items.map(i => (
                    <a key={i.id} href={`#/${i.id}`} className={`ws-item ${route.page === i.id ? 'on' : ''}`} aria-current={route.page === i.id ? 'page' : undefined}>
                      <Icon name={i.icon} />{i.label}
                      {count(i.id) > 0 && <span className="ml-auto bg-orange text-white rounded-full text-[11px] min-w-5 h-5 grid place-items-center px-1.5">{count(i.id)}</span>}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </>)}

      <div className="flex-1 overflow-y-auto scroll-thin -mx-1 px-1 mt-2 pb-2">
        {!chats.length ? <p className="text-muted text-[13.5px] px-3 py-3.5">Your chats will appear here.</p>
          : !shown.length ? <p className="text-muted text-[13.5px] px-3 py-3.5">No chats match your search.</p>
          : groupChats(shown).map(([label, items]) => (
            <div key={label}>
              <div className="text-xs font-bold text-muted px-2 pt-3.5 pb-1.5">{label}</div>
              {items.map(c => (
                <a key={c.id} href={`#/chat/${c.id}`} className={`chat-item ${route.chat === c.id ? 'on' : ''}`}>
                  <span className="flex-1 min-w-0 truncate">{c.title}</span>
                  <button className="dots hover:bg-ink/5" aria-label={`Options for ${c.title}`} onClick={e => chatMenu(e, c)}><Icon name="dots" size={16} /></button>
                </a>
              ))}
            </div>
          ))}
      </div>

      <div role="button" tabIndex={0} onClick={accountMenu} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && accountMenu(e)}
        className="flex items-center gap-2.5 px-1.5 h-[54px] rounded-t-xl border border-b-0 border-line bg-side hover:bg-orange-50 cursor-pointer" aria-label="Account menu">
        <Avatar user={me} />
        <span className="flex-1 min-w-0 flex flex-col leading-tight">
          <b className="text-sm text-ink truncate">{me.full_name}</b>
          <small className="text-xs text-muted truncate">{ROLE_LABEL[me.role]} · {scopeLabel(me, app.activeDepartments)}</small>
        </span>
        <Icon name="dots" size={18} className="text-ink-2" />
      </div>
    </nav>
  );
}

function renameChat(chat: Chat, done: () => void) {
  openModal('Rename chat', close => <RenameChat chat={chat} done={() => { close(); done(); }} cancel={close} />);
}
function RenameChat({ chat, done, cancel }: { chat: Chat; done: () => void; cancel: () => void }) {
  const [title, setTitle] = useState(chat.title); const a = useAction();
  const save = () => a.run(() => api(`/v1/conversations/${chat.id}`, { method: 'PATCH', body: { title } })).then(ok => ok && done());
  return (<>
    <input className="input mb-4" value={title} maxLength={120} autoFocus onChange={e => setTitle(e.target.value)} onKeyDown={e => e.key === 'Enter' && save()} />
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-end gap-3"><button className="btn" onClick={cancel}>Cancel</button><button className="btn primary" disabled={a.busy} onClick={save}>Save</button></div>
  </>);
}
function deleteChat(chat: Chat, done: () => void) {
  openModal('Delete chat?', close => (<>
    <p className="text-ink-2 mb-4.5">This will delete <b>{chat.title}</b>. It can't be undone.</p>
    <div className="flex justify-end gap-3">
      <button className="btn" onClick={close}>Cancel</button>
      <button className="btn bad" onClick={async () => {
        try { await api(`/v1/conversations/${chat.id}`, { method: 'DELETE' }); close(); done(); toast('Chat deleted'); } catch (e) { toast((e as Error).message); }
      }}>Delete</button>
    </div>
  </>));
}

