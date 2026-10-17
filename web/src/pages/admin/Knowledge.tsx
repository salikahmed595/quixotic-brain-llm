import { useState } from 'react';
import { api, session } from '../../api';
import { Icon } from '../../icons';
import { useApp } from '../../state';
import { Banner, DeptChecks, Empty, fmtDate, Loading, openDrawer, openModal, PageHead, STATUS, StatusChip, toast, useAction, useLoad } from '../../ui';

/* PRD §7 Knowledge / Add information / Approvals (P1 in §14; ported unchanged so nothing that works is lost). */
type Version = { id: string; item_id: string; title: string; status: string; version: number; departments: string[]; category?: string; document_type?: string;
  access_level?: string; information?: string; created_by?: string; created_at?: string; updated_at?: string; reviewed_at?: string; history?: { to_status: string; note?: string; at: string }[] };

async function transition(id: string, to: string) {
  const step = (s: string) => api(`/v1/knowledge/${id}/transitions`, { method: 'POST', body: { to: s } });
  if (to === 'submit') return step('submitted');
  if (to === 'approve') { await step('approved'); return step('active'); }
  return step(to);
}

function actionsFor(v: Version, rank: number, myId: string) {
  const a: [string, string, string][] = [], mine = v.created_by === myId;
  if (v.status === 'draft' && (mine || rank >= 3)) a.push(['Submit for review', 'submit', 'primary']);
  if (v.status === 'pending_review' && rank >= 2) { a.push(['Approve', 'approve', 'good']); a.push(['Reject', 'rejected', 'bad']); }
  if (v.status === 'approved' && rank >= 2) a.push(['Activate', 'active', 'good']);
  if (rank >= 1 && v.status !== 'draft') a.push(['New version', 'newversion', '']);
  if (v.status !== 'archived' && rank >= 3) a.push(['Archive', 'archived', '']);
  return a;
}

export async function openKnowledge(id: string, rank: number, myId: string, refresh: () => void) {
  const v = await api<Version>(`/v1/knowledge/${id}`);
  openDrawer(close => <KnowledgeDetail v={v} actions={actionsFor(v, rank, myId)} close={close} refresh={refresh} />);
}
function KnowledgeDetail({ v, actions, close, refresh }: { v: Version; actions: [string, string, string][]; close: () => void; refresh: () => void }) {
  const a = useAction();
  return (<div>
    <div className="flex items-start">
      <div><h2 className="text-[21px] font-extrabold tracking-[-.01em]">{v.title}</h2>
        <div className="flex flex-wrap gap-1.5 mt-2"><StatusChip s={v.status} />{v.departments.map(d => <span key={d} className="chip">{d}</span>)}</div></div>
      <span className="flex-1" /><button className="btn ghost sm" onClick={close} aria-label="Close"><Icon name="x" size={18} /></button>
    </div>
    <h4 className="mt-5.5 mb-2 text-sm font-bold">Information</h4>
    <div className="whitespace-pre-wrap bg-canvas border border-line rounded-[14px] p-3.5 max-h-[260px] overflow-auto text-ink-2">{v.information || <span className="hint">This item is an uploaded document.</span>}</div>
    <h4 className="mt-5.5 mb-2 text-sm font-bold">Details</h4>
    <dl className="kv"><dt>Version</dt><dd>{v.version}</dd><dt>Category</dt><dd>{v.category || '—'}</dd><dt>Type</dt><dd>{v.document_type || '—'}</dd>
      <dt>Access</dt><dd>{v.access_level || '—'}</dd><dt>Created</dt><dd>{fmtDate(v.created_at)}</dd><dt>Last updated</dt><dd>{fmtDate(v.updated_at)}</dd><dt>Reviewed</dt><dd>{fmtDate(v.reviewed_at)}</dd></dl>
    <h4 className="mt-5.5 mb-2 text-sm font-bold">History</h4>
    <div className="timeline">{(v.history || []).map((h, k) => <div key={k} className="tl"><i /><div><b>{(STATUS[h.to_status] || [h.to_status])[0]}</b>{h.note && <> — {h.note}</>}<small>{fmtDate(h.at)}</small></div></div>)}</div>
    {actions.length > 0 && <div className="flex flex-wrap gap-3 mt-6.5">{actions.map(([label, act, cls]) => (
      <button key={act} className={`btn ${cls}`} disabled={a.busy} onClick={() => {
        if (act === 'newversion') { close(); newVersionModal(v, refresh); return; }
        a.run(() => transition(v.id, act)).then(ok => { if (ok) { toast('Done'); close(); refresh(); } });
      }}>{label}</button>))}</div>}
    {a.error && <Banner kind="err" className="mt-3">{a.error}</Banner>}
  </div>);
}

function newVersionModal(v: Version, refresh: () => void) {
  openModal(`New version of “${v.title}”`, close => <NewVersion v={v} close={close} refresh={refresh} />);
}
function NewVersion({ v, close, refresh }: { v: Version; close: () => void; refresh: () => void }) {
  const [text, setText] = useState(v.information || ''); const a = useAction();
  return (<>
    <div className="field"><label>Updated information</label><textarea className="textarea min-h-[200px]" value={text} onChange={e => setText(e.target.value)} /></div>
    <p className="hint mt-2 mb-4">It starts as a draft. When it becomes active, the current version is archived automatically.</p>
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button>
      <button className="btn primary" disabled={a.busy} onClick={() => a.run(() => api(`/v1/knowledge/items/${v.item_id}/versions`, { method: 'POST', body: { information: text, access_level: v.access_level } }))
        .then(ok => { if (ok) { toast('Draft created'); close(); refresh(); } })}>Create draft</button></div>
  </>);
}

export function KnowledgePage() {
  const { rank, me } = useApp();
  const [status, setStatus] = useState(''); const [q, setQ] = useState('');
  const { data, error, reload } = useLoad(() => api<{ items: Version[] }>('/v1/knowledge?limit=200' + (status ? '&status=' + status : '')).then(r => r.items), [status]);
  const rows = (data || []).filter(i => !q || i.title.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="page">
      <PageHead title="Knowledge" sub="Approved and in-progress company knowledge.">
        {rank >= 1 && <a className="btn primary" href="#/add"><Icon name="plus" size={17} /> Add information</a>}
      </PageHead>
      <div className="flex flex-wrap gap-3 mb-3.5">
        <div className="relative flex-1 min-w-[220px]"><input className="input !pl-10" placeholder="Search by title…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search by title" />
          <span className="absolute left-3.5 top-3 text-muted"><Icon name="search" /></span></div>
        <select className="select !w-[190px]" value={status} onChange={e => setStatus(e.target.value)} aria-label="Status">
          <option value="">All statuses</option>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v[0]}</option>)}</select>
      </div>
      {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : rows.length ? (
        <div className="table-wrap"><table><thead><tr><th>Title</th><th>Departments</th><th>Category</th><th>Status</th><th>Version</th><th>Updated</th></tr></thead>
          <tbody>{rows.map(i => (
            <tr key={i.id} className="click" tabIndex={0} onClick={() => openKnowledge(i.id, rank, me.user_id, reload).catch(e => toast(e.message))}
              onKeyDown={e => e.key === 'Enter' && openKnowledge(i.id, rank, me.user_id, reload).catch(err => toast(err.message))}>
              <td><b>{i.title}</b></td><td>{i.departments.join(', ') || '—'}</td><td>{i.category || '—'}</td><td><StatusChip s={i.status} /></td><td>v{i.version}</td><td>{fmtDate(i.updated_at)}</td>
            </tr>))}</tbody></table></div>
      ) : <Empty icon="book" title={data.length ? 'No matches' : 'No knowledge yet'} text={data.length ? 'Try a different search or status.' : 'Add the first piece of knowledge to get started.'}
        action={rank >= 1 && !data.length ? <a className="btn primary" href="#/add">Add information</a> : undefined} />}
    </div>
  );
}

export function AddPage() {
  const { rank, departments } = useApp(); const isAdmin = rank >= 3;
  const [prefill] = useState(() => { try { const p = JSON.parse(session.get('qb_prefill') || 'null'); session.set('qb_prefill', null); return p; } catch { return null; } });
  const [tab, setTab] = useState(0);
  const blank = { title: prefill?.title || '', category: '', document_type: '', access: '', info: '', status: 'draft' };
  const [f, setF] = useState(blank); const [dept, setDept] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null); const [ok, setOk] = useState<React.ReactNode>(null); const a = useAction();
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = (mode: string) => async (e?: React.FormEvent) => {
    e?.preventDefault(); setOk(null);
    if (!dept.length) { a.setError('Pick at least one department.'); return; }
    if (!f.title.trim()) { a.setError('Enter a title.'); return; }
    await a.run(async () => {
      if (tab === 1) {
        if (!file) throw new Error('Choose a file to upload.');
        const fd = new FormData(); fd.append('file', file); fd.append('department_ids', dept.join(',')); fd.append('title', f.title);
        if (f.category) fd.append('category', f.category); if (f.document_type) fd.append('document_type', f.document_type); if (f.access) fd.append('access_level', f.access);
        fd.append('status', isAdmin ? f.status : 'draft');
        await api('/v1/documents', { method: 'POST', form: fd });
        setOk(<>Uploaded. It is being processed in the background — see <a className="underline" href="#/documents">Documents</a>.</>); setF(blank); setFile(null);
      } else {
        if (!f.info.trim()) throw new Error('Write the information first.');
        const r = await api('/v1/knowledge', { method: 'POST', body: { title: f.title, department_ids: dept, category: f.category || null, document_type: f.document_type || null, access_level: f.access || null, information: f.info } });
        const step = (s: string) => api(`/v1/knowledge/${r.version_id}/transitions`, { method: 'POST', body: { to: s } });
        if (mode !== 'draft') await step('submitted');
        if (mode === 'publish') { await step('approved'); await step('active'); }
        setOk(<>{mode === 'draft' ? 'Saved as a draft.' : mode === 'publish' ? 'Published.' : 'Submitted for review.'} <a className="underline" href="#/knowledge">View in Knowledge</a></>); setF(blank);
      }
    });
  };
  return (
    <div className="page max-w-[820px]">
      <PageHead title="Add information" sub={isAdmin ? 'Add knowledge directly, or send it through review.' : 'Your submission is reviewed before it becomes official.'} />
      <div className="tabs" role="tablist">{['Write', 'Upload document'].map((t, k) => <button key={t} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => { setTab(k); a.setError(null); setOk(null); }}>{t}</button>)}</div>
      <form className="card grid gap-4.5" onSubmit={submit(tab === 1 ? 'upload' : 'submit')}>
        <div className="field"><label htmlFor="ad-t">Title</label><input id="ad-t" className="input" required value={f.title} onChange={set('title')} placeholder="e.g. Refund policy" /></div>
        <div className="field"><label>Department</label><DeptChecks depts={departments} value={dept} onChange={setDept} /></div>
        <div className="grid grid-cols-2 gap-3.5 max-sm:grid-cols-1">
          <div className="field"><label htmlFor="ad-c">Category</label><input id="ad-c" className="input" value={f.category} onChange={set('category')} placeholder="e.g. Pricing" /></div>
          <div className="field"><label htmlFor="ad-y">Type <span className="hint">(optional)</span></label><input id="ad-y" className="input" value={f.document_type} onChange={set('document_type')} placeholder="e.g. policy, sop, script" /></div>
        </div>
        <div className="field"><label htmlFor="ad-a">Access</label><input id="ad-a" className="input" value={f.access} onChange={set('access')} placeholder="e.g. Sales + Managers" />
          <span className="hint">Who this is meant for. Visibility follows the departments you pick.</span></div>
        {tab === 0 ? (
          <div className="field"><label htmlFor="ad-i">Information</label><textarea id="ad-i" className="textarea min-h-[220px]" value={f.info} onChange={set('info')} placeholder="Write the knowledge here…" /></div>
        ) : (
          <div className="field"><label>File</label>
            <label className="block text-center rounded-2xl border-2 border-dashed border-orange bg-orange-50 p-5 cursor-pointer"
              onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); setFile(e.dataTransfer.files[0] || null); }}>
              <div className="text-orange flex justify-center"><Icon name="cloud" size={34} /></div>
              <b>{file ? file.name : 'Choose a file or drop it here'}</b><div className="hint">PDF, DOCX, TXT, Markdown, JSON or CSV</div>
              <input type="file" hidden accept=".pdf,.docx,.txt,.md,.markdown,.json,.csv" onChange={e => setFile(e.target.files?.[0] || null)} />
            </label></div>
        )}
        {isAdmin && tab === 1 && <div className="field"><label htmlFor="ad-s">Status</label><select id="ad-s" className="select" value={f.status} onChange={set('status')}><option value="draft">Send for review</option><option value="active">Publish now</option></select></div>}
        {a.error && <Banner kind="err">{a.error}</Banner>}
        {ok && <Banner kind="ok">{ok}</Banner>}
        <div className="flex flex-wrap justify-end gap-3">
          {tab === 0 ? (<>
            <button type="button" className="btn" disabled={a.busy} onClick={() => submit('draft')()}>Save as draft</button>
            <button className="btn primary" disabled={a.busy}>{isAdmin ? 'Send for review' : 'Submit for review'}</button>
            {isAdmin && <button type="button" className="btn good" disabled={a.busy} onClick={() => submit('publish')()}>Publish now</button>}
          </>) : <button className="btn primary" disabled={a.busy}><Icon name="cloud" size={17} /> Upload</button>}
        </div>
      </form>
    </div>
  );
}

export function ApprovalsPage() {
  const { rank, me, setCounts } = useApp();
  const { data, error, reload } = useLoad(() => api<{ items: Version[] }>('/v1/knowledge?status=pending_review&limit=200').then(r => { setCounts({ pending: r.items.length }); return r.items; }));
  const act = async (id: string, to: string, msg: string) => { try { await transition(id, to); toast(msg); reload(); } catch (e) { toast((e as Error).message); } };
  return (
    <div className="page">
      <PageHead title="Approvals" sub="Review knowledge before it becomes official." />
      {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : data.length ? (
        <div className="grid gap-4">{data.map(i => (
          <div key={i.id} className="card"><div className="flex flex-wrap items-start gap-3">
            <div className="flex-1 min-w-[220px]"><b className="text-base">{i.title}</b>
              <div className="flex flex-wrap gap-1.5 my-1.5">{i.departments.map(d => <span key={d} className="chip">{d}</span>)}<span className="hint">v{i.version} · submitted {fmtDate(i.updated_at)}</span></div>
              <p className="text-ink-2 line-clamp-3">{i.information || 'Uploaded document'}</p></div>
            <div className="flex gap-2">
              <button className="btn sm" onClick={() => openKnowledge(i.id, rank, me.user_id, reload).catch(e => toast(e.message))}>View</button>
              <button className="btn good sm" onClick={() => act(i.id, 'approve', 'Approved and active')}><Icon name="check" size={15} /> Approve</button>
              <button className="btn bad sm" onClick={() => act(i.id, 'rejected', 'Rejected')}><Icon name="x" size={15} /> Reject</button>
            </div>
          </div></div>))}</div>
      ) : <Empty icon="check" title="All caught up" text="There is nothing waiting for your review." />}
    </div>
  );
}
