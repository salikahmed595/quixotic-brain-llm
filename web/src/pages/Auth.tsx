import { ReactNode, useEffect, useState } from 'react';
import { api, ApiError, setToken } from '../api';
import { Brand, Icon } from '../icons';
import { Banner, useAction } from '../ui';

/* PRD §5: public pages styled like the screenshots (cream canvas, white card, orange accents). */
function Shell({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return (
    <main className="min-h-screen grid place-items-center p-5 bg-[radial-gradient(900px_500px_at_50%_-10%,#ffe6d2,transparent),var(--color-canvas)]">
      <div className={`bg-white rounded-3xl shadow-lift p-8.5 w-full ${wide ? 'max-w-[460px]' : 'max-w-[420px]'}`}>
        <div className="flex justify-center pb-1.5"><Brand size={22} /></div>
        {children}
      </div>
    </main>
  );
}

type Screen = 'login' | 'signup' | 'pending' | 'rejected';

export function AuthPages({ onSignedIn, initialMessage }: { onSignedIn: () => void; initialMessage?: string }) {
  const [screen, setScreen] = useState<Screen>('login');
  const [msg, setMsg] = useState<string | undefined>(initialMessage);
  const [username, setUsername] = useState('');
  if (screen === 'signup') return <Signup toLogin={() => { setMsg(undefined); setScreen('login'); }} done={u => { setUsername(u); setScreen('pending'); }} />;
  if (screen === 'pending') return <Status icon="clock" title="Waiting for approval" back={() => setScreen('login')}>
    {/* PRD §5 FR-AUTH-03: clear pending page; no access to chat or knowledge until approved */}
    Your account request was sent. An administrator will check it and decide which department information you can use.
    You can't use Quixotic AI until then. {username && <>Once approved, sign in with <b>{username}</b> and your password.</>}
  </Status>;
  if (screen === 'rejected') return <Status icon="lock" title="Account not approved" back={() => setScreen('login')}>
    {/* PRD §5 FR-AUTH-05: tell rejected users how to get help, without revealing internal data */}
    Your account request was not approved. If you think this is a mistake, please contact your administrator.
  </Status>;
  return <Login message={msg} toSignup={() => setScreen('signup')} onSignedIn={onSignedIn}
    onPending={() => setScreen('pending')} onRejected={() => setScreen('rejected')} />;
}

function Login({ message, toSignup, onSignedIn, onPending, onRejected }: { message?: string; toSignup: () => void; onSignedIn: () => void; onPending: () => void; onRejected: () => void }) {
  const [id, setId] = useState(''); const [pw, setPw] = useState(''); const a = useAction();
  useEffect(() => { if (message) a.setError(message); }, [message]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); a.setError(null);
    try {
      const r = await api<{ access_token: string }>('/v1/auth/login', { method: 'POST', body: { identifier: id.trim(), password: pw } });
      setToken(r.access_token); onSignedIn();
    } catch (err) {
      const e2 = err as ApiError;
      if (e2.status === 403 && /waiting for approval/i.test(e2.message)) return onPending();
      if (e2.status === 403 && /not approved/i.test(e2.message)) return onRejected();
      a.setError(e2.status === 401 ? 'Those details don’t match. Please try again.' : e2.message);
    }
  };
  return (
    <Shell>
      <p className="text-center text-muted mb-5.5">Sign in to ask your company knowledge base.</p>
      <form onSubmit={submit} className="grid gap-3.5">
        {a.error && <Banner kind="err">{a.error}</Banner>}
        <div className="field"><label htmlFor="lid">Email or username</label><input id="lid" className="input" autoComplete="username" required autoFocus value={id} onChange={e => setId(e.target.value)} /></div>
        <div className="field"><label htmlFor="lpw">Password</label><input id="lpw" className="input" type="password" autoComplete="current-password" required value={pw} onChange={e => setPw(e.target.value)} /></div>
        <button className="btn primary w-full !h-[46px] mt-1.5">Sign in</button>
      </form>
      <p className="text-center text-muted mt-4.5">New here? <button className="text-orange font-bold" onClick={toSignup}>Create an account</button></p>
    </Shell>
  );
}

function Signup({ toLogin, done }: { toLogin: () => void; done: (username: string) => void }) {
  const [depts, setDepts] = useState<{ id: string; name: string }[]>([]);
  const [f, setF] = useState({ n: '', u: '', m: '', p: '', r: '', d: '' }); const a = useAction();
  useEffect(() => { api('/v1/auth/signup-options').then(r => setDepts(r.departments)).catch(() => {}); }, []);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (f.p !== f.r) { a.setError('The two passwords are not the same.'); return; }
    const username = f.u.trim().toLowerCase();
    a.run(() => api('/v1/auth/register', { method: 'POST', body: { full_name: f.n, username, email: f.m.trim(), password: f.p, department_id: f.d || null } }))
      .then(ok => ok && done(username));
  };
  return (
    <Shell wide>
      <p className="text-center text-muted mb-5.5">Create your account. An administrator approves it and decides which department information you can use.</p>
      <form onSubmit={submit} className="grid gap-3">
        {a.error && <Banner kind="err">{a.error}</Banner>}
        <div className="field"><label htmlFor="su-n">Full name</label><input id="su-n" className="input" required minLength={2} maxLength={80} autoComplete="name" autoFocus value={f.n} onChange={set('n')} /></div>
        <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
          <div className="field"><label htmlFor="su-u">Choose a username</label><input id="su-u" className="input" required minLength={3} maxLength={30} autoComplete="username" autoCapitalize="none" placeholder="e.g. nadia.khan" value={f.u} onChange={set('u')} /></div>
          <div className="field"><label htmlFor="su-m">Work email</label><input id="su-m" className="input" type="email" required autoComplete="email" value={f.m} onChange={set('m')} /></div>
        </div>
        <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
          <div className="field"><label htmlFor="su-p">Password</label><input id="su-p" className="input" type="password" required minLength={8} autoComplete="new-password" value={f.p} onChange={set('p')} /></div>
          <div className="field"><label htmlFor="su-r">Confirm password</label><input id="su-r" className="input" type="password" required minLength={8} autoComplete="new-password" value={f.r} onChange={set('r')} /></div>
        </div>
        <div className="field"><label htmlFor="su-d">Department you work in</label>
          <select id="su-d" className="select" value={f.d} onChange={set('d')}><option value="">Not sure / not listed</option>{depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
          <span className="hint">This is only a request. The person who approves you chooses your access.</span></div>
        <button className="btn primary w-full !h-[46px] mt-3" disabled={a.busy}>Request account</button>
      </form>
      <p className="text-center text-muted mt-4">Already approved? <button className="text-orange font-bold" onClick={toLogin}>Sign in</button></p>
    </Shell>
  );
}

function Status({ icon, title, children, back }: { icon: string; title: string; children: ReactNode; back: () => void }) {
  return (
    <Shell>
      <div className="empty !py-4.5"><div className="ico"><Icon name={icon} size={24} /></div><h3>{title}</h3><p>{children}</p></div>
      <button className="btn primary w-full !h-[46px]" onClick={back}>Back to sign in</button>
    </Shell>
  );
}
