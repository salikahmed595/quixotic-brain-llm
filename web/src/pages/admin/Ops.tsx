import { useEffect, useState } from 'react';
import { api, session } from '../../api';
import { Icon } from '../../icons';
import { go, useApp } from '../../state';
import type { Department } from '../../types';
import { Banner, confirmModal, DeptChecks, Empty, fmtDate, Loading, openModal, PageHead, toast, useAction, useLoad, usePoll } from '../../ui';

const prefillAdd = (title: string) => { session.set('qb_prefill', JSON.stringify({ title })); go('add'); };
const Stat = ({ n, l, sub }: { n: React.ReactNode; l: string; sub?: string }) => <div className="card stat"><span className="n">{n}</span><span className="l">{l}</span>{sub && <span className="hint">{sub}</span>}</div>;

/* PRD §7 Dashboard */
export function DashboardPage() {
  const { rank } = useApp();
  const { data: d, error } = useLoad(() => api('/v1/dashboard'));
  const list = (arr: any[], empty: string, fn: (x: any, k: number) => React.ReactNode) => arr.length ? arr.map(fn) : <p className="hint py-2.5">{empty}</p>;
  return (
    <div className="page">
      <PageHead title="Dashboard" sub={rank >= 3 ? 'Company-wide activity.' : 'Activity in the departments you manage.'} />
      {error ? <Banner kind="err">{error}</Banner> : !d ? <Loading /> : (<>
        <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(180px,1fr))]">
          <Stat n={d.knowledge_chunks} l="Knowledge sections" /><Stat n={d.departments} l="Departments" /><Stat n={d.questions_this_week} l="Questions this week" />
          <Stat n={d.retrieval_success == null ? '—' : Math.round(d.retrieval_success * 100) + '%'} l="Answers found" /><Stat n={d.pending_approvals} l="Pending approvals" />
        </div>
        <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fit,minmax(300px,1fr))]">
          <div className="card"><b>Recent questions</b><div className="mt-2">{list(d.recent_questions, 'No questions yet.', (q, k) => (
            <div key={k} className="flex items-center gap-3 py-2.5 border-t border-line"><span className="flex-1">{q.original_query}</span>
              <span className={`chip ${q.knowledge_found ? 'green' : 'red'}`}>{q.knowledge_found ? 'Answered' : 'Not found'}</span><span className="hint">{fmtDate(q.created_at)}</span></div>))}</div></div>
          <div className="card"><b>Recently updated knowledge</b><div className="mt-2">{list(d.recently_updated_knowledge, 'Nothing active yet.', (k2, k) => (
            <div key={k} className="flex items-center gap-3 py-2.5 border-t border-line"><span className="flex-1">{k2.title} <span className="hint">v{k2.version}</span></span><span className="hint">{fmtDate(k2.updated_at)}</span></div>))}</div></div>
          <div className="card"><b>Most used sources</b><div className="mt-2">{list(d.most_used_sources, 'Sources appear once questions are answered.', (s, k) => (
            <div key={k} className="flex items-center gap-3 py-2.5 border-t border-line"><span className="flex-1">{s.title}</span><span className="chip">{s.uses} uses</span></div>))}</div></div>
        </div>
      </>)}
    </div>
  );
}

/* PRD §7 Insights: zero-result questions, knowledge health, answer quality (aggregate only, §6 FR-CHAT-09). */
export function InsightsPage() {
  const [tab, setTab] = useState(0);
  return (
    <div className="page">
      <PageHead title="Insights" sub="Find the gaps in your knowledge." />
      <div className="tabs" role="tablist">{['Failed questions', 'Knowledge health', 'Answer quality'].map((t, k) => <button key={t} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{t}</button>)}</div>
      {tab === 0 ? <Failed /> : tab === 1 ? <Health /> : <Quality />}
    </div>
  );
}
function Failed() {
  const { data, error } = useLoad(() => api('/v1/failed-questions').then(r => r.failed_questions as any[]));
  if (error) return <Banner kind="err">{error}</Banner>; if (!data) return <Loading />;
  return data.length ? (
    <div className="table-wrap"><table><thead><tr><th>Question</th><th>Language</th><th>Confidence</th><th>Asked</th><th /></tr></thead>
      <tbody>{data.map((q, k) => (<tr key={k}><td><b>{q.original_query}</b></td><td>{(q.language || '').replace('_', ' ')}</td><td><span className="chip red">{q.confidence || 'low'}</span></td><td>{fmtDate(q.created_at)}</td>
        <td><div className="flex gap-2"><button className="btn sm" onClick={() => prefillAdd(q.original_query)}>Add missing knowledge</button><button className="btn sm" onClick={() => teachModal(q.original_query)}>Teach a word</button></div></td></tr>))}</tbody></table></div>
  ) : <Empty icon="check" title="No failed questions" text="Every question so far found an answer." />;
}
function Health() {
  const { data: h, error } = useLoad(() => api('/v1/knowledge-health'));
  if (error) return <Banner kind="err">{error}</Banner>; if (!h) return <Loading />;
  const rows: [string, number | null][] = [['Active documents', h.active_documents], ['Outdated (expired)', h.outdated_documents], ['Not reviewed in 6 months', h.not_reviewed_over_6_months],
    ['No owner assigned', h.no_owner_assigned], ['Potential duplicates', h.potential_duplicates], ['Conflicting policies', h.conflicting_policies]];
  return <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(200px,1fr))]">{rows.map(r => <Stat key={r[0]} n={r[1] == null ? '—' : r[1]} l={r[0]} sub={r[1] == null ? 'Not tracked yet' : undefined} />)}</div>;
}
function Quality() {
  const { data: q, error, reload } = useLoad(() => api('/v1/answer-quality?days=30'));
  if (error) return <Banner kind="err">{error}</Banner>; if (!q) return <Loading />;
  const pct = (u: number, d: number) => (u + d) ? Math.round(100 * u / (u + d)) + '%' : '—';
  const label: Record<string, string> = { high: 'High', medium: 'Medium', low: 'Low' };
  const tbl = (title: string, rows: any[], first: string) => <div className="card"><b>{title}</b>{rows.length ? (
    <table className="w-full mt-2 text-sm"><thead><tr className="text-left text-muted"><th className="py-1.5">{first}</th><th>Rated</th><th>Helpful</th></tr></thead>
      <tbody>{rows.map((r, k) => <tr key={k} className="border-t border-line"><td className="py-2">{r.k}</td><td>{r.up + r.down}</td><td>{pct(r.up, r.down)}</td></tr>)}</tbody></table>) : <p className="hint mt-2">Nothing rated yet.</p>}</div>;
  const srcs = (title: string, rows: any[]) => <div className="card"><b>{title}</b>{rows.length ? <div className="mt-2">{rows.map((r, k) => (
    <div key={k} className="flex items-center gap-2 py-2 border-t border-line"><span className="flex-1">{r.title || '—'}{r.section && <span className="hint"> · {r.section}</span>}</span>
      <span className="chip green">{r.up} 👍</span><span className="chip red">{r.down} 👎</span></div>))}</div> : <p className="hint mt-2">Nothing yet.</p>}</div>;
  return (<>
    {!q.learning_enabled && <Banner kind="err" className="mb-3.5">Learning from ratings is switched off (QB_FEEDBACK_LEARNING=false). Ratings are still collected.</Banner>}
    <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(170px,1fr))]"><Stat n={q.up + q.down} l="Rated answers (30 days)" /><Stat n={pct(q.up, q.down)} l="Rated helpful" /><Stat n={q.up} l="👍 Helpful" /><Stat n={q.down} l="👎 Not helpful" /></div>
    <div className="card mt-4"><b>How the system learns from 👍 / 👎</b>
      <p className="hint mt-1.5">Passages that keep getting 👍 rank a little higher; passages that keep getting 👎 rank a little lower (at least 3 ratings, only a few places, nothing is ever hidden). Each person's own ratings also teach the assistant their style. It never edits your knowledge and never trains a model — you decide what to fix, using the lists below.</p>
      <button className="btn sm mt-2.5" onClick={() => confirmModal('Reset what the system has learned?', 'Ratings given until now stop influencing the order of passages. Nothing is deleted and nobody’s account changes.', 'Reset', async () => {
        await api('/v1/learning/reset', { method: 'POST' }); toast('Learning reset'); reload(); })}>Reset what it has learned</button></div>
    <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fit,minmax(300px,1fr))]">
      {tbl('Does the confidence label match reality?', q.by_confidence.map((r: any) => ({ ...r, k: (label[r.k] || r.k) + ' confidence' })), 'Label shown')}
      {tbl('By language', q.by_language.map((r: any) => ({ ...r, k: (r.k || '').replace('_', ' ') })), 'Language')}</div>
    <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fit,minmax(300px,1fr))]">{srcs('Sources people rate down — review these first', q.weakest_sources)}{srcs('Sources people rate up', q.best_sources)}</div>
    <div className="card mt-4"><b>Recent 👎 answers</b>{q.recent_not_helpful.length ? q.recent_not_helpful.map((b: any, k: number) => (
      <div key={k} className="py-3 border-t border-line mt-2"><div className="flex flex-wrap items-center gap-3"><b className="flex-1 min-w-[200px]">{b.original_query}</b><span className="chip">{label[b.confidence] || b.confidence} confidence</span><span className="hint">{fmtDate(b.created_at)}</span></div>
        <p className="hint mt-1">{b.answer}{b.answer.length >= 240 ? '…' : ''}</p>{b.note && <p className="mt-1 text-bad">Reason: {b.note}</p>}
        <button className="btn sm mt-1.5" onClick={() => prefillAdd(b.original_query)}>Add missing knowledge</button></div>)) : <p className="hint mt-2">No 👎 yet.</p>}</div>
  </>);
}

/* PRD §7 Vocabulary: aliases staff really use (Urdu / Roman Urdu → document wording). */
function teachModal(prefill: string, done?: () => void) { openModal('Teach the system a word', close => <Teach prefill={prefill} close={close} done={done} />); }
function Teach({ prefill, close, done }: { prefill: string; close: () => void; done?: () => void }) {
  const [p, setP] = useState(prefill); const [m, setM] = useState(''); const a = useAction();
  return (
    <form className="grid gap-3.5" onSubmit={e => { e.preventDefault(); a.run(() => api('/v1/vocabulary', { method: 'POST', body: { phrase: p, meaning: m } })).then(ok => { if (ok) { close(); toast('Learned. Questions with this phrase now find it.'); done?.(); } }); }}>
      <p className="hint">Write a word or phrase the way your staff type it, and what it means in English — the words your documents use. From then on, questions containing it also search for that meaning.</p>
      <div className="field"><label htmlFor="v-p">Staff write (Roman Urdu or Urdu)</label><input id="v-p" className="input" required maxLength={80} value={p} onChange={e => setP(e.target.value)} placeholder="e.g. ghar se kaam   or   چھٹی" /></div>
      <div className="field"><label htmlFor="v-m">It means (English, as in your documents)</label><input id="v-m" className="input" required maxLength={120} value={m} onChange={e => setM(e.target.value)} placeholder="e.g. work from home" /></div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={a.busy}>Teach</button></div>
    </form>
  );
}
export function VocabularyPage() {
  const { data, error, reload } = useLoad(() => api('/v1/vocabulary').then(r => r.entries as any[]));
  return (
    <div className="page">
      <PageHead title="Vocabulary" sub="Teach the system the Urdu and Roman Urdu words your staff really use."><button className="btn primary" onClick={() => teachModal('', reload)}><Icon name="plus" size={17} /> Teach a word</button></PageHead>
      <div className="card mb-4"><b>How it works</b><p className="hint mt-1.5">Your documents are mostly English, but people ask in Urdu and Roman Urdu. When someone writes <code>ghar se kaam</code>, the system also searches for <code>work from home</code>. Add the words that fail for you — the <b>Insights → Failed questions</b> list shows which ones. Changes work immediately.</p></div>
      {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : data.length ? (
        <div className="table-wrap"><table><thead><tr><th>Staff write</th><th>Means</th><th>Added</th><th /></tr></thead>
          <tbody>{data.map(r => <tr key={r.id}><td><b>{r.phrase}</b></td><td>{r.meaning}</td><td>{fmtDate(r.created_at)}</td>
            <td><button className="btn ghost sm" title="Forget" aria-label={`Forget ${r.phrase}`} onClick={async () => { try { await api(`/v1/vocabulary/${r.id}`, { method: 'DELETE' }); reload(); } catch (e) { toast((e as Error).message); } }}><Icon name="trash" size={16} /></button></td></tr>)}</tbody></table></div>
      ) : <Empty icon="spark" title="No words taught yet" text="Add a few of the Roman Urdu or Urdu phrases your staff use, with their English meaning." action={<button className="btn primary" onClick={() => teachModal('', reload)}>Teach a word</button>} />}
    </div>
  );
}

/* PRD §7 API keys: masked, revocable, scoped; the secret is shown once and never again. */
const EXPIRY = [['never', 'Never — until I revoke it'], ['1h', '1 hour'], ['24h', '24 hours'], ['1w', '1 week'], ['1m', '1 month'], ['1y', '1 year']];
const expiresText = (iso?: string | null) => {
  if (!iso) return 'Never'; const d = new Date(iso), ms = +d - Date.now(); if (ms <= 0) return 'Expired ' + fmtDate(iso);
  const m = ms / 60000; return m < 90 ? `in ${Math.round(m)} min` : m < 2880 ? `in ${Math.round(m / 60)} h` : `in ${Math.round(m / 1440)} days · ${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;
};
export function KeysPage() {
  const { data, error, reload } = useLoad(() => Promise.all([api('/v1/admin/api-keys').then(r => r.api_keys as any[]), api<{ departments: Department[] }>('/v1/departments').then(r => r.departments)]));
  const [fresh, setFresh] = useState<{ name: string; key: string; expires?: string } | null>(null);
  const [keys, ds] = data || [null, []];
  const dn = (id: string) => ds.find(d => d.id === id)?.name || '—';
  const state = (k: any): [string, string] => k.status !== 'active' ? ['Revoked', ''] : k.expires_at && new Date(k.expires_at) <= new Date() ? ['Expired', 'red'] : ['Active', 'green'];
  const create = () => openModal('Create new API key', close => <NewKey depts={ds.filter(d => d.status === 'active')} close={close} done={k => { setFresh(k); reload(); }} />);
  return (
    <div className="page">
      <PageHead title="API keys" sub="Let other Quixotic apps use your knowledge base. Keep keys secret — treat them like passwords."><button className="btn primary" onClick={create}><Icon name="plus" size={17} /> Create new key</button></PageHead>
      {fresh && (
        <div className="card !border-good mb-4"><b>Your new key{fresh.name && ` “${fresh.name}”`}</b><div className="keybox my-2.5">{fresh.key}</div>
          <p className="hint">Copy it now and store it somewhere safe. You won't be able to see it again.</p>
          <div className="flex flex-wrap gap-3 my-2.5"><button className="btn sm" onClick={() => { navigator.clipboard?.writeText(fresh.key); toast('Copied'); }}><Icon name="copy" size={15} /> Copy key</button>
            <span className={`chip ${fresh.expires ? 'amber' : 'green'}`}>{fresh.expires ? 'Expires ' + expiresText(fresh.expires) : 'Never expires'}</span></div>
        </div>
      )}
      {error ? <Banner kind="err">{error}</Banner> : !keys ? <Loading /> : keys.length ? (
        <div className="table-wrap"><table><thead><tr><th>Name</th><th>Key</th><th>Permissions</th><th>Access</th><th>Expires</th><th>Last used</th><th>Created</th><th>Status</th><th /></tr></thead>
          <tbody>{keys.map(k => { const [sl, sc] = state(k); return (
            <tr key={k.id}><td><b>{k.app_name}</b></td><td><code>{k.key_prefix}••••{k.last4 || ''}</code></td><td>{k.permissions.map((p: string) => <span key={p} className="chip m-0.5">{p.replace('_', ' ')}</span>)}</td>
              <td>{k.allowed_department_ids.length ? k.allowed_department_ids.map(dn).join(', ') : 'All departments'}</td><td>{expiresText(k.expires_at)}</td><td>{k.last_used_at ? fmtDate(k.last_used_at) : 'Never'}</td><td>{fmtDate(k.created_at)}</td>
              <td><span className={`chip dot ${sc}`}>{sl}</span></td>
              <td>{k.status === 'active' && <button className="btn ghost sm" onClick={() => confirmModal('Revoke this key?', 'Any app using it stops working immediately. This can’t be undone.', 'Revoke', async () => { await api(`/v1/admin/api-keys/${k.id}`, { method: 'DELETE' }); reload(); })}>Revoke</button>}</td></tr>); })}</tbody></table></div>
      ) : <Empty icon="key" title="No API keys yet" text="Create a key so another app can use your company knowledge." />}
    </div>
  );
}
function NewKey({ depts, close, done }: { depts: Department[]; close: () => void; done: (k: { name: string; key: string; expires?: string }) => void }) {
  const [name, setName] = useState(''); const [exp, setExp] = useState('never'); const [perms, setPerms] = useState(['ask', 'search']);
  const [all, setAll] = useState(true); const [ids, setIds] = useState<string[]>([]); const a = useAction();
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!all && !ids.length) { a.setError('Pick at least one department, or choose “All departments”.'); return; }
    a.run(async () => { const r = await api('/v1/admin/api-keys', { method: 'POST', body: { name, permissions: perms, department_ids: all ? [] : ids, expires_in: exp } }); done({ name, key: r.api_key, expires: r.expires_at }); close(); });
  };
  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="field"><label htmlFor="k-n">Name <span className="hint">(just for you — it isn't part of the key)</span></label><input id="k-n" className="input" required value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Call center app" /></div>
      <div className="field"><label htmlFor="k-x">This key works for</label><select id="k-x" className="select" value={exp} onChange={e => setExp(e.target.value)}>{EXPIRY.map(x => <option key={x[0]} value={x[0]}>{x[1]}</option>)}</select></div>
      <div className="field"><label>Permissions</label><div>{['ask', 'search', 'documents', 'sales_memory', 'feedback'].map(p => (
        <label key={p} className="check"><input type="checkbox" checked={perms.includes(p)} onChange={e => setPerms(e.target.checked ? [...perms, p] : perms.filter(x => x !== p))} /> {p.replace('_', ' ')}</label>))}</div></div>
      <div className="field"><label>Access</label><label className="check"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} /> All departments</label>
        {!all && <div className="mt-1.5"><DeptChecks depts={depts} value={ids} onChange={setIds} /></div>}</div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex justify-end gap-3"><button type="button" className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={a.busy}>Create key</button></div>
    </form>
  );
}

/* PRD §7 System: background jobs and the audit trail. */
const EVENTS = ['user_login', 'failed_authentication', 'document_upload', 'knowledge_submission', 'approval', 'rejection', 'archive_event', 'permission_change', 'api_key_creation', 'model_change', 'admin_action', 'sensitive_access_event'];
const JOBS: Record<string, [string, string]> = { queued: ['Queued', 'amber'], running: ['Running', 'blue'], succeeded: ['Done', 'green'], failed: ['Failed', 'red'] };
export function SystemPage() {
  const [healthy, setHealthy] = useState<boolean | null>(null); const [ev, setEv] = useState('');
  useEffect(() => { api('/v1/health').then(() => setHealthy(true)).catch(() => setHealthy(false)); }, []);
  const jobs = useLoad(() => api('/v1/admin/jobs').then(r => r.jobs as any[]));
  usePoll(!!jobs.data?.some(x => x.status === 'queued' || x.status === 'running'), jobs.reload);
  const audit = useLoad(() => api('/v1/audit-logs?limit=100' + (ev ? '&event=' + ev : '')).then(r => r.audit_logs as any[]), [ev]);
  return (
    <div className="page">
      <PageHead title="System" sub="Background work and the audit trail.">
        {healthy != null && <span className={`chip dot ${healthy ? 'green' : 'red'}`}>{healthy ? 'Service healthy' : 'Service unreachable'}</span>}
      </PageHead>
      <div className="card mb-4"><b>Background jobs</b><div className="mt-2.5">
        {jobs.error ? <Banner kind="err">{jobs.error}</Banner> : !jobs.data ? <Loading /> : jobs.data.length ? (
          <div className="table-wrap !border-0"><table><thead><tr><th>Job</th><th>Status</th><th className="w-60">Progress</th><th>Started</th></tr></thead>
            <tbody>{jobs.data.map(x => { const [l, c] = JOBS[x.status] || [x.status, '']; const pct = x.progress_total ? Math.round(100 * x.progress_done / x.progress_total) : (x.status === 'succeeded' ? 100 : 0);
              return (<tr key={x.id}><td><b>{x.type.replace(/[._]/g, ' ')}</b>{x.error && <div className="hint !text-bad">{x.error}</div>}</td><td><span className={`chip dot ${c}`}>{l}</span></td>
                <td>{x.progress_total ? <><div className="bar"><i style={{ width: pct + '%' }} /></div><div className="hint">{x.progress_done.toLocaleString()} / {x.progress_total.toLocaleString()}</div></> : <span className="hint">—</span>}</td><td>{fmtDate(x.created_at)}</td></tr>); })}</tbody></table></div>
        ) : <p className="hint">No background jobs yet.</p>}</div></div>
      <div className="card">
        <div className="flex flex-wrap items-center gap-3 mb-2.5"><b className="flex-1">Audit log</b>
          <select className="select !w-[220px] !h-[38px]" value={ev} onChange={e => setEv(e.target.value)} aria-label="Event"><option value="">All events</option>{EVENTS.map(e => <option key={e} value={e}>{e.replace(/_/g, ' ')}</option>)}</select></div>
        {audit.error ? <Banner kind="err">{audit.error}</Banner> : !audit.data ? <Loading /> : audit.data.length ? (
          <div className="table-wrap !border-0"><table><thead><tr><th>When</th><th>Who</th><th>Event</th><th>Detail</th></tr></thead>
            <tbody>{audit.data.map((x, k) => <tr key={k}><td>{fmtDate(x.at)}</td><td>{x.actor_label || '—'}</td><td><span className="chip">{x.event.replace(/_/g, ' ')}</span></td>
              <td className="hint max-w-[380px] truncate">{Object.entries(x.detail || {}).filter(([, v]) => v != null).map(([k2, v]) => k2.replace(/_/g, ' ') + ': ' + v).join(' · ')}</td></tr>)}</tbody></table></div>
        ) : <p className="hint">No events yet.</p>}
      </div>
    </div>
  );
}
