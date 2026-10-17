import { ReactNode, useEffect, useState } from 'react';
import { api, ApiError } from '../api';
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

type Screen = 'login' | 'signup' | 'checkEmail' | 'forgot' | 'resetSent';

/* Links from emails open #/verify?token=… and #/reset?token=… */
const linkToken = (kind: 'verify' | 'reset') => {
  const m = location.hash.match(new RegExp(`^#/${kind}\\?token=([\\w-]+)`));
  return m ? m[1] : null;
};
const clearLink = () => history.replaceState(null, '', location.pathname + location.search);

export function AuthPages({ onSignedIn, initialMessage }: { onSignedIn: () => void; initialMessage?: string }) {
  const [screen, setScreen] = useState<Screen>('login');
  const [msg, setMsg] = useState<string | undefined>(initialMessage);
  const [email, setEmail] = useState('');
  const verify = linkToken('verify'), reset = linkToken('reset');
  if (verify) return <VerifyEmail token={verify} done={m => { clearLink(); setMsg(m); setScreen('login'); }} />;
  if (reset) return <ResetPassword token={reset} done={m => { clearLink(); setMsg(m); setScreen('login'); }} />;
  if (screen === 'signup') return <Signup toLogin={() => { setMsg(undefined); setScreen('login'); }} done={e => { setEmail(e); setScreen('checkEmail'); }} />;
  if (screen === 'checkEmail') return <Status icon="mail" title="Check your email" back={() => setScreen('login')}>
    {/* PRD §5 FR-AUTH-02/03: verify the email; the account stays Pending until an administrator approves it */}
    We sent a link to <b>{email}</b>. Open it to confirm your email. After that, an administrator checks your request and decides
    which department information you can use. You can't use Quixotic AI until then.
  </Status>;
  if (screen === 'forgot') return <Forgot back={() => setScreen('login')} done={() => setScreen('resetSent')} />;
  if (screen === 'resetSent') return <Status icon="mail" title="Check your email" back={() => setScreen('login')}>
    If an active account uses that email or username, we sent it a link to choose a new password. The link works once.
  </Status>;
  return <Login message={msg} toSignup={() => setScreen('signup')} toForgot={() => setScreen('forgot')} onSignedIn={onSignedIn} />;
}

function Login({ message, toSignup, toForgot, onSignedIn }: { message?: string; toSignup: () => void; toForgot: () => void; onSignedIn: () => void }) {
  const [id, setId] = useState(''); const [pw, setPw] = useState(''); const a = useAction();
  const [info, setInfo] = useState<string | null>(null); const [unverified, setUnverified] = useState(false);
  useEffect(() => { if (message) setInfo(message); }, [message]);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); a.setError(null); setInfo(null); setUnverified(false);
    try {
      await api('/v1/auth/login', { method: 'POST', body: { identifier: id.trim(), password: pw } });
      onSignedIn();
    } catch (err) {
      const e2 = err as ApiError;
      if (e2.status === 403 && /verify your email/i.test(e2.message)) setUnverified(true);
      a.setError(e2.status === 401 ? 'Those details don’t match. Please try again.' : e2.message);
    }
  };
  const resend = () => api('/v1/auth/verify-email/resend', { method: 'POST', body: { identifier: id.trim() } })
    .then(() => { a.setError(null); setUnverified(false); setInfo('If your email is not verified yet, a new link is on its way.'); }).catch(e => a.setError(e.message));
  return (
    <Shell>
      <p className="text-center text-muted mb-5.5">Sign in to ask your company knowledge base.</p>
      <form onSubmit={submit} className="grid gap-3.5">
        {info && <Banner kind="ok">{info}</Banner>}
        {a.error && <Banner kind="err">{a.error}{unverified && <> <button type="button" className="underline font-semibold" onClick={resend}>Send the link again</button></>}</Banner>}
        <div className="field"><label htmlFor="lid">Email or username</label><input id="lid" className="input" autoComplete="username" required autoFocus value={id} onChange={e => setId(e.target.value)} /></div>
        <div className="field"><label htmlFor="lpw">Password</label><input id="lpw" className="input" type="password" autoComplete="current-password" required value={pw} onChange={e => setPw(e.target.value)} /></div>
        <button className="btn primary w-full !h-[46px] mt-1.5">Sign in</button>
      </form>
      <p className="text-center mt-4"><button className="text-muted hover:text-orange text-sm min-h-11 px-2" onClick={toForgot}>Forgot your password?</button></p>
      <p className="text-center text-muted mt-1">New here? <button className="text-orange font-bold min-h-11 px-1" onClick={toSignup}>Create an account</button></p>
    </Shell>
  );
}

function Signup({ toLogin, done }: { toLogin: () => void; done: (email: string) => void }) {
  const [depts, setDepts] = useState<{ id: string; name: string }[]>([]);
  const [f, setF] = useState({ n: '', u: '', m: '', p: '', r: '', d: '', ph: '' }); const a = useAction();
  useEffect(() => { api('/v1/auth/signup-options').then(r => setDepts(r.departments)).catch(() => {}); }, []);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (f.p !== f.r) { a.setError('The two passwords are not the same.'); return; }
    const email = f.m.trim().toLowerCase();
    a.run(() => api('/v1/auth/register', { method: 'POST', body: {
      full_name: f.n, username: f.u.trim().toLowerCase(), email, password: f.p, department_id: f.d, phone: f.ph.trim() || null } }))
      .then(ok => ok && done(email));
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
          <select id="su-d" className="select" required value={f.d} onChange={set('d')}><option value="" disabled>Choose your department</option>{depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
          <span className="hint">This is only a request. The person who approves you chooses your access.</span></div>
        <div className="field"><label htmlFor="su-ph">Phone <span className="text-muted font-normal">(optional)</span></label><input id="su-ph" className="input" type="tel" autoComplete="tel" maxLength={30} value={f.ph} onChange={set('ph')} /></div>
        <button className="btn primary w-full !h-[46px] mt-3" disabled={a.busy}>Request account</button>
      </form>
      <p className="text-center text-muted mt-4">Already approved? <button className="text-orange font-bold min-h-11 px-1" onClick={toLogin}>Sign in</button></p>
    </Shell>
  );
}

function VerifyEmail({ token, done }: { token: string; done: (message: string) => void }) {
  const [state, setState] = useState<'busy' | 'ok' | 'err'>('busy'); const [err, setErr] = useState('');
  useEffect(() => {
    api('/v1/auth/verify-email', { method: 'POST', body: { token } }).then(() => setState('ok')).catch(e => { setErr(e.message); setState('err'); });
  }, [token]);
  if (state === 'busy') return <Shell><p className="text-center text-muted py-6">Checking your link…</p></Shell>;
  return <Status icon={state === 'ok' ? 'check' : 'alert'} title={state === 'ok' ? 'Email confirmed' : 'Link not valid'}
    back={() => done(state === 'ok' ? 'Email confirmed. An administrator will approve your account soon.' : '')}>
    {state === 'ok' ? 'Thank you. An administrator still has to approve your account before you can sign in.' : err}
  </Status>;
}

function Forgot({ back, done }: { back: () => void; done: () => void }) {
  const [id, setId] = useState(''); const a = useAction();
  return (
    <Shell>
      <p className="text-center text-muted mb-5.5">Enter your email or username. We'll send a link to choose a new password.</p>
      <form className="grid gap-3.5" onSubmit={e => { e.preventDefault(); a.run(() => api('/v1/auth/password-reset', { method: 'POST', body: { identifier: id.trim() } })).then(ok => ok && done()); }}>
        {a.error && <Banner kind="err">{a.error}</Banner>}
        <div className="field"><label htmlFor="fp-id">Email or username</label><input id="fp-id" className="input" required autoFocus value={id} onChange={e => setId(e.target.value)} /></div>
        <button className="btn primary w-full !h-[46px]" disabled={a.busy}>Send link</button>
      </form>
      <p className="text-center mt-4"><button className="text-orange font-bold min-h-11 px-1" onClick={back}>Back to sign in</button></p>
    </Shell>
  );
}

function ResetPassword({ token, done }: { token: string; done: (message: string) => void }) {
  const [p, setP] = useState(''); const [r, setR] = useState(''); const a = useAction();
  return (
    <Shell>
      <p className="text-center text-muted mb-5.5">Choose a new password. You'll be signed out on every device.</p>
      <form className="grid gap-3.5" onSubmit={e => {
        e.preventDefault();
        if (p !== r) { a.setError('The two passwords are not the same.'); return; }
        a.run(() => api('/v1/auth/password-reset/confirm', { method: 'POST', body: { token, new_password: p } }))
          .then(ok => ok && done('Your password was changed. Sign in with the new one.'));
      }}>
        {a.error && <Banner kind="err">{a.error}</Banner>}
        <div className="field"><label htmlFor="rp-p">New password</label><input id="rp-p" className="input" type="password" required minLength={8} autoComplete="new-password" autoFocus value={p} onChange={e => setP(e.target.value)} /></div>
        <div className="field"><label htmlFor="rp-r">Confirm new password</label><input id="rp-r" className="input" type="password" required minLength={8} autoComplete="new-password" value={r} onChange={e => setR(e.target.value)} /></div>
        <button className="btn primary w-full !h-[46px]" disabled={a.busy}>Save password</button>
      </form>
    </Shell>
  );
}

/* PRD §5 FR-AUTH-06 admin MFA: a code from an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…). */
export function MfaScreen({ mode, email, done, cancel }: { mode: 'setup' | 'verify'; email: string; done: () => void; cancel: () => void }) {
  const [setup, setSetup] = useState<{ secret: string; qr_svg: string } | null>(null);
  const [code, setCode] = useState(''); const a = useAction();
  useEffect(() => { if (mode === 'setup') api('/v1/auth/mfa/setup').then(setSetup).catch(e => a.setError(e.message)); }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    a.run(() => api(mode === 'setup' ? '/v1/auth/mfa/enable' : '/v1/auth/mfa/verify', { method: 'POST', body: { code } })).then(ok => ok && done());
  };
  return (
    <Shell>
      <h2 className="text-center text-xl font-extrabold mt-2">Two-step sign-in</h2>
      <p className="text-center text-muted mb-4.5">{mode === 'setup'
        ? <>Administrator accounts need a code from an authenticator app. Scan this with the app on your phone, then enter the 6-digit code it shows.</>
        : <>Enter the 6-digit code from your authenticator app for <b>{email}</b>.</>}</p>
      {mode === 'setup' && setup && (
        <div className="grid justify-items-center gap-2 mb-4">
          <img src={setup.qr_svg} alt="QR code to add Quixotic AI to your authenticator app" className="w-44 h-44 rounded-xl border border-line" />
          <span className="hint text-center">Can't scan? Enter this key: <code className="select-all">{setup.secret}</code></span>
        </div>
      )}
      <form onSubmit={submit} className="grid gap-3.5">
        {a.error && <Banner kind="err">{a.error}</Banner>}
        <div className="field"><label htmlFor="mfa-c">6-digit code</label>
          <input id="mfa-c" className="input text-center tracking-[.3em] text-lg" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9 ]{6,7}" maxLength={7} required autoFocus value={code} onChange={e => setCode(e.target.value)} /></div>
        <button className="btn primary w-full !h-[46px]" disabled={a.busy}>{mode === 'setup' ? 'Turn on and continue' : 'Continue'}</button>
      </form>
      <p className="text-center mt-4"><button className="text-muted hover:text-orange text-sm min-h-11 px-2" onClick={cancel}>Sign out</button></p>
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
