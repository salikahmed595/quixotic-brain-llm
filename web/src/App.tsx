import { useCallback, useEffect, useState } from 'react';
import { api, onMfaRequired, onSessionExpired, storage } from './api';
import { Icon } from './icons';
import { pagePerm, Sidebar } from './components/Sidebar';
import { AppProvider, go, useApp, useRoute } from './state';
import { Loading, Overlays } from './ui';
import type { Me } from './types';
import { AuthPages, MfaScreen } from './pages/Auth';
import { Ask } from './pages/Ask';
import { PAGES } from './pages/admin';

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [mfa, setMfa] = useState<null | { mode: 'setup' | 'verify'; email: string }>(null);
  const [checking, setChecking] = useState(true);
  const [message, setMessage] = useState<string>();

  /* PRD §5: the server session decides everything — signed out, two-step sign-in still due, or in. */
  const boot = useCallback(async () => {
    setChecking(true);
    try {
      const s = await api<{ mfa: 'none' | 'setup' | 'verify'; email: string }>('/v1/auth/session');
      if (s.mfa !== 'none') { setMfa({ mode: s.mfa, email: s.email }); setMe(null); return; }
      setMfa(null); setMe(await api<Me>('/v1/auth/me')); setMessage(undefined);
    } catch (e) { setMe(null); setMfa(null); if ((e as { status?: number }).status !== 401) setMessage((e as Error).message); }
    finally { setChecking(false); }
  }, []);
  const logout = useCallback(async (expired?: boolean) => {
    if (!expired) await api('/v1/auth/logout', { method: 'POST' }).catch(() => {});
    setMe(null); setMfa(null); setMessage(expired ? 'Your session has ended. Please sign in again.' : undefined); go('ask');
  }, []);
  useEffect(() => { onSessionExpired(() => logout(true)); onMfaRequired(() => { boot(); }); boot(); }, [boot, logout]);

  return (<>
    {checking ? <div className="min-h-screen grid place-items-center"><Loading /></div>
      : me ? <AppProvider key={me.user_id} me={me} onLogout={() => logout()}><Shell /></AppProvider>
      : mfa ? <MfaScreen mode={mfa.mode} email={mfa.email} done={boot} cancel={() => logout()} />
      : <AuthPages onSignedIn={boot} initialMessage={message} />}
    <Overlays />
  </>);
}

const isMobile = () => window.matchMedia('(max-width: 900px)').matches;

/* PRD §4: fixed left sidebar (~283 px) + cream main panel. Tablet: collapsible; mobile: accessible drawer (§4.4). */
function Shell() {
  const { me } = useApp(); const route = useRoute();
  const [collapsed, setCollapsed] = useState(storage.get('qb_sb') === '0');
  const [drawer, setDrawer] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const perm = pagePerm(route.page);
  const page = route.page !== 'ask' && (!PAGES[route.page] || !perm || !me.permissions.includes(perm)) ? 'ask' : route.page;
  useEffect(() => { if (page !== route.page) history.replaceState(null, '', '#/ask'); }, [page, route.page]);
  useEffect(() => { setDrawer(false); }, [route.page, route.chat]);
  useEffect(() => { document.getElementById('main')?.scrollTo(0, 0); }, [page]);

  const close = () => { if (isMobile()) setDrawer(false); else { setCollapsed(true); storage.set('qb_sb', '0'); } };
  const open = () => { if (isMobile()) setDrawer(true); else { setCollapsed(false); storage.set('qb_sb', '1'); } };
  const newChat = () => { setResetKey(k => k + 1); go('ask'); setDrawer(false); };
  const Page = PAGES[page];

  return (
    <div className="flex h-screen bg-canvas">
      {drawer && <div className="fixed inset-0 z-40 bg-ink/40 min-[901px]:hidden" onClick={() => setDrawer(false)} />}
      <aside className={`flex-none w-[283px] h-screen border-r border-line z-50 transition-[margin,transform] duration-200
        max-[900px]:fixed max-[900px]:inset-y-0 max-[900px]:left-0 max-[900px]:w-[min(300px,86vw)] ${drawer ? 'max-[900px]:translate-x-0 max-[900px]:shadow-lift' : 'max-[900px]:-translate-x-[102%]'}
        ${collapsed ? 'min-[901px]:-ml-[283px]' : ''}`} aria-hidden={isMobile() ? !drawer : collapsed}>
        <Sidebar onClose={close} onNewChat={newChat} />
      </aside>
      <div id="main" className="flex-1 min-w-0 h-screen overflow-y-auto flex flex-col relative">
        <header className={`absolute top-0 left-0 z-10 p-2.5 ${collapsed ? '' : 'min-[901px]:hidden'}`}>
          <button className="w-11 h-11 grid place-items-center rounded-[10px] text-ink-2 hover:bg-orange-100 hover:text-orange" onClick={open} aria-label="Open sidebar">
            <Icon name="menu" size={22} />
          </button>
        </header>
        {page === 'ask' ? <Ask resetKey={resetKey} /> : <div className="pt-14 flex-1"><Page /></div>}
      </div>
    </div>
  );
}
