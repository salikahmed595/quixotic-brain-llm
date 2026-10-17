import { createContext, ReactNode, useCallback, useContext, useEffect, useState, useSyncExternalStore } from 'react';
import { api } from './api';
import { RANK } from './ui';
import type { Chat, Department, Me } from './types';

/* ---------------- hash router: #/ask, #/chat/<id>, #/<admin page> ---------------- */
const subscribeHash = (fn: () => void) => { window.addEventListener('hashchange', fn); return () => window.removeEventListener('hashchange', fn); };
export function useRoute() {
  const hash = useSyncExternalStore(subscribeHash, () => location.hash);
  const [first, second] = hash.replace(/^#\/?/, '').split('?')[0].split('/');
  if (!first || first === 'ask') return { page: 'ask', chat: undefined as string | undefined };
  if (first === 'chat' && second) return { page: 'ask', chat: second };
  return { page: first, chat: undefined };
}
export const go = (path: string) => { location.hash = '#/' + path; };
/* Change the address without triggering navigation (a new chat just got its id). */
export const replaceRoute = (path: string) => { history.replaceState(null, '', '#/' + path); window.dispatchEvent(new HashChangeEvent('hashchange')); };

/* ---------------- signed-in app state ---------------- */
interface AppState {
  me: Me;
  setMe: (m: Me) => void;
  rank: number;
  /** departments this person may search/choose (PRD §6 FR-CHAT-06: only permitted scopes) */
  departments: Department[];
  /** every active department (for labels and admin pickers) */
  activeDepartments: Department[];
  chats: Chat[];
  reloadChats: () => void;
  setChats: (c: Chat[]) => void;
  counts: { requests: number; pending: number };
  setCounts: (c: Partial<{ requests: number; pending: number }>) => void;
  logout: () => void;
}
const Ctx = createContext<AppState | null>(null);
export const useApp = () => { const c = useContext(Ctx); if (!c) throw new Error('useApp outside provider'); return c; };

export function AppProvider({ me: initialMe, onLogout, children }: { me: Me; onLogout: () => void; children: ReactNode }) {
  const [me, setMe] = useState(initialMe);
  const [activeDepartments, setActive] = useState<Department[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [counts, setCountsState] = useState({ requests: 0, pending: 0 });
  const rank = RANK[me.role] ?? 0;

  const reloadChats = useCallback(() => {
    api<{ conversations: Chat[] }>('/v1/conversations').then(r => setChats(r.conversations)).catch(() => {});
  }, []);
  useEffect(() => {
    api<{ departments: Department[] }>('/v1/departments').then(r => setActive(r.departments.filter(d => d.status === 'active'))).catch(() => {});
    reloadChats();
    if (rank >= 2) {
      api<{ requests: unknown[] }>('/v1/access-requests').then(r => setCountsState(c => ({ ...c, requests: r.requests.length }))).catch(() => {});
      api<{ items: unknown[] }>('/v1/knowledge?status=pending_review&limit=100').then(r => setCountsState(c => ({ ...c, pending: r.items.length }))).catch(() => {});
    }
  }, [rank, reloadChats]);

  const departments = me.role === 'administrator' ? activeDepartments : activeDepartments.filter(d => me.department_ids.includes(d.id));
  const value: AppState = {
    me, setMe, rank, departments, activeDepartments, chats, setChats, reloadChats, counts,
    setCounts: c => setCountsState(old => ({ ...old, ...c })), logout: onLogout,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
