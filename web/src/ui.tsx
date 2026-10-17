import { ReactNode, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Icon } from './icons';
import type { Me, Role } from './types';

/* ---------------- tiny global stores: toast, modals, menus ---------------- */
function store<T>(initial: T) {
  let value = initial; const subs = new Set<() => void>();
  return {
    get: () => value,
    set: (v: T) => { value = v; subs.forEach(s => s()); },
    subscribe: (fn: () => void) => { subs.add(fn); return () => { subs.delete(fn); }; },
  };
}

const toastStore = store<{ text: string; id: number } | null>(null);
let toastTimer: number | undefined;
export function toast(text: string) {
  toastStore.set({ text, id: Date.now() });
  clearTimeout(toastTimer); toastTimer = window.setTimeout(() => toastStore.set(null), 3200);
}

type ModalEntry = { id: number; title: string; wide?: boolean; drawer?: boolean; render: (close: () => void) => ReactNode };
const modalStore = store<ModalEntry[]>([]);
let modalId = 0;
export function openModal(title: string, render: (close: () => void) => ReactNode, opts: { wide?: boolean } = {}) {
  const id = ++modalId; modalStore.set([...modalStore.get(), { id, title, render, ...opts }]);
  return () => modalStore.set(modalStore.get().filter(m => m.id !== id));
}
export function openDrawer(render: (close: () => void) => ReactNode) {
  const id = ++modalId; modalStore.set([...modalStore.get(), { id, title: '', drawer: true, render }]);
  return () => modalStore.set(modalStore.get().filter(m => m.id !== id));
}
export function confirmModal(title: string, text: ReactNode, okLabel: string, onOk: () => Promise<void> | void, danger = true) {
  openModal(title, close => <Confirm text={text} okLabel={okLabel} danger={danger} onOk={async () => { await onOk(); close(); }} onCancel={close} />);
}
function Confirm({ text, okLabel, danger, onOk, onCancel }: { text: ReactNode; okLabel: string; danger: boolean; onOk: () => Promise<void>; onCancel: () => void }) {
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  return (<>
    <p className="text-ink-2 mb-4.5">{text}</p>
    {err && <Banner kind="err" className="mb-3">{err}</Banner>}
    <div className="flex justify-end gap-3">
      <button className="btn" onClick={onCancel}>Cancel</button>
      <button className={`btn ${danger ? 'bad' : 'primary'}`} disabled={busy}
        onClick={async () => { setBusy(true); try { await onOk(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }}>{okLabel}</button>
    </div>
  </>);
}

type MenuItem = { label: string; icon: string; onClick: () => void; danger?: boolean };
type MenuEntry = { rect: DOMRect; items: MenuItem[]; up?: boolean; header?: ReactNode; minWidth?: number } | null;
const menuStore = store<MenuEntry>(null);
export function openMenu(anchor: HTMLElement, items: MenuItem[], opts: { up?: boolean; header?: ReactNode; minWidth?: number } = {}) {
  menuStore.set({ rect: anchor.getBoundingClientRect(), items, ...opts });
}

function MenuHost() {
  const m = useSyncExternalStore(menuStore.subscribe, menuStore.get);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    if (!m || !ref.current) { setPos(null); return; }
    const w = ref.current.offsetWidth, h = ref.current.offsetHeight, r = m.rect;
    setPos({ left: Math.min(Math.max(8, m.up ? r.left : r.right - w + 4), innerWidth - w - 8), top: m.up ? Math.max(8, r.top - h - 8) : r.bottom + 4 });
  }, [m]);
  useEffect(() => {
    if (!m) return;
    const close = (e: Event) => { if (!ref.current?.contains(e.target as Node)) menuStore.set(null); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') menuStore.set(null); };
    setTimeout(() => document.addEventListener('mousedown', close));
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [m]);
  if (!m) return null;
  return (
    <div ref={ref} className="menu-pop" role="menu" style={{ left: pos?.left ?? -999, top: pos?.top ?? -999, minWidth: m.minWidth }}>
      {m.header}
      {m.items.map(it => (
        <button key={it.label} role="menuitem" className={it.danger ? 'danger' : ''} onClick={() => { menuStore.set(null); it.onClick(); }}>
          <Icon name={it.icon} size={16} /> {it.label}
        </button>
      ))}
    </div>
  );
}

export function Overlays() {
  const t = useSyncExternalStore(toastStore.subscribe, toastStore.get);
  const modals = useSyncExternalStore(modalStore.subscribe, modalStore.get);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { const top = modalStore.get().at(-1); if (e.key === 'Escape' && top) modalStore.set(modalStore.get().slice(0, -1)); };
    document.addEventListener('keydown', esc); return () => document.removeEventListener('keydown', esc);
  }, []);
  return (<>
    {modals.map(m => {
      const close = () => modalStore.set(modalStore.get().filter(x => x.id !== m.id));
      return m.drawer ? (
        <div key={m.id} className="fixed inset-0 z-[80] flex justify-end bg-ink/40" onMouseDown={e => e.target === e.currentTarget && close()}>
          <aside role="dialog" aria-modal="true" className="w-[min(560px,100%)] h-full bg-white overflow-auto p-6.5 animate-[slide_.2s_ease]">{m.render(close)}</aside>
        </div>
      ) : (
        <div key={m.id} className="fixed inset-0 z-[90] grid place-items-center p-4 bg-ink/40" onMouseDown={e => e.target === e.currentTarget && close()}>
          <div role="dialog" aria-modal="true" aria-label={m.title} className={`bg-white rounded-[20px] p-6.5 max-h-[90vh] overflow-auto shadow-lift ${m.wide ? 'w-[min(680px,100%)]' : 'w-[min(520px,100%)]'}`}>
            <h3 className="text-[19px] font-bold mb-3.5">{m.title}</h3>
            {m.render(close)}
          </div>
        </div>
      );
    })}
    <MenuHost />
    <div role="status" aria-live="polite"
      className={`fixed left-1/2 bottom-7 -translate-x-1/2 bg-ink text-canvas px-4.5 py-3 rounded-xl font-semibold text-sm z-[120] max-w-[90vw] pointer-events-none transition-all duration-250 ${t ? 'opacity-100' : 'opacity-0 translate-y-5'}`}>
      {t?.text}
    </div>
  </>);
}

/* ---------------- small pieces ---------------- */
export const Loading = () => <div className="empty"><div className="typing"><i /><i /><i /></div></div>;
export function Banner({ kind, children, className = '' }: { kind: 'ok' | 'err'; children: ReactNode; className?: string }) {
  return <div className={`banner ${kind} ${className}`}>{children}</div>;
}
export function Empty({ icon, title, text, action }: { icon: string; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="empty"><div className="ico"><Icon name={icon} size={22} /></div><h3>{title}</h3><p>{text}</p>
      {action && <div className="mt-3.5">{action}</div>}</div>
  );
}
export function PageHead({ title, sub, children }: { title: string; sub: string; children?: ReactNode }) {
  return <div className="page-head"><div><h1>{title}</h1><p>{sub}</p></div>{children}</div>;
}

export const STATUS: Record<string, [string, string]> = {
  draft: ['Draft', ''], submitted: ['Submitted', 'blue'], pending_review: ['Pending review', 'amber'], approved: ['Approved', 'blue'],
  active: ['Active', 'green'], rejected: ['Rejected', 'red'], archived: ['Archived', ''], expired: ['Expired', ''],
};
export const StatusChip = ({ s }: { s: string }) => { const [l, c] = STATUS[s] || [s, '']; return <span className={`chip dot ${c}`}>{l}</span>; };

/* PRD §3 roles. "Administrator" is the System Admin, as on the §4.3 admin card. */
export const ROLE_LABEL: Record<Role, string> = {
  employee: 'Employee', department_reviewer: 'Department Reviewer', knowledge_admin: 'Knowledge Admin',
  system_admin: 'Administrator', founder_ceo: 'Founder / CEO',
};
export const can = (me: Me, permission: string) => me.permissions.includes(permission);

export function fmtDate(iso?: string | null) {
  if (!iso) return '—'; const d = new Date(iso); if (isNaN(+d)) return '—';
  const s = (Date.now() - +d) / 1000;
  if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + ' min ago'; if (s < 86400) return Math.floor(s / 3600) + ' h ago';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}
export const initials = (n?: string) => (n || '?').split(/\s+/).map(x => x[0]).slice(0, 2).join('').toUpperCase();

export function Avatar({ user, size = 36 }: { user?: { full_name?: string; avatar?: string | null } | null; size?: number }) {
  const st = { width: size, height: size, fontSize: Math.round(size * 0.38) };
  return user?.avatar ? <img className="avatar" alt="" src={user.avatar} style={st} /> : <span className="avatar" style={st}>{initials(user?.full_name)}</span>;
}

/* PRD §4.2 / §4.3: "Role · Authorized Scope". 'Company Wide' only when the person truly sees every active department
   (administrators do); never assigned or shown by default (§15). */
export function scopeLabel(me: Me) {
  if (me.company_wide) return 'Company Wide';
  return me.scope.map(d => d.name).join(', ') || 'No access yet';
}

export function DeptChecks({ depts, value, onChange }: { depts: { id: string; name: string }[]; value: string[]; onChange: (v: string[]) => void }) {
  if (!depts.length) return <p className="hint">No departments are available to you yet. Ask an administrator to assign you to one.</p>;
  return (<div>{depts.map(d => (
    <label key={d.id} className="check">
      <input type="checkbox" checked={value.includes(d.id)} onChange={e => onChange(e.target.checked ? [...value, d.id] : value.filter(x => x !== d.id))} /> {d.name}
    </label>))}</div>);
}

/* Runs an async action with a disabled button and an error message. */
export function useAction() {
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); return true; } catch (e) { setError((e as Error).message); return false; } finally { setBusy(false); }
  };
  return { busy, error, setError, run };
}

/* Loads data on mount (and when `deps` change); `reload` refreshes it. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null); const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true; setError(null);
    fn().then(d => { if (live) setData(d); }).catch(e => { if (live) setError((e as Error).message); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return { data, error, reload: () => setN(x => x + 1), setData };
}

/* Re-runs `fn` every `ms` while `active` is true (background jobs, imports). */
export function usePoll(active: boolean, fn: () => void, ms = 4000) {
  useEffect(() => { if (!active) return; const t = setInterval(fn, ms); return () => clearInterval(t); }, [active, ms]); // eslint-disable-line react-hooks/exhaustive-deps
}
