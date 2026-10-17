import { useEffect, useState } from 'react';
import { api } from '../api';
import { Icon } from '../icons';
import type { useApp } from '../state';
import { Avatar, Banner, confirmModal, openModal, ROLE_LABEL, toast, useAction } from '../ui';

type App = ReturnType<typeof useApp>;

/* PRD §5 FR-AUTH-07: the person sees name, departments and effective scope; role and access are set by an admin. */
async function toAvatar(file: File): Promise<string> {
  if (!/^image\//.test(file.type)) throw new Error('Please choose an image file (PNG, JPG or WebP).');
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('That image could not be read. Try a PNG or JPG.')); i.src = url; });
    const size = 256, side = Math.min(img.width, img.height), c = document.createElement('canvas'); c.width = c.height = size;
    c.getContext('2d')!.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);
    return c.toDataURL('image/jpeg', 0.85);
  } finally { URL.revokeObjectURL(url); }
}

export function profileModal(app: App) { openModal('Profile', close => <Profile app={app} close={close} />); }
function Profile({ app, close }: { app: App; close: () => void }) {
  const m = app.me; const [name, setName] = useState(m.full_name);
  const [avatar, setAvatar] = useState<string | null | undefined>(m.avatar); const a = useAction();
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, string> = { full_name: name };
    if (avatar === null && m.avatar) body.avatar = ''; else if (avatar && avatar !== m.avatar) body.avatar = avatar;
    a.run(async () => { const me = await api('/v1/auth/profile', { method: 'PATCH', body }); app.setMe(me); close(); toast('Profile saved'); });
  };
  return (
    <form onSubmit={save} className="grid gap-4.5">
      <div className="flex items-center gap-4.5">
        <Avatar user={{ full_name: name, avatar }} size={84} />
        <div className="grid gap-2">
          <div className="flex flex-wrap gap-2">
            <label className="btn sm cursor-pointer"><Icon name="cloud" size={15} /> Upload photo
              <input type="file" accept="image/*" hidden onChange={async e => { const f = e.target.files?.[0]; if (!f) return; try { setAvatar(await toAvatar(f)); a.setError(null); } catch (err) { a.setError((err as Error).message); } }} />
            </label>
            <button type="button" className="btn ghost sm" onClick={() => setAvatar(null)}>Remove</button>
          </div>
          <span className="hint">PNG, JPG or WebP. It is cropped to a small square.</span>
        </div>
      </div>
      <div className="field"><label htmlFor="pf-name">Full name</label><input id="pf-name" className="input" required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></div>
      <dl className="kv">
        <dt>Email</dt><dd>{m.email}</dd><dt>Employee ID</dt><dd>{m.employee_id}</dd><dt>Role</dt><dd>{ROLE_LABEL[m.role]}</dd>
        <dt>Access</dt><dd>{m.departments.length ? m.departments.map(d => <span key={d.id} className="chip m-0.5">{d.name}</span>) : <span className="hint">None yet — ask an administrator</span>}</dd>
      </dl>
      <p className="hint">Your role and access are set by an administrator. They decide which company knowledge your answers can use.</p>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={a.busy}>Save</button></div>
    </form>
  );
}

const PREF_STYLE = [['concise', 'Short and to the point'], ['balanced', 'Balanced'], ['detailed', 'Detailed, step by step']];
const PREF_TONE = [['professional', 'Professional'], ['friendly', 'Friendly'], ['direct', 'Direct']];
const PREF_LANG = [['auto', 'Same language as my question'], ['english', 'Always English'], ['urdu', 'Always Urdu (اردو)'], ['roman_urdu', 'Always Roman Urdu']];

export function personalizationModal(app: App) { openModal('Personalization', close => <Personalization app={app} close={close} />, { wide: true }); }
function Personalization({ app, close }: { app: App; close: () => void }) {
  const p = app.me.preferences || {};
  const [f, setF] = useState({ answer_style: p.answer_style || 'balanced', tone: p.tone || 'professional', language: p.language || 'auto', about_me: p.about_me || '', instructions: p.instructions || '', learn: p.learn !== false });
  const [learned, setLearned] = useState<{ liked: number; disliked: number; hints: string[] } | null>(null);
  const a = useAction();
  const loadLearned = () => api('/v1/auth/learned').then(setLearned).catch(() => setLearned(null));
  useEffect(() => { loadLearned(); }, []);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    a.run(async () => { const prefs = await api('/v1/auth/preferences', { method: 'PUT', body: f }); app.setMe({ ...app.me, preferences: prefs }); close(); toast('Saved. Your next answers will follow this.'); });
  };
  const opts = (list: string[][]) => list.map(o => <option key={o[0]} value={o[0]}>{o[1]}</option>);
  return (
    <form onSubmit={save} className="grid gap-4">
      <p className="hint">Make Quixotic AI answer the way you like. This changes how answers are written — never what the company knowledge says, and never what you are allowed to see.</p>
      <div className="grid grid-cols-2 gap-3">
        <div className="field"><label>Answer length</label><select className="select" value={f.answer_style} onChange={set('answer_style')}>{opts(PREF_STYLE)}</select></div>
        <div className="field"><label>Tone</label><select className="select" value={f.tone} onChange={set('tone')}>{opts(PREF_TONE)}</select></div>
      </div>
      <div className="field"><label>Reply language</label><select className="select" value={f.language} onChange={set('language')}>{opts(PREF_LANG)}</select></div>
      <div className="field"><label>About you and your work <span className="hint">(optional)</span></label>
        <textarea className="textarea min-h-20" maxLength={500} value={f.about_me} onChange={set('about_me')} placeholder="e.g. I lead the Karachi sales team and mostly handle price objections." /></div>
      <div className="field"><label>How should answers be written? <span className="hint">(optional)</span></label>
        <textarea className="textarea min-h-20" maxLength={500} value={f.instructions} onChange={set('instructions')} placeholder="e.g. Give me bullet points and one example script I can say to the customer." /></div>
      <div className="rounded-2xl bg-canvas border border-line p-3.5">
        <label className="check"><input type="checkbox" checked={f.learn} onChange={e => setF({ ...f, learn: e.target.checked })} /> <b>Learn from my 👍 / 👎</b></label>
        {learned && <div className="hint mt-2">
          {learned.hints.length
            ? <p>From your ratings ({learned.liked} 👍, {learned.disliked} 👎) I noticed you like: <b>{learned.hints.join(', ')}</b>. I use this for your answers.</p>
            : <p>Nothing learned yet ({learned.liked} 👍, {learned.disliked} 👎 so far). After a few of each I look for patterns, such as short answers or bullet points.</p>}
          {(learned.liked > 0 || learned.disliked > 0) && <button type="button" className="btn sm mt-2" onClick={async () => {
            try { await api('/v1/auth/learned/reset', { method: 'POST' }); toast('Forgotten. I start fresh from your next rating.'); loadLearned(); } catch (e) { toast((e as Error).message); }
          }}>Forget what I learned</button>}
        </div>}
      </div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={a.busy}>Save</button></div>
    </form>
  );
}

export function settingsModal(app: App, onChatsGone: () => void) { openModal('Settings', close => <Settings app={app} close={close} onChatsGone={onChatsGone} />); }
function Settings({ app, close, onChatsGone }: { app: App; close: () => void; onChatsGone: () => void }) {
  const [pw, setPw] = useState({ c: '', n: '', r: '' }); const [ok, setOk] = useState(false); const a = useAction();
  const change = (e: React.FormEvent) => {
    e.preventDefault(); setOk(false);
    if (pw.n !== pw.r) { a.setError('The two new passwords are not the same.'); return; }
    a.run(() => api('/v1/auth/password', { method: 'POST', body: { current_password: pw.c, new_password: pw.n } })).then(done => { if (done) { setPw({ c: '', n: '', r: '' }); setOk(true); } });
  };
  return (
    <div className="grid gap-5.5">
      <form onSubmit={change} className="grid gap-3">
        <h4 className="text-[15px] font-bold flex items-center gap-2"><Icon name="lock" size={16} /> Change password</h4>
        <div className="field"><label>Current password</label><input className="input" type="password" required autoComplete="current-password" value={pw.c} onChange={e => setPw({ ...pw, c: e.target.value })} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div className="field"><label>New password</label><input className="input" type="password" required minLength={8} autoComplete="new-password" value={pw.n} onChange={e => setPw({ ...pw, n: e.target.value })} /></div>
          <div className="field"><label>Repeat new password</label><input className="input" type="password" required minLength={8} autoComplete="new-password" value={pw.r} onChange={e => setPw({ ...pw, r: e.target.value })} /></div>
        </div>
        <span className="hint">At least 8 characters. Use something you don't use anywhere else.</span>
        {a.error && <Banner kind="err">{a.error}</Banner>}
        {ok && <Banner kind="ok">Password updated. Use it the next time you sign in.</Banner>}
        <div className="flex justify-end"><button className="btn primary" disabled={a.busy}>Update password</button></div>
      </form>
      <div className="grid gap-2.5 border-t border-line pt-4.5">
        <h4 className="text-[15px] font-bold flex items-center gap-2"><Icon name="msg" size={16} /> Your chats</h4>
        <p className="hint">Chats are private to you. Deleting them removes the history and what the assistant remembers from it. It can't be undone.</p>
        <div><button className="btn bad" onClick={() => { close(); confirmModal('Delete all chats?', 'All your chats will be deleted. This can’t be undone.', 'Delete everything', async () => {
          const r = await api<{ deleted: number }>('/v1/chats', { method: 'DELETE' }); app.setChats([]); onChatsGone(); toast(`${r.deleted} chat${r.deleted === 1 ? '' : 's'} deleted`);
        }); }}><Icon name="trash" size={16} /> Delete all my chats</button></div>
      </div>
      <div className="flex items-center justify-between border-t border-line pt-4">
        <span className="hint">Signed in as {app.me.email}</span>
        <button className="btn" onClick={() => { close(); app.logout(); }}><Icon name="out" size={16} /> Log out</button>
      </div>
    </div>
  );
}
