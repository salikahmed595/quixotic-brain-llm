import { useState } from 'react';
import { api } from '../../api';
import { Icon } from '../../icons';
import { useApp } from '../../state';
import type { Department, Role } from '../../types';
import { Avatar, Banner, confirmModal, DeptChecks, Empty, fmtDate, Loading, openDrawer, openModal, PageHead, ROLE_LABEL, toast, useAction, useLoad } from '../../ui';

const ROLES = Object.keys(ROLE_LABEL) as Role[];
/* PRD §5 FR-AUTH-05 */
const STATE: Record<string, [string, string]> = {
  pending: ['Pending', 'amber'], active: ['Active', 'green'], rejected: ['Rejected', 'red'], suspended: ['Suspended', 'red'], deactivated: ['Deactivated', ''],
};
const StateChip = ({ s }: { s: string }) => { const [l, c] = STATE[s] || [s, '']; return <span className={`chip dot ${c}`}>{l}</span>; };
const activeDepts = () => api<{ departments: Department[] }>('/v1/departments').then(r => r.departments);

/* ---------------- PRD §5 FR-AUTH-04 / §7 Access requests ---------------- */
type Req = { id: string; full_name: string; email: string; phone?: string | null; username: string; requested_department?: string;
  requested_department_id?: string; created_at: string; email_verified: boolean };

export function RequestsPage() {
  const { setCounts } = useApp();
  const { data, error, reload } = useLoad(() => Promise.all([
    api<{ requests: Req[] }>('/v1/admin/access-requests').then(r => { setCounts({ requests: r.requests.length }); return r.requests; }),
    activeDepts(),
  ]));
  const [rq, ds] = data || [null, []];
  const approve = (r: Req) => openModal(`Approve ${r.full_name}`, close => <Approve r={r} depts={ds} close={close} done={reload} />);
  const reject = (r: Req) => openModal('Reject this request?', close => <Reject r={r} close={close} done={reload} />);
  return (
    <div className="page">
      <PageHead title="Access requests" sub="People who signed up. Check who they are, then choose their role and which departments' information they can use." />
      {error ? <Banner kind="err">{error}</Banner> : !rq ? <Loading /> : rq.length ? (
        <div className="table-wrap"><table><thead><tr><th>Person</th><th>Username</th><th>Department asked for</th><th>Email</th><th>Requested</th><th /></tr></thead>
          <tbody>{rq.map(r => (
            <tr key={r.id}><td><b>{r.full_name}</b><div className="hint">{r.email}{r.phone ? ` · ${r.phone}` : ''}</div></td><td>{r.username}</td>
              <td>{r.requested_department ? <span className="chip">{r.requested_department}</span> : <span className="hint">—</span>}</td>
              <td>{r.email_verified ? <span className="chip dot green">Verified</span> : <span className="chip dot amber" title="They must open the link we emailed before you can approve them">Not verified yet</span>}</td>
              <td>{fmtDate(r.created_at)}</td>
              <td><div className="flex justify-end gap-2">
                <button className="btn good sm" disabled={!r.email_verified} title={r.email_verified ? '' : 'Waiting for email verification'} onClick={() => approve(r)}><Icon name="check" size={15} /> Approve</button>
                <button className="btn bad sm" onClick={() => reject(r)}><Icon name="x" size={15} /> Reject</button></div></td></tr>))}</tbody></table></div>
      ) : <Empty icon="check" title="No requests waiting" text="When someone signs up, their request appears here." />}
    </div>
  );
}

function Approve({ r, depts, close, done }: { r: Req; depts: Department[]; close: () => void; done: () => void }) {
  const [role, setRole] = useState<Role>('employee'); const [publish, setPublish] = useState(false); const [note, setNote] = useState('');
  const [ids, setIds] = useState<string[]>(r.requested_department_id && depts.some(d => d.id === r.requested_department_id) ? [r.requested_department_id] : []);
  const a = useAction();
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ids.length) { a.setError('Tick at least one department.'); return; }
    a.run(() => api(`/v1/admin/access-requests/${r.id}/approve`, { method: 'POST', body: { role, department_ids: ids, can_publish: publish, note: note.trim() || null } }))
      .then(ok => { if (ok) { close(); toast(`${r.full_name} can now sign in`); done(); } });
  };
  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="field"><label htmlFor="ap-r">Role</label><select id="ap-r" className="select" value={role} onChange={e => setRole(e.target.value as Role)}>{ROLES.map(x => <option key={x} value={x}>{ROLE_LABEL[x]}</option>)}</select></div>
      {role === 'knowledge_admin' && <label className="check"><input type="checkbox" checked={publish} onChange={e => setPublish(e.target.checked)} /> Can publish approved knowledge (publisher permission)</label>}
      <div className="field"><label>Can see knowledge of <span className="hint">(at least one)</span></label><DeptChecks depts={depts} value={ids} onChange={setIds} />
        <span className="hint">“Company Wide” is never given automatically: tick every department only if this person really needs all of them.</span></div>
      <div className="field"><label htmlFor="ap-n">Note <span className="hint">(optional, kept in the record)</span></label><input id="ap-n" className="input" maxLength={500} value={note} onChange={e => setNote(e.target.value)} /></div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn good" disabled={a.busy}>Approve</button></div>
    </form>
  );
}

function Reject({ r, close, done }: { r: Req; close: () => void; done: () => void }) {
  const [note, setNote] = useState(''); const a = useAction();
  return (<>
    <p className="text-ink-2 mb-3"><b>{r.full_name}</b> will not be able to sign in. They are told to contact an administrator.</p>
    <div className="field mb-4"><label htmlFor="rj-n">Reason <span className="hint">(optional, internal)</span></label><input id="rj-n" className="input" maxLength={500} value={note} onChange={e => setNote(e.target.value)} /></div>
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button>
      <button className="btn bad" disabled={a.busy} onClick={() => a.run(() => api(`/v1/admin/access-requests/${r.id}/reject`, { method: 'POST', body: { note: note.trim() || null } }))
        .then(ok => { if (ok) { close(); toast('Rejected'); done(); } })}>Reject</button></div>
  </>);
}

/* ---------------- PRD §7 Users: search/add/invite/edit/suspend/deactivate; roles, departments, last login, state, audit ---------------- */
type User = { id: string; full_name: string; email: string; employee_id: string; role: Role; department_ids: string[]; departments: string[];
  account_status: string; can_publish: boolean; last_login_at?: string | null; mfa_enabled: boolean; avatar?: string | null };

export function UsersPage() {
  const { me } = useApp();
  const { data, error, reload, setData } = useLoad(() => Promise.all([api<{ users: User[] }>('/v1/admin/users').then(r => r.users), activeDepts()]));
  const [q, setQ] = useState(''); const [role, setRole] = useState(''); const [dept, setDept] = useState(''); const [state, setState] = useState('');
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [users, depts] = data || [null, []];
  const shown = (users || []).filter(u => (!role || u.role === role) && (!state || u.account_status === state)
    && (!dept || (dept === '_none' ? !u.department_ids.length : u.department_ids.includes(dept)))
    && (!q || [u.full_name, u.email, u.employee_id].some(x => String(x).toLowerCase().includes(q.toLowerCase()))));
  const toggle = (id: string, on: boolean) => { const s = new Set(sel); if (on) s.add(id); else s.delete(id); setSel(s); };
  const patch = async (u: User, body: object, msg?: string) => {
    try { await api(`/v1/admin/users/${u.id}`, { method: 'PATCH', body }); if (msg) toast(msg); reload(); } catch (e) { toast((e as Error).message); reload(); }
  };
  const access = (u: User) => openModal(`What can ${u.full_name} see?`, close => <AccessEdit depts={depts} initial={u.department_ids} close={close}
    save={ids => patch(u, { department_ids: ids }, 'Saved')} />);
  const bulk = (add: boolean) => openModal(add ? `Give ${sel.size} people access` : `Remove access from ${sel.size} people`, close => <AccessEdit depts={depts} initial={[]} close={close}
    note={add ? 'They will be able to see the knowledge of the departments you tick (their answers use it right away).' : 'They will no longer see the knowledge of the departments you tick.'}
    okLabel={add ? 'Give access' : 'Remove access'} requireOne
    save={async ids => { await api('/v1/admin/users/bulk-departments', { method: 'POST', body: { user_ids: [...sel], [add ? 'add' : 'remove']: ids } }); toast('Access updated'); setSel(new Set()); reload(); }} />);
  const add = () => openModal('Add user', close => <AddUser depts={depts} close={close} done={reload} />, { wide: true });
  const status = (u: User, to: string) => openModal(to === 'active' ? `Reactivate ${u.full_name}?` : `${to === 'suspended' ? 'Suspend' : 'Deactivate'} ${u.full_name}?`,
    close => <StatusChange u={u} to={to} close={close} done={reload} />);

  return (
    <div className="page">
      <PageHead title="Users" sub="Who can sign in, their role, and which knowledge each person can see — access follows departments.">
        <button className="btn primary" onClick={add}><Icon name="plus" size={17} /> Add user</button>
      </PageHead>
      <div className="flex flex-wrap gap-3 mb-3">
        <div className="relative flex-1 min-w-[220px]"><input className="input !pl-10" placeholder="Search by name, email or username…" aria-label="Search users" value={q} onChange={e => setQ(e.target.value)} />
          <span className="absolute left-3.5 top-3 text-muted"><Icon name="search" /></span></div>
        <select className="select !w-44" value={role} onChange={e => setRole(e.target.value)} aria-label="Role"><option value="">All roles</option>{ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select>
        <select className="select !w-40" value={state} onChange={e => setState(e.target.value)} aria-label="State"><option value="">Any state</option>{['active', 'suspended', 'deactivated', 'rejected'].map(s => <option key={s} value={s}>{STATE[s][0]}</option>)}</select>
        <select className="select !w-[200px]" value={dept} onChange={e => setDept(e.target.value)} aria-label="Department">
          <option value="">Any department</option>{depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}<option value="_none">No department</option></select>
      </div>
      {sel.size > 0 && (
        <div className="card flex flex-wrap items-center gap-2.5 !py-2.5 !px-3.5 mb-3 !border-orange"><b>{sel.size} selected</b><span className="flex-1" />
          <button className="btn sm primary" onClick={() => bulk(true)}>Give access to a department…</button><button className="btn sm" onClick={() => bulk(false)}>Remove access…</button>
          <button className="btn ghost sm" onClick={() => setSel(new Set())}>Clear</button></div>
      )}
      {error ? <Banner kind="err">{error}</Banner> : !users ? <Loading /> : shown.length ? (<>
        <div className="hint mb-2">Showing {shown.length} of {users.length} people</div>
        <div className="table-wrap"><table><thead><tr>
          <th className="w-9"><input type="checkbox" aria-label="Select everyone shown" checked={shown.every(u => sel.has(u.id))} onChange={e => { const s = new Set(sel); shown.forEach(u => e.target.checked ? s.add(u.id) : s.delete(u.id)); setSel(s); }} /></th>
          <th>Name</th><th>Role</th><th>Can see knowledge of</th><th>State</th><th>Last sign-in</th><th /></tr></thead>
          <tbody>{shown.map(u => {
            const self = u.id === me.user_id;
            return (
              <tr key={u.id}>
                <td><input type="checkbox" aria-label={`Select ${u.full_name}`} checked={sel.has(u.id)} onChange={e => toggle(u.id, e.target.checked)} /></td>
                <td><button className="flex items-center gap-3 text-left" onClick={() => openUser(u.id, reload)}><Avatar user={u} size={32} /><div><b>{u.full_name}</b><div className="hint">{u.email} · {u.employee_id}</div></div></button></td>
                <td><select className="select !h-9 !w-[170px]" aria-label={`Role of ${u.full_name}`} value={u.role} disabled={self} title={self ? 'You cannot change your own role' : ''}
                  onChange={e => { const r = e.target.value as Role; setData([users.map(x => x.id === u.id ? { ...x, role: r } : x), depts]); patch(u, { role: r }, 'Role updated'); }}>
                  {ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select>
                  {u.can_publish && <div className="hint mt-1">Publisher</div>}</td>
                <td>{['knowledge_admin', 'system_admin', 'founder_ceo'].includes(u.role) ? <span className="chip orange">Every department ({ROLE_LABEL[u.role]})</span>
                  : u.departments.length ? u.departments.map(d => <span key={d} className="chip m-0.5">{d}</span>) : <span className="hint">Nothing yet</span>}</td>
                <td><StateChip s={u.account_status} /></td>
                <td className="whitespace-nowrap">{u.last_login_at ? fmtDate(u.last_login_at) : <span className="hint">Never</span>}</td>
                <td><div className="flex gap-2 justify-end"><button className="btn sm" onClick={() => access(u)}>Access</button>
                  {!self && u.account_status === 'active' && <button className="btn ghost sm" onClick={() => status(u, 'suspended')}>Suspend</button>}
                  {!self && u.account_status === 'suspended' && <button className="btn ghost sm" onClick={() => status(u, 'active')}>Reactivate</button>}
                  {!self && u.account_status === 'deactivated' && <button className="btn ghost sm" onClick={() => status(u, 'active')}>Reactivate</button>}
                </div></td>
              </tr>);
          })}</tbody></table></div>
      </>) : <Empty icon="users" title={users.length ? 'No one matches' : 'No users'} text={users.length ? 'Try a different search or filter.' : 'Add the first user.'} />}
    </div>
  );
}

function StatusChange({ u, to, close, done }: { u: User; to: string; close: () => void; done: () => void }) {
  const [note, setNote] = useState(''); const a = useAction();
  const text = to === 'suspended' ? 'They are signed out everywhere right away and cannot sign in until you reactivate them.'
    : to === 'deactivated' ? 'The account is closed: they are signed out everywhere and cannot sign in. You can reactivate it later.'
    : 'They can sign in again with their existing role and departments.';
  return (<>
    <p className="text-ink-2 mb-3">{text}</p>
    <div className="field mb-4"><label htmlFor="st-n">Reason <span className="hint">(kept in the account history)</span></label><input id="st-n" className="input" maxLength={500} value={note} onChange={e => setNote(e.target.value)} /></div>
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-between gap-3">
      {to === 'suspended' ? <button className="btn ghost" onClick={() => a.run(() => api(`/v1/admin/users/${u.id}/status`, { method: 'POST', body: { status: 'deactivated', note: note.trim() || null } })).then(ok => { if (ok) { close(); toast('Deactivated'); done(); } })}>Deactivate instead</button> : <span />}
      <div className="flex gap-3"><button className="btn" onClick={close}>Cancel</button>
        <button className={`btn ${to === 'active' ? 'good' : 'bad'}`} disabled={a.busy} onClick={() => a.run(() => api(`/v1/admin/users/${u.id}/status`, { method: 'POST', body: { status: to, note: note.trim() || null } }))
          .then(ok => { if (ok) { close(); toast(STATE[to][0]); done(); } })}>{to === 'active' ? 'Reactivate' : STATE[to][0].replace(/ed$/, '')}</button></div>
    </div>
  </>);
}

type UserDetail = User & { phone?: string | null; created_at: string; email_verified_at?: string | null; decision_note?: string | null;
  status_history: { from_status?: string | null; to_status: string; note?: string | null; at: string; actor?: string | null }[];
  audit: { id: number; at: string; event: string; actor_label?: string | null; detail: Record<string, unknown> }[] };

async function openUser(id: string, refresh: () => void) {
  try {
    const u = await api<UserDetail>(`/v1/admin/users/${id}`);
    openDrawer(close => <UserDrawer u={u} close={close} refresh={refresh} />);
  } catch (e) { toast((e as Error).message); }
}

function UserDrawer({ u, close, refresh }: { u: UserDetail; close: () => void; refresh: () => void }) {
  const resetMfa = () => confirmModal('Reset two-step sign-in?', <>For a lost phone. <b>{u.full_name}</b> is signed out and sets it up again at the next sign-in.</>, 'Reset', async () => {
    await api(`/v1/admin/users/${u.id}/mfa-reset`, { method: 'POST' }); toast('Two-step sign-in reset'); close(); refresh();
  });
  return (<>
    <div className="flex items-center gap-3.5 mb-4"><Avatar user={u} size={48} /><div className="min-w-0 flex-1"><h2 className="text-xl font-extrabold truncate">{u.full_name}</h2>
      <div className="hint">{u.email} · {u.employee_id}{u.phone ? ` · ${u.phone}` : ''}</div></div>
      <button className="btn ghost sm" onClick={close} aria-label="Close"><Icon name="x" size={18} /></button></div>
    <dl className="kv text-[13.5px] mb-5">
      <dt>Role</dt><dd>{ROLE_LABEL[u.role]}{u.can_publish ? ' · Publisher' : ''}</dd>
      <dt>State</dt><dd><StateChip s={u.account_status} /></dd>
      <dt>Departments</dt><dd>{u.departments.join(', ') || '—'}</dd>
      <dt>Email verified</dt><dd>{u.email_verified_at ? fmtDate(u.email_verified_at) : 'No'}</dd>
      <dt>Two-step sign-in</dt><dd>{u.mfa_enabled ? <>On <button className="text-orange font-semibold ml-2" onClick={resetMfa}>Reset</button></> : 'Off'}</dd>
      <dt>Last sign-in</dt><dd>{u.last_login_at ? fmtDate(u.last_login_at) : 'Never'}</dd>
      <dt>Created</dt><dd>{fmtDate(u.created_at)}</dd>
    </dl>
    <h3 className="font-bold mb-2">Account history</h3>
    <ol className="grid gap-2 mb-5">{u.status_history.map((h, i) => (
      <li key={i} className="text-[13.5px]"><StateChip s={h.to_status} /> <span className="hint">{fmtDate(h.at)}{h.actor ? ` · by ${h.actor}` : ''}</span>{h.note && <div className="text-ink-2 mt-0.5">{h.note}</div>}</li>))}</ol>
    <h3 className="font-bold mb-2">Audit trail</h3>
    {u.audit.length ? <ol className="grid gap-1.5">{u.audit.map(a => (
      <li key={a.id} className="text-[13px]"><b>{String(a.detail.action || a.event).replace(/_/g, ' ')}</b> <span className="hint">{fmtDate(a.at)}{a.actor_label ? ` · ${a.actor_label}` : ''}</span></li>))}</ol>
      : <p className="hint">Nothing recorded yet.</p>}
  </>);
}

function AccessEdit({ depts, initial, close, save, note, okLabel = 'Save', requireOne }: {
  depts: Department[]; initial: string[]; close: () => void; save: (ids: string[]) => Promise<void> | void; note?: string; okLabel?: string; requireOne?: boolean;
}) {
  const [ids, setIds] = useState(initial); const a = useAction();
  return (<>
    <p className="hint mb-3">{note || 'Tick the departments whose knowledge this person may use. Their answers never use anything else.'}</p>
    <div className="mb-4"><DeptChecks depts={depts} value={ids} onChange={setIds} /></div>
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button>
      <button className="btn primary" disabled={a.busy} onClick={() => {
        if (requireOne && !ids.length) { a.setError('Tick at least one department.'); return; }
        a.run(async () => { await save(ids); close(); });
      }}>{okLabel}</button></div>
  </>);
}

function AddUser({ depts, close, done }: { depts: Department[]; close: () => void; done: () => void }) {
  const [f, setF] = useState({ n: '', u: '', m: '', p: '', r: 'employee' as Role }); const [invite, setInvite] = useState(true);
  const [publish, setPublish] = useState(false); const [ids, setIds] = useState<string[]>([]); const a = useAction();
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    a.run(() => api('/v1/admin/users', { method: 'POST', body: { full_name: f.n, username: f.u.trim().toLowerCase(), email: f.m.trim(), role: f.r,
      department_ids: ids, invite, password: invite ? null : f.p, can_publish: publish } }))
      .then(ok => { if (ok) { close(); toast(invite ? 'Invitation sent' : 'User added'); done(); } });
  };
  return (
    <form onSubmit={submit} className="grid gap-3.5">
      <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1"><div className="field"><label htmlFor="au-n">Full name</label><input id="au-n" className="input" required minLength={2} value={f.n} onChange={set('n')} /></div>
        <div className="field"><label htmlFor="au-u">Username</label><input id="au-u" className="input" required minLength={3} maxLength={30} autoCapitalize="none" value={f.u} onChange={set('u')} /></div></div>
      <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1"><div className="field"><label htmlFor="au-m">Work email</label><input id="au-m" className="input" type="email" required value={f.m} onChange={set('m')} /></div>
        <div className="field"><label htmlFor="au-r">Role</label><select id="au-r" className="select" value={f.r} onChange={set('r')}>{ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></div></div>
      {f.r === 'knowledge_admin' && <label className="check"><input type="checkbox" checked={publish} onChange={e => setPublish(e.target.checked)} /> Can publish approved knowledge (publisher permission)</label>}
      <label className="check"><input type="checkbox" checked={invite} onChange={e => setInvite(e.target.checked)} /> Email an invitation so they choose their own password</label>
      {!invite && <div className="field"><label htmlFor="au-p">Temporary password</label><input id="au-p" className="input" type="password" required minLength={8} autoComplete="new-password" value={f.p} onChange={set('p')} /></div>}
      <div className="field"><label>Can see knowledge of</label><DeptChecks depts={depts} value={ids} onChange={setIds} /></div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={a.busy}>{invite ? 'Send invitation' : 'Add user'}</button></div>
    </form>
  );
}

/* ---------------- PRD §7 Departments: create/edit/disable; members and reviewers ---------------- */
type AdminDept = Department & { description?: string | null; reviewer_ids: string[]; member_count: number };

export function DepartmentsPage() {
  const { data, error, reload } = useLoad(() => Promise.all([
    api<{ departments: AdminDept[] }>('/v1/admin/departments').then(r => r.departments), api<{ users: User[] }>('/v1/admin/users?status=active').then(r => r.users),
  ]));
  const [name, setName] = useState('');
  const [ds, users] = data || [null, []];
  const patchDept = async (id: string, body: object, msg = 'Saved') => { try { await api(`/v1/admin/departments/${id}`, { method: 'PATCH', body }); toast(msg); reload(); } catch (e) { toast((e as Error).message); } };
  const create = async (e: React.FormEvent) => {
    e.preventDefault(); try { await api('/v1/admin/departments', { method: 'POST', body: { name: name.trim() } }); setName(''); toast('Department created'); reload(); } catch (err) { toast((err as Error).message); }
  };
  const edit = (d: AdminDept) => openModal(`Edit ${d.name}`, close => <DeptEdit d={d} users={users} close={close} save={body => patchDept(d.id, body)} />, { wide: true });
  const reviewerNames = (d: AdminDept) => d.reviewer_ids.map(id => users.find(u => u.id === id)?.full_name).filter(Boolean).join(', ');
  return (
    <div className="page">
      <PageHead title="Departments" sub="Knowledge and people are organised by department. Reviewers approve proposed changes for their department." />
      <form className="card flex gap-3 !p-3.5 mb-4" onSubmit={create}>
        <input className="input" placeholder="New department name" aria-label="New department name" required minLength={2} value={name} onChange={e => setName(e.target.value)} />
        <button className="btn primary flex-none"><Icon name="plus" size={16} /> Create</button>
      </form>
      {error ? <Banner kind="err">{error}</Banner> : !ds ? <Loading /> : (
        <div className="table-wrap"><table><thead><tr><th>Department</th><th>Members</th><th>Reviewers</th><th>Status</th><th /></tr></thead>
          <tbody>{ds.map(d => (
            <tr key={d.id}><td><b>{d.name}</b>{d.description && <div className="hint">{d.description}</div>}</td><td>{d.member_count}</td>
              <td>{reviewerNames(d) || <span className="hint">None</span>}</td>
              <td><span className={`chip dot ${d.status === 'active' ? 'green' : ''}`}>{d.status === 'active' ? 'Active' : 'Disabled'}</span></td>
              <td><div className="flex justify-end gap-2"><button className="btn sm" onClick={() => edit(d)}>Edit</button>
                <button className="btn ghost sm" onClick={() => patchDept(d.id, { status: d.status === 'active' ? 'archived' : 'active' }, d.status === 'active' ? 'Disabled' : 'Enabled')}>{d.status === 'active' ? 'Disable' : 'Enable'}</button></div></td></tr>))}</tbody></table></div>
      )}
    </div>
  );
}

function DeptEdit({ d, users, close, save }: { d: AdminDept; users: User[]; close: () => void; save: (body: object) => Promise<void> }) {
  const [name, setName] = useState(d.name); const [desc, setDesc] = useState(d.description || ''); const [rev, setRev] = useState<string[]>(d.reviewer_ids);
  const eligible = users.filter(u => u.role !== 'employee'); const a = useAction();
  return (<>
    <div className="grid gap-3.5 mb-4">
      <div className="field"><label htmlFor="de-n">Name</label><input id="de-n" className="input" value={name} onChange={e => setName(e.target.value)} /></div>
      <div className="field"><label htmlFor="de-d">Description <span className="hint">(optional)</span></label><input id="de-d" className="input" maxLength={300} value={desc} onChange={e => setDesc(e.target.value)} /></div>
      <div className="field"><label>Reviewers <span className="hint">(approve changes for this department)</span></label>
        {eligible.length ? <DeptChecks depts={eligible.map(u => ({ id: u.id, name: `${u.full_name} · ${ROLE_LABEL[u.role]}` }))} value={rev} onChange={setRev} />
          : <p className="hint">Give someone the Department Reviewer role on the Users page first.</p>}</div>
    </div>
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button>
      <button className="btn primary" disabled={a.busy} onClick={() => a.run(async () => { await save({ name: name.trim(), description: desc.trim(), reviewer_ids: rev }); close(); })}>Save</button></div>
  </>);
}
