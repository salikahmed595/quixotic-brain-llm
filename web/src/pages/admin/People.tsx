import { useState } from 'react';
import { api } from '../../api';
import { Icon } from '../../icons';
import { useApp } from '../../state';
import type { Department, Role } from '../../types';
import { Avatar, Banner, confirmModal, DeptChecks, Empty, fmtDate, Loading, openModal, PageHead, ROLE_LABEL, toast, useAction, useLoad } from '../../ui';

const ROLES = Object.keys(ROLE_LABEL) as Role[];

/* PRD §5 FR-AUTH-04 / §7 Access requests: approve with role + scope, or reject. */
type Req = { id: string; full_name: string; email: string; username: string; requested_department?: string; requested_department_id?: string; created_at: string };

export function RequestsPage() {
  const { rank, me, setCounts } = useApp(); const isAdmin = rank >= 3;
  const { data, error, reload } = useLoad(() => Promise.all([
    api<{ requests: Req[] }>('/v1/access-requests').then(r => { setCounts({ requests: r.requests.length }); return r.requests; }),
    api<{ departments: Department[] }>('/v1/departments').then(r => r.departments.filter(d => d.status === 'active')),
  ]));
  const [rq, ds] = data || [null, []];
  const grantable = isAdmin ? ds : ds.filter(d => me.department_ids.includes(d.id));
  const approve = (r: Req) => openModal(`Approve ${r.full_name}`, close => <Approve r={r} roles={isAdmin ? ROLES : ['employee', 'contributor']} grantable={grantable} isAdmin={isAdmin} close={close} done={reload} />);
  const reject = (r: Req) => confirmModal('Reject this request?', <><b>{r.full_name}</b> will not be able to sign in.</>, 'Reject', async () => {
    await api(`/v1/access-requests/${r.id}/reject`, { method: 'POST' }); toast('Rejected'); reload();
  });
  return (
    <div className="page">
      <PageHead title="Access requests" sub="People who created their own account. Decide their role and which departments' information they can use." />
      {error ? <Banner kind="err">{error}</Banner> : !rq ? <Loading /> : rq.length ? (
        <div className="table-wrap"><table><thead><tr><th>Person</th><th>Username</th><th>Asked for</th><th>Requested</th><th /></tr></thead>
          <tbody>{rq.map(r => (
            <tr key={r.id}><td><b>{r.full_name}</b><div className="hint">{r.email}</div></td><td>{r.username}</td>
              <td>{r.requested_department ? <span className="chip">{r.requested_department}</span> : <span className="hint">No department chosen</span>}</td><td>{fmtDate(r.created_at)}</td>
              <td><div className="flex justify-end gap-2"><button className="btn good sm" onClick={() => approve(r)}><Icon name="check" size={15} /> Approve</button>
                <button className="btn bad sm" onClick={() => reject(r)}><Icon name="x" size={15} /> Reject</button></div></td></tr>))}</tbody></table></div>
      ) : <Empty icon="check" title="No requests waiting" text="When someone creates an account, it appears here for approval." />}
    </div>
  );
}
function Approve({ r, roles, grantable, isAdmin, close, done }: { r: Req; roles: Role[]; grantable: Department[]; isAdmin: boolean; close: () => void; done: () => void }) {
  const [role, setRole] = useState<Role>('employee');
  const [ids, setIds] = useState<string[]>(r.requested_department_id && grantable.some(d => d.id === r.requested_department_id) ? [r.requested_department_id] : []);
  const a = useAction();
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ids.length) { a.setError('Tick at least one department.'); return; }
    a.run(() => api(`/v1/access-requests/${r.id}/approve`, { method: 'POST', body: { role, department_ids: ids } })).then(ok => { if (ok) { close(); toast(`${r.full_name} can now sign in`); done(); } });
  };
  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="field"><label htmlFor="ap-r">Role</label><select id="ap-r" className="select" value={role} onChange={e => setRole(e.target.value as Role)}>{roles.map(x => <option key={x} value={x}>{ROLE_LABEL[x]}</option>)}</select></div>
      <div className="field"><label>Can see knowledge of <span className="hint">(at least one)</span></label><DeptChecks depts={grantable} value={ids} onChange={setIds} />
        {!isAdmin && <span className="hint">You can only give access to departments you belong to.</span>}</div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn good" disabled={a.busy}>Approve</button></div>
    </form>
  );
}

/* PRD §7 Users: search, add, edit role and departments, disable. */
type User = { id: string; full_name: string; email: string; employee_id: string; role: Role; department_ids: string[]; departments: string[]; is_active: boolean; avatar?: string | null };

export function UsersPage() {
  const { data, error, reload, setData } = useLoad(() => Promise.all([
    api<{ users: User[] }>('/v1/users').then(r => r.users),
    api<{ departments: Department[] }>('/v1/departments').then(r => r.departments.filter(d => d.status === 'active')),
  ]));
  const [q, setQ] = useState(''); const [role, setRole] = useState(''); const [dept, setDept] = useState('');
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [users, depts] = data || [null, []];
  const shown = (users || []).filter(u => (!role || u.role === role)
    && (!dept || (dept === '_none' ? !u.department_ids.length : u.department_ids.includes(dept)))
    && (!q || [u.full_name, u.email, u.employee_id].some(x => String(x).toLowerCase().includes(q.toLowerCase()))));
  const toggle = (id: string, on: boolean) => { const s = new Set(sel); if (on) s.add(id); else s.delete(id); setSel(s); };
  const patch = async (u: User, body: object, msg?: string) => {
    try { await api(`/v1/users/${u.id}`, { method: 'PATCH', body }); if (msg) toast(msg); reload(); } catch (e) { toast((e as Error).message); reload(); }
  };
  const access = (u: User) => openModal(`What can ${u.full_name} see?`, close => <AccessEdit depts={depts} initial={u.department_ids} close={close}
    save={ids => patch(u, { department_ids: ids }, 'Saved')} />);
  const bulk = (add: boolean) => openModal(add ? `Give ${sel.size} people access` : `Remove access from ${sel.size} people`, close => <AccessEdit depts={depts} initial={[]} close={close}
    note={add ? 'They will be able to see the knowledge of the departments you tick (their answers use it right away).' : 'They will no longer see the knowledge of the departments you tick.'}
    okLabel={add ? 'Give access' : 'Remove access'} requireOne
    save={async ids => { await api('/v1/users/bulk-departments', { method: 'POST', body: { user_ids: [...sel], [add ? 'add' : 'remove']: ids } }); toast('Access updated'); setSel(new Set()); reload(); }} />);
  const add = () => openModal('Add user', close => <AddUser depts={depts} close={close} done={reload} />);

  return (
    <div className="page">
      <PageHead title="Users" sub="Who can sign in, and which knowledge each person can see — access follows departments.">
        <button className="btn primary" onClick={add}><Icon name="plus" size={17} /> Add user</button>
      </PageHead>
      <div className="flex flex-wrap gap-3 mb-3">
        <div className="relative flex-1 min-w-[220px]"><input className="input !pl-10" placeholder="Search by name, email or employee ID…" aria-label="Search users" value={q} onChange={e => setQ(e.target.value)} />
          <span className="absolute left-3.5 top-3 text-muted"><Icon name="search" /></span></div>
        <select className="select !w-40" value={role} onChange={e => setRole(e.target.value)} aria-label="Role"><option value="">All roles</option>{ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select>
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
          <th>Name</th><th>ID</th><th>Role</th><th>Can see knowledge of</th><th>Status</th><th /></tr></thead>
          <tbody>{shown.map(u => (
            <tr key={u.id}>
              <td><input type="checkbox" aria-label={`Select ${u.full_name}`} checked={sel.has(u.id)} onChange={e => toggle(u.id, e.target.checked)} /></td>
              <td><div className="flex items-center gap-3"><Avatar user={u} size={32} /><div><b>{u.full_name}</b><div className="hint">{u.email}</div></div></div></td>
              <td>{u.employee_id}</td>
              <td><select className="select !h-9 !w-[132px]" aria-label={`Role of ${u.full_name}`} value={u.role}
                onChange={e => { const r = e.target.value as Role; setData([users.map(x => x.id === u.id ? { ...x, role: r } : x), depts]); patch(u, { role: r }, 'Role updated'); }}>
                {ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></td>
              <td>{u.role === 'administrator' ? <span className="chip orange">Everything (administrator)</span>
                : u.departments.length ? u.departments.map(d => <span key={d} className="chip m-0.5">{d}</span>) : <span className="hint">Nothing yet</span>}</td>
              <td><span className={`chip dot ${u.is_active ? 'green' : ''}`}>{u.is_active ? 'Active' : 'Disabled'}</span></td>
              <td><div className="flex gap-2"><button className="btn sm" onClick={() => access(u)}>Access</button>
                <button className="btn ghost sm" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? 'Disable' : 'Enable'}</button></div></td>
            </tr>))}</tbody></table></div>
      </>) : <Empty icon="users" title={users.length ? 'No one matches' : 'No users'} text={users.length ? 'Try a different search or filter.' : 'Add the first user.'} />}
    </div>
  );
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
  const [f, setF] = useState({ n: '', e: '', m: '', p: '', r: 'employee' }); const [ids, setIds] = useState<string[]>([]); const a = useAction();
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    a.run(() => api('/v1/users', { method: 'POST', body: { full_name: f.n, employee_id: f.e, email: f.m, password: f.p, role: f.r, department_ids: ids } }))
      .then(ok => { if (ok) { close(); toast('User added'); done(); } });
  };
  return (
    <form onSubmit={submit} className="grid gap-3.5">
      <div className="grid grid-cols-2 gap-3"><div className="field"><label htmlFor="au-n">Full name</label><input id="au-n" className="input" required value={f.n} onChange={set('n')} /></div>
        <div className="field"><label htmlFor="au-e">Employee ID</label><input id="au-e" className="input" required value={f.e} onChange={set('e')} /></div></div>
      <div className="field"><label htmlFor="au-m">Email</label><input id="au-m" className="input" type="email" required value={f.m} onChange={set('m')} /></div>
      <div className="grid grid-cols-2 gap-3"><div className="field"><label htmlFor="au-p">Temporary password</label><input id="au-p" className="input" type="password" required minLength={8} autoComplete="new-password" value={f.p} onChange={set('p')} /></div>
        <div className="field"><label htmlFor="au-r">Role</label><select id="au-r" className="select" value={f.r} onChange={set('r')}>{ROLES.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></div></div>
      <div className="field"><label>Can see knowledge of</label><DeptChecks depts={depts} value={ids} onChange={setIds} /></div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={a.busy}>Add user</button></div>
    </form>
  );
}

/* PRD §7 Departments: create, rename, set manager, archive/restore. */
export function DepartmentsPage() {
  const { data, error, reload } = useLoad(() => Promise.all([
    api<{ departments: Department[] }>('/v1/departments').then(r => r.departments), api<{ users: User[] }>('/v1/users').then(r => r.users),
  ]));
  const [name, setName] = useState('');
  const [ds, users] = data || [null, []];
  const patchDept = async (id: string, body: object) => { try { await api(`/v1/departments/${id}`, { method: 'PATCH', body }); reload(); } catch (e) { toast((e as Error).message); } };
  const create = async (e: React.FormEvent) => {
    e.preventDefault(); try { await api('/v1/departments', { method: 'POST', body: { name: name.trim() } }); setName(''); reload(); } catch (err) { toast((err as Error).message); }
  };
  const rename = (d: Department) => openModal('Rename department', close => <Prompt initial={d.name} close={close} save={v => patchDept(d.id, { name: v })} />);
  const manager = (d: Department) => openModal('Set department manager', close => (
    <Prompt initial={d.manager_id || ''} close={close} save={v => patchDept(d.id, v ? { manager_id: v } : { clear_manager: true })}
      options={[['', 'No manager'], ...users.filter(u => u.is_active).map(u => [u.id, `${u.full_name} (${ROLE_LABEL[u.role]})`] as [string, string])]} />));
  return (
    <div className="page">
      <PageHead title="Departments" sub="Knowledge and people are organised by department." />
      <form className="card flex gap-3 !p-3.5 mb-4" onSubmit={create}>
        <input className="input" placeholder="New department name" aria-label="New department name" required value={name} onChange={e => setName(e.target.value)} />
        <button className="btn primary flex-none"><Icon name="plus" size={16} /> Create</button>
      </form>
      {error ? <Banner kind="err">{error}</Banner> : !ds ? <Loading /> : (
        <div className="table-wrap"><table><thead><tr><th>Department</th><th>Manager</th><th>Status</th><th /></tr></thead>
          <tbody>{ds.map(d => (
            <tr key={d.id}><td><b>{d.name}</b></td><td>{users.find(u => u.id === d.manager_id)?.full_name || '—'}</td>
              <td><span className={`chip dot ${d.status === 'active' ? 'green' : ''}`}>{d.status === 'active' ? 'Active' : 'Archived'}</span></td>
              <td><div className="flex justify-end gap-2"><button className="btn sm" onClick={() => rename(d)}>Rename</button><button className="btn sm" onClick={() => manager(d)}>Set manager</button>
                <button className="btn ghost sm" onClick={() => patchDept(d.id, { status: d.status === 'active' ? 'archived' : 'active' })}>{d.status === 'active' ? 'Archive' : 'Restore'}</button></div></td></tr>))}</tbody></table></div>
      )}
    </div>
  );
}

function Prompt({ initial, close, save, options }: { initial: string; close: () => void; save: (v: string) => void; options?: [string, string][] }) {
  const [v, setV] = useState(initial);
  const ok = () => { if (options || v.trim()) { close(); save(v.trim()); } };
  return (<>
    {options ? <select className="select mb-4" value={v} onChange={e => setV(e.target.value)} aria-label="Choose">{options.map(o => <option key={o[0]} value={o[0]}>{o[1]}</option>)}</select>
      : <input className="input mb-4" value={v} autoFocus onChange={e => setV(e.target.value)} onKeyDown={e => e.key === 'Enter' && ok()} />}
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button><button className="btn primary" onClick={ok}>Save</button></div>
  </>);
}
