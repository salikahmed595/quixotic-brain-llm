import { useEffect, useState } from 'react';
import { api, session } from '../../api';
import { Icon } from '../../icons';
import { go } from '../../state';
import type { Department } from '../../types';
import { Banner, confirmModal, DeptChecks, Empty, fmtDate, Loading, openModal, PageHead, toast, useAction, useLoad, usePoll } from '../../ui';

const prefillAdd = (title: string) => { session.set('qb_prefill', JSON.stringify({ title })); go('add'); };
const Stat = ({ n, l, sub }: { n: React.ReactNode; l: string; sub?: string }) => <div className="card stat"><span className="n">{n}</span><span className="l">{l}</span>{sub && <span className="hint">{sub}</span>}</div>;

/* PRD §7 Dashboard: approved users (target 160), pending accounts, active chats, answer volume, knowledge health, index status,
   unresolved gaps, queue counts. Aggregate only (§6 FR-CHAT-09). */
export function DashboardPage() {
  const { data: d, error } = useLoad(() => api('/v1/dashboard'));
  const list = (arr: any[], empty: string, fn: (x: any, k: number) => React.ReactNode) => arr.length ? arr.map(fn) : <p className="hint py-2.5">{empty}</p>;
  return (
    <div className="page">
      <PageHead title="Dashboard" sub="How Quixotic AI is being used, and what needs attention." />
      {error ? <Banner kind="err">{error}</Banner> : !d ? <Loading /> : (<>
        <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(170px,1fr))]">
          <Stat n={<>{d.approved_users}<span className="text-muted text-lg"> / {d.target_users}</span></>} l="Approved users" sub="Target from the plan" />
          <a href="#/requests" className="no-underline"><Stat n={d.pending_accounts} l="Pending accounts" sub={d.pending_accounts ? 'Waiting for approval' : undefined} /></a>
          <Stat n={d.signed_in_now} l="Signed in now" sub="Active in the last 15 min" /><Stat n={d.active_chats} l="Active chats" sub="Last 24 hours" />
          <Stat n={d.answers_today} l="Questions today" sub={`${d.questions_this_week} this week`} />
          <Stat n={d.answered_rate == null ? '—' : Math.round(d.answered_rate * 100) + '%'} l="Answered from knowledge" sub="Last 7 days" />
        </div>
        <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fit,minmax(170px,1fr))]">
          <Stat n={d.published_documents} l="Published documents" sub={`${d.knowledge_chunks} searchable passages`} />
          <a href="#/approvals" className="no-underline"><Stat n={d.pending_approvals} l="Changes to review" sub={d.failed_publications ? `${d.failed_publications} failed publication(s)` : undefined} /></a>
          <a href="#/knowledge" className="no-underline"><Stat n={d.unresolved_gaps} l="Unanswered questions" sub="Missing knowledge" /></a>
          <Stat n={d.index_not_current} l="Index not current" sub={d.index_not_current ? 'Reindex from Documents' : 'All published text indexed'} />
          <Stat n={d.unclassified_documents} l="Need classification" sub={d.unclassified_documents ? 'Hidden from answers until classified' : undefined} />
          <Stat n={`${d.jobs.queued + d.jobs.running}`} l="Jobs in queue" sub={`${d.jobs.done_24h} done · ${d.jobs.failed_24h} failed (24 h)`} />
        </div>
        <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fit,minmax(300px,1fr))]">
          <div className="card"><b>Recently published</b><div className="mt-2">{list(d.recently_updated_knowledge, 'Nothing published yet.', (k2, k) => (
            <div key={k} className="flex items-center gap-3 py-2.5 border-t border-line"><span className="flex-1">{k2.title} <span className="hint">v{k2.version}</span></span><span className="hint">{fmtDate(k2.updated_at)}</span></div>))}</div></div>
          <div className="card"><b>Most used sources (30 days)</b><div className="mt-2">{list(d.most_used_sources, 'Sources appear once questions are answered.', (s, k) => (
            <div key={k} className="flex items-center gap-3 py-2.5 border-t border-line"><span className="flex-1">{s.title}</span><span className="chip">{s.uses} uses</span></div>))}</div></div>
        </div>
      </>)}
    </div>
  );
}

/* PRD §7 Insights: top questions, zero-result queries, feedback, department usage, document coverage, response latency.
   Aggregate and permission-aware: question texts and counts, never who asked (§6 FR-CHAT-09). */
export function InsightsPage() {
  const [tab, setTab] = useState(0);
  return (
    <div className="page">
      <PageHead title="Insights" sub="What people ask, where answers are missing, and how well the assistant performs." />
      <div className="tabs" role="tablist">{['Questions', 'Knowledge health', 'Answer quality'].map((t, k) => <button key={t} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{t}</button>)}</div>
      {tab === 0 ? <Overview /> : tab === 1 ? <Health /> : <Quality />}
    </div>
  );
}
function Overview() {
  const [days, setDays] = useState(30);
  const { data: d, error } = useLoad(() => api(`/v1/insights?days=${days}`), [days]);
  if (error) return <Banner kind="err">{error}</Banner>; if (!d) return <Loading />;
  const sec = (ms: number | null) => ms == null ? '—' : (ms / 1000).toFixed(1) + ' s';
  const lat = d.latency_ms;
  return (<>
    <div className="flex justify-end mb-3"><select className="select !w-40" value={days} onChange={e => setDays(+e.target.value)} aria-label="Period">
      {[7, 30, 90].map(n => <option key={n} value={n}>Last {n} days</option>)}</select></div>
    <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(170px,1fr))]">
      <Stat n={sec(lat.answer_p95)} l="Answer time (p95)" sub={`Target under ${lat.targets.answer_p95 / 1000} s · median ${sec(lat.answer_p50)}`} />
      <Stat n={sec(lat.search_p95)} l="Document search (p95)" sub={`Target under ${lat.targets.retrieval_p95 / 1000} s`} />
      <Stat n={lat.answers} l="Answers" /><Stat n={`${d.feedback.up} 👍 · ${d.feedback.down} 👎`} l="Feedback" />
    </div>
    <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fit,minmax(340px,1fr))]">
      <div className="card"><b>Top questions</b>{d.top_questions.length ? <table className="w-full mt-2 text-sm"><thead><tr className="text-left text-muted"><th className="py-1.5">Question</th><th>Asked</th><th>Unanswered</th></tr></thead>
        <tbody>{d.top_questions.map((q: any, k: number) => <tr key={k} className="border-t border-line"><td className="py-2 pr-2">{q.question}</td><td>{q.asked}</td><td>{q.unanswered ? <span className="chip red">{q.unanswered}</span> : '—'}</td></tr>)}</tbody></table>
        : <p className="hint mt-2">No questions yet.</p>}</div>
      <div className="card"><b>Questions without an approved answer</b>{d.zero_result.length ? <div className="mt-2">{d.zero_result.map((g: any, k: number) => (
        <div key={k} className="py-2 border-t border-line"><div>{g.question}</div><div className="hint">{g.occurrences}× asked · {g.reports} reports · {g.department || 'no department'}</div>
          <button className="btn sm mt-1.5" onClick={() => prefillAdd(g.question)}>Add missing knowledge</button> <button className="btn sm mt-1.5" onClick={() => teachModal(g.question)}>Teach a word</button></div>))}</div>
        : <p className="hint mt-2">None. Every question found approved knowledge.</p>}</div>
    </div>
    <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fit,minmax(340px,1fr))]">
      <div className="card"><b>Department usage</b>{d.department_usage.length ? <table className="w-full mt-2 text-sm"><thead><tr className="text-left text-muted"><th className="py-1.5">Scope</th><th>Questions</th><th>Answered</th></tr></thead>
        <tbody>{d.department_usage.map((u: any, k: number) => <tr key={k} className="border-t border-line"><td className="py-2">{u.department}</td><td>{u.questions}</td><td>{u.questions ? Math.round(100 * u.answered / u.questions) + '%' : '—'}</td></tr>)}</tbody></table>
        : <p className="hint mt-2">No questions yet.</p>}</div>
      <div className="card"><b>Document coverage</b><table className="w-full mt-2 text-sm"><thead><tr className="text-left text-muted"><th className="py-1.5">Department</th><th>Published documents</th></tr></thead>
        <tbody>{d.coverage.map((c: any, k: number) => <tr key={k} className="border-t border-line"><td className="py-2">{c.department}</td><td>{c.published ? c.published : <span className="chip red">none</span>}</td></tr>)}</tbody></table></div>
    </div>
  </>);
}
function Health() {
  const { data: h, error } = useLoad(() => api('/v1/knowledge-health'));
  if (error) return <Banner kind="err">{error}</Banner>; if (!h) return <Loading />;
  const rows: [string, number | null][] = [['Published documents', h.active_documents], ['Expired but still marked published', h.outdated_documents], ['Expiring in 30 days', h.expiring_in_30_days],
    ['Published over 6 months ago', h.not_reviewed_over_6_months], ['No owner assigned', h.no_owner_assigned], ['Need classification', h.unclassified],
    ['Potential duplicates', h.potential_duplicates], ['Conflicting policies', h.conflicting_policies]];
  return (<><div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(200px,1fr))]">{rows.map(r => <Stat key={r[0]} n={r[1] == null ? '—' : r[1]} l={r[0]} sub={r[1] == null ? 'Checked per change in Approvals' : undefined} />)}</div>
    <p className="hint mt-3">Expired documents are never used in answers, even before someone archives them.</p></>);
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

/* PRD §7 System: models, RAG settings, indexing jobs, integration health, backups, incident controls, audit export. */
const EVENTS = ['user_login', 'failed_authentication', 'document_upload', 'knowledge_submission', 'approval', 'rejection', 'archive_event', 'permission_change', 'api_key_creation', 'model_change', 'admin_action', 'sensitive_access_event'];
const JOBS: Record<string, [string, string]> = { queued: ['Queued', 'amber'], running: ['Running', 'blue'], succeeded: ['Done', 'green'], failed: ['Failed', 'red'] };
const KV = ({ rows }: { rows: [string, React.ReactNode][] }) => <dl className="kv mt-2.5 text-[13.5px]">{rows.map(([k, v]) => <><dt key={k + 'k'}>{k}</dt><dd key={k}>{v}</dd></>)}</dl>;
export function SystemPage() {
  const [healthy, setHealthy] = useState<boolean | null>(null); const [ev, setEv] = useState('');
  useEffect(() => { api('/v1/health').then(() => setHealthy(true)).catch(() => setHealthy(false)); }, []);
  const sys = useLoad(() => api('/v1/admin/system'));
  const jobs = useLoad(() => api('/v1/admin/jobs').then(r => r.jobs as any[]));
  usePoll(!!jobs.data?.some(x => x.status === 'queued' || x.status === 'running'), jobs.reload);
  const audit = useLoad(() => api('/v1/audit-logs?limit=100' + (ev ? '&event=' + ev : '')).then(r => r.audit_logs as any[]), [ev]);
  const s = sys.data;
  const pause = () => openModal(s?.incident?.answers_paused ? 'Resume answers?' : 'Pause all answers?', close => <IncidentForm paused={!!s?.incident?.answers_paused} close={close} done={sys.reload} />);
  const reindexAll = () => confirmModal('Rebuild the whole search index?', 'Every published document is read and indexed again in the background. Answers keep working meanwhile.', 'Rebuild', async () => {
    await api('/v1/admin/reindex', { method: 'POST' }); toast('Reindex started'); jobs.reload(); }, false);
  return (
    <div className="page">
      <PageHead title="System" sub="Models, search settings, integrations, backups and the audit trail. Keys and secrets stay on the server.">
        {healthy != null && <span className={`chip dot ${healthy ? 'green' : 'red'}`}>{healthy ? 'Service healthy' : 'Service unreachable'}</span>}
      </PageHead>
      {sys.error ? <Banner kind="err">{sys.error}</Banner> : !s ? <Loading /> : (<>
        {s.incident?.answers_paused && <Banner kind="err" className="mb-4">Answers are paused for everyone. Employees see: “{s.incident.message || 'Answers are paused by an administrator. Please try again later.'}”</Banner>}
        <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(320px,1fr))] mb-4">
          <div className="card"><b>Answer model and search</b><KV rows={[['Answer model', `${s.models.answer_provider} · ${s.models.answer_model}`], ['Embeddings', s.models.embeddings], ['Reranker', s.models.reranker],
            ['Passages', `${s.retrieval.candidates} searched → ${s.retrieval.final_passages} used`], ['Chunk size', `${s.retrieval.chunk_size} (overlap ${s.retrieval.chunk_overlap})`],
            ['Web Search', <span key="w" className="hint">Off — {s.web_search.reason}</span>]]} />
            <p className="hint mt-2.5">Change these in the server configuration (.env / secret manager); they are never edited from the browser.</p>
            <button className="btn sm mt-2" onClick={reindexAll}>Rebuild search index</button></div>
          <div className="card"><b>Security</b><KV rows={[['Admin two-step sign-in', s.security.admin_mfa_required ? 'Required' : <span className="chip red">Off (development)</span>],
            ['Secure cookies (HTTPS)', s.security.secure_cookies ? 'Yes' : <span className="chip amber">No (http)</span>], ['Session length', `${s.security.session_hours} h`],
            ['Email', s.security.mail_backend === 'smtp' ? 'SMTP' : <span className="chip amber">Console (development)</span>],
            ['Access levels', Object.entries(s.retrieval.sensitivity_levels).map(([k, v]) => `${k}: ${(v as string[]).length} roles`).join(' · ')]]} /></div>
          <div className="card"><b>Knowledge vault and backups</b><KV rows={[['Vault (Git)', s.vault.path], ['Last commit', s.vault.head ? s.vault.head.slice(0, 10) : 'none yet'],
            ['Last backup', s.backups ? `${fmtDate(s.backups.at)} · ${s.backups.status}${s.backups.s3 ? ' · in S3' : ''}` : <span className="chip amber">No backup recorded</span>],
            ['Last restore test', s.restore_drill ? <span key="d" className={`chip dot ${s.restore_drill.ok ? 'green' : 'red'}`}>{s.restore_drill.ok ? 'Passed' : 'Failed'} · {fmtDate(s.restore_drill.at)}</span> : <span className="chip amber">Never tested</span>]]} />
            <button className="btn sm mt-2.5" onClick={async () => { try { const v = await api('/v1/admin/system/audit-verify'); toast(v.ok ? `Audit log intact (${v.entries} entries)` : `Audit log problem: ${v.problems[0]?.problem}`); } catch (e) { toast((e as Error).message); } }}>Verify audit log</button></div>
          <IntegrationsCard />
          <div className="card"><b>Incident controls</b><p className="hint mt-1.5">Stop all answers at once, e.g. if wrong information was published or the AI provider misbehaves. Document search keeps working.</p>
            <button className={`btn mt-2.5 ${s.incident?.answers_paused ? 'good' : 'bad'}`} onClick={pause}>{s.incident?.answers_paused ? 'Resume answers' : 'Pause answers'}</button></div>
        </div>
      </>)}
      <div className="card mb-4"><b>Background jobs</b><div className="mt-2.5">
        {jobs.error ? <Banner kind="err">{jobs.error}</Banner> : !jobs.data ? <Loading /> : jobs.data.length ? (
          <div className="table-wrap !border-0"><table><thead><tr><th>Job</th><th>Status</th><th className="w-60">Progress</th><th>Started</th></tr></thead>
            <tbody>{jobs.data.map(x => { const [l, c] = JOBS[x.status] || [x.status, '']; const pct = x.progress_total ? Math.round(100 * x.progress_done / x.progress_total) : (x.status === 'succeeded' ? 100 : 0);
              return (<tr key={x.id}><td><b>{x.type.replace(/[._]/g, ' ')}</b>{x.error && <div className="hint !text-bad">{x.error}</div>}</td><td><span className={`chip dot ${c}`}>{l}</span></td>
                <td>{x.progress_total ? <><div className="bar"><i style={{ width: pct + '%' }} /></div><div className="hint">{x.progress_done.toLocaleString()} / {x.progress_total.toLocaleString()}</div></> : <span className="hint">—</span>}</td><td>{fmtDate(x.created_at)}</td></tr>); })}</tbody></table></div>
        ) : <p className="hint">No background jobs yet.</p>}</div></div>
      <div className="card">
        <div className="flex flex-wrap items-center gap-3 mb-2.5"><b className="flex-1">Audit log</b>
          <a className="btn sm" href={`${(window as unknown as { QB_API?: string }).QB_API || ''}/v1/admin/system/audit-export`} download>Export CSV</a>
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

function IncidentForm({ paused, close, done }: { paused: boolean; close: () => void; done: () => void }) {
  const [msg, setMsg] = useState(''); const a = useAction();
  return (<>
    {!paused && <div className="field mb-4"><label htmlFor="inc-m">Message employees see <span className="hint">(optional)</span></label>
      <input id="inc-m" className="input" maxLength={300} value={msg} onChange={e => setMsg(e.target.value)} placeholder="Answers are paused while we fix a document. Please try again later." /></div>}
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button>
      <button className={`btn ${paused ? 'good' : 'bad'}`} disabled={a.busy} onClick={() => a.run(async () => {
        await api('/v1/admin/system/incident', { method: 'POST', body: { answers_paused: !paused, message: msg.trim() || null } }); close(); toast(paused ? 'Answers resumed' : 'Answers paused'); done(); })}>{paused ? 'Resume answers' : 'Pause answers'}</button></div>
  </>);
}


/* Hermes + Telegram + Obsidian (PRD §9 step 1): only linked accounts of active people can send or approve. */
type Ident = { id: string; platform: string; external_id: string; label?: string | null; full_name: string; email: string; role: string; account_status: string };
function IntegrationsCard() {
  const { data, error, reload } = useLoad(() => Promise.all([api<{ identities: Ident[]; telegram: boolean; hermes: boolean; obsidian: boolean }>('/v1/admin/integrations/identities'),
    api<{ users: { id: string; full_name: string; role: string }[] }>('/v1/admin/users?status=active').then(r => r.users)]));
  const [f, setF] = useState({ platform: 'telegram', external_id: '', user_id: '', label: '' }); const a = useAction();
  if (error) return <div className="card"><b>Integrations</b><Banner kind="err" className="mt-2">{error}</Banner></div>;
  if (!data) return <div className="card"><b>Integrations</b><Loading /></div>;
  const [st, users] = data;
  const chip = (on: boolean, label: string) => <span className={`chip dot ${on ? 'green' : ''}`}>{label}: {on ? 'configured' : 'off'}</span>;
  return (
    <div className="card md:col-span-2"><b>Integrations — Telegram, Hermes, Obsidian</b>
      <div className="flex flex-wrap gap-2 mt-2">{chip(st.telegram, 'Approvals bot')}{chip(st.hermes, 'Hermes')}{chip(st.obsidian, 'Obsidian sync')}</div>
      <p className="hint mt-2">Link a person's Telegram ID (they send <code>/start</code> to the Quixotic Approvals bot to see it) or their Obsidian branch name. Only linked, active people can propose or approve from there; every change is still reviewed.</p>
      {st.identities.length > 0 && <div className="table-wrap !border-0 mt-2"><table><thead><tr><th>Where</th><th>Account</th><th>Person</th><th /></tr></thead>
        <tbody>{st.identities.map(i => <tr key={i.id}><td>{i.platform === 'telegram' ? 'Telegram' : 'Obsidian branch'}</td><td><code>{i.platform === 'obsidian' ? 'proposals/' : ''}{i.external_id}</code>{i.label && <div className="hint">{i.label}</div>}</td>
          <td>{i.full_name}<div className="hint">{i.role.replace('_', ' ')}{i.account_status !== 'active' ? ' · not active' : ''}</div></td>
          <td><button className="btn ghost sm" aria-label="Remove link" onClick={() => confirmModal('Remove this link?', 'They can no longer propose or approve from there.', 'Remove', async () => { await api(`/v1/admin/integrations/identities/${i.id}`, { method: 'DELETE' }); reload(); })}><Icon name="trash" size={16} /></button></td></tr>)}</tbody></table></div>}
      <form className="grid grid-cols-[150px_1fr_1fr_1fr_auto] gap-2 mt-3 max-md:grid-cols-1" onSubmit={e => { e.preventDefault(); a.run(async () => {
        await api('/v1/admin/integrations/identities', { method: 'POST', body: { ...f, external_id: f.external_id.trim(), label: f.label.trim() || null } }); setF({ ...f, external_id: '', label: '' }); toast('Linked'); reload(); }); }}>
        <select className="select" value={f.platform} onChange={e => setF({ ...f, platform: e.target.value })} aria-label="Where"><option value="telegram">Telegram</option><option value="obsidian">Obsidian branch</option></select>
        <input className="input" required value={f.external_id} onChange={e => setF({ ...f, external_id: e.target.value })} placeholder={f.platform === 'telegram' ? 'Telegram ID, e.g. 123456789' : 'Branch name, e.g. ceo'} aria-label="Account" />
        <select className="select" required value={f.user_id} onChange={e => setF({ ...f, user_id: e.target.value })} aria-label="Person"><option value="" disabled>Person…</option>{users.map(u => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select>
        <input className="input" value={f.label} onChange={e => setF({ ...f, label: e.target.value })} placeholder="Label (optional)" aria-label="Label" />
        <button className="btn primary" disabled={a.busy}>Link</button>
      </form>
      {a.error && <Banner kind="err" className="mt-2">{a.error}</Banner>}
      {st.obsidian && <ObsidianActivity />}
    </div>
  );
}

/* Owner request 2026-10-20: per-contributor activity — pushes, the proposals they became, view refreshes and Git conflicts. */
type ObsEvent = { contributor: string; kind: string; at: string; note?: string | null; proposal_title?: string | null; proposal_status?: string | null };
const OBS_KIND: Record<string, string> = { push: 'Pushed notes', proposal: 'Proposal', view_refresh: 'View updated', conflict: 'Conflict: pull and resolve' };
function ObsidianActivity() {
  const { data, error } = useLoad(() => api<{ events: ObsEvent[] }>('/v1/admin/integrations/obsidian/activity'));
  if (error) return <Banner kind="err" className="mt-3">{error}</Banner>;
  if (!data) return <Loading />;
  return (
    <details className="more mt-3"><summary>Obsidian activity ({data.events.length})</summary>
      {data.events.length ? <div className="table-wrap !border-0 mt-2"><table><thead><tr><th>When</th><th>Contributor</th><th>What</th><th>Note / proposal</th></tr></thead>
        <tbody>{data.events.slice(0, 100).map((e, k) => <tr key={k}><td>{new Date(e.at).toLocaleString()}</td><td><code>{e.contributor}</code></td>
          <td>{OBS_KIND[e.kind] || e.kind}</td><td>{e.proposal_title || e.note || '—'}{e.proposal_status && <div className="hint">{e.proposal_status.replace('_', ' ')}</div>}</td></tr>)}</tbody></table></div>
        : <p className="hint mt-2">No pushes yet.</p>}
    </details>
  );
}
