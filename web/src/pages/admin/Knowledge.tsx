import { useState } from 'react';
import { api, session } from '../../api';
import { Icon } from '../../icons';
import { useApp } from '../../state';
import type { Me } from '../../types';
import { Banner, can, confirmModal, DeptChecks, Empty, fmtDate, Loading, openDrawer, openModal, PageHead, StatusChip, toast, useAction, useLoad, usePoll } from '../../ui';

/* PRD §7 Knowledge, Add information, Approvals; §8 statuses, versions and controlled publication. */
export type DocRow = { item_id: string; version_id: string; title: string; category?: string | null; sensitivity: string; departments: string[];
  department_ids: string[]; version: number; status: string; effective_date?: string | null; expires_at?: string | null; published_at?: string | null;
  updated_at: string; indexed: boolean; filename?: string | null; processing_status?: string | null; owner_name?: string | null; open_proposals: number };
type Listing = { documents: DocRow[]; categories: string[]; sensitivity_levels: string[] };
export type Proposal = { id: string; kind: string; title: string; summary?: string | null; status: string; source: string; submitted_by_name?: string | null;
  submitted_at: string; high_impact: boolean; required_approvals: number; item_id: string; version: number; version_status: string; filename?: string | null;
  processing_status?: string | null; processing_error?: string | null; indexed: boolean; departments: string[]; error?: string | null; mine?: boolean; can_review?: boolean };
type ProposalDetail = Proposal & { meta: Record<string, unknown>; diff: { unified: string[]; metadata_changes: { field: string; from: string | null; to: string | null }[];
  before: { version: number; text: string } | null; after: { version: number; text: string } };
  related: { item_id: string; title: string; version: number; similarity: number }[];
  decisions: { full_name: string; decision: string; note?: string | null; at: string; via: string }[] };

const KIND: Record<string, string> = { create: 'New document', update: 'Change', archive: 'Archive', restore: 'Restore earlier version' };
const listing = (q = '') => api<Listing>('/v1/knowledge/documents?limit=500' + q);
const expired = (d: { expires_at?: string | null }) => !!d.expires_at && new Date(d.expires_at) < new Date();

/* ---------------- Knowledge (browse approved knowledge, versions, citations) ---------------- */
export function KnowledgePage() {
  const { me } = useApp();
  const [q, setQ] = useState(''); const [status, setStatus] = useState('published'); const [cat, setCat] = useState(''); const [dept, setDept] = useState('');
  const { data, error, reload } = useLoad(() => status === 'gaps' ? Promise.resolve(null as unknown as Listing) : listing(status ? '&status=' + status : ''), [status]);
  const rows = (data?.documents || []).filter(d => (!q || d.title.toLowerCase().includes(q.toLowerCase())) && (!cat || d.category === cat)
    && (!dept || d.departments.includes(dept)));
  const depts = [...new Set((data?.documents || []).flatMap(d => d.departments))].sort();
  return (
    <div className="page">
      <PageHead title="Knowledge" sub="Approved company knowledge employees get answers from. Every change goes through review.">
        {can(me, 'propose_knowledge') && <a className="btn primary" href="#/add"><Icon name="plus" size={17} /> Add information</a>}
      </PageHead>
      <div className="flex flex-wrap gap-3 mb-3.5">
        <div className="relative flex-1 min-w-[220px]"><input className="input !pl-10" placeholder="Search titles and text…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search knowledge" />
          <span className="absolute left-3.5 top-3 text-muted"><Icon name="search" /></span></div>
        <select className="select !w-44" value={status} onChange={e => setStatus(e.target.value)} aria-label="Status">
          <option value="gaps">Missing knowledge</option><option value="published">Published</option><option value="under_review">Under review</option><option value="draft">Draft</option><option value="archived">Archived</option><option value="">All</option></select>
        <select className="select !w-44" value={dept} onChange={e => setDept(e.target.value)} aria-label="Department"><option value="">All departments</option>{depts.map(d => <option key={d}>{d}</option>)}</select>
        <select className="select !w-40" value={cat} onChange={e => setCat(e.target.value)} aria-label="Category"><option value="">All categories</option>{(data?.categories || []).map(c => <option key={c}>{c}</option>)}</select>
      </div>
      {status === 'gaps' ? <GapsPanel /> : error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : rows.length ? (
        <div className="table-wrap"><table><thead><tr><th>Title</th><th>Departments</th><th>Category</th><th>Access</th><th>Status</th><th>Effective</th><th>Version</th></tr></thead>
          <tbody>{rows.map(d => (
            <tr key={d.item_id} className="click" tabIndex={0} onClick={() => openDocument(d.item_id, reload, me)} onKeyDown={e => e.key === 'Enter' && openDocument(d.item_id, reload, me)}>
              <td><b>{d.title}</b>{d.open_proposals > 0 && <span className="chip amber ml-2">Change waiting</span>}</td>
              <td>{d.departments.join(', ') || '—'}</td><td>{d.category || '—'}</td>
              <td><span className={`chip ${d.sensitivity === 'unclassified' ? 'red' : ''}`}>{d.sensitivity === 'unclassified' ? 'Needs classification' : d.sensitivity}</span></td>
              <td>{expired(d) ? <span className="chip dot red">Expired</span> : <StatusChip s={d.status} />}</td>
              <td className="whitespace-nowrap">{d.effective_date ? fmtDate(d.effective_date) : fmtDate(d.published_at)}</td><td>v{d.version}</td>
            </tr>))}</tbody></table></div>
      ) : <Empty icon="book" title={data.documents.length ? 'No matches' : 'No knowledge here yet'} text={data.documents.length ? 'Try a different search or filter.' : 'Add the first approved document to get started.'}
        action={can(me, 'propose_knowledge') && !data.documents.length ? <a className="btn primary" href="#/add">Add information</a> : undefined} />}
    </div>
  );
}

type DocDetail = { item: { id: string; title: string; category?: string | null; sensitivity: string; departments: string[]; owner_name?: string | null; provenance?: string | null; vault_path?: string | null };
  published: { id: string; version: number; text?: string | null; effective_date?: string | null; expires_at?: string | null; published_at?: string | null; vault_commit?: string | null; filename?: string | null } | null;
  versions: { id: string; version: number; status: string; created_at: string; published_at?: string | null; change_note?: string | null; approved_by_name?: string | null }[];
  proposals: Proposal[] };

/* Drawers render outside the app provider, so the signed-in person is passed in. */
export async function openDocument(itemId: string, refresh: () => void, me: Me) {
  try {
    const d = await api<DocDetail>(`/v1/knowledge/documents/${itemId}`);
    openDrawer(close => <DocumentDrawer d={d} me={me} close={close} refresh={refresh} />);
  } catch (e) { toast((e as Error).message); }
}

function DocumentDrawer({ d, me, close, refresh }: { d: DocDetail; me: Me; close: () => void; refresh: () => void }) {
  const manage = can(me, 'manage_documents'); const [viewing, setViewing] = useState<{ version: number; text: string } | null>(null);
  const after = (msg: string) => { toast(msg); close(); refresh(); };
  const archive = () => confirmModal('Archive this document?', 'It stops being used in answers once a reviewer approves. Earlier versions stay recoverable.', 'Propose archive',
    async () => { await api(`/v1/admin/documents/${d.item.id}/archive`, { method: 'POST', body: {} }); after('Archive sent for review'); }, false);
  const restore = (v: { id: string; version: number }) => confirmModal(`Publish version ${v.version} again?`, 'This creates a change for review. When approved, this version replaces the current one.', 'Propose restore',
    async () => { await api(`/v1/admin/documents/${d.item.id}/restore`, { method: 'POST', body: { version_id: v.id } }); after('Restore sent for review'); }, false);
  const reindex = async () => { try { await api(`/v1/admin/documents/${d.item.id}/reindex`, { method: 'POST' }); toast('Reindexing in the background'); } catch (e) { toast((e as Error).message); } };
  const show = async (id: string, version: number) => { try { const v = await api<{ text: string }>(`/v1/knowledge/documents/${d.item.id}/versions/${id}`); setViewing({ version, text: v.text || '' }); } catch (e) { toast((e as Error).message); } };
  const pub = d.published;
  return (<div>
    <div className="flex items-start gap-3"><div className="flex-1 min-w-0"><h2 className="text-[21px] font-extrabold tracking-[-.01em]">{d.item.title}</h2>
      <div className="flex flex-wrap gap-1.5 mt-2">{pub ? <StatusChip s="published" /> : <StatusChip s={d.versions[0]?.status || 'draft'} />}{d.item.departments.map(x => <span key={x} className="chip">{x}</span>)}<span className="chip orange">{d.item.sensitivity}</span></div></div>
      <button className="btn ghost sm" onClick={close} aria-label="Close"><Icon name="x" size={18} /></button></div>
    <dl className="kv mt-5 text-[13.5px]">
      <dt>Category</dt><dd>{d.item.category || '—'}</dd><dt>Owner</dt><dd>{d.item.owner_name || '—'}</dd><dt>Source</dt><dd>{d.item.provenance || '—'}</dd>
      {pub && <><dt>Published</dt><dd>v{pub.version} · {fmtDate(pub.published_at)}</dd><dt>Effective</dt><dd>{pub.effective_date ? fmtDate(pub.effective_date) : 'Now'}{pub.expires_at && <> · expires {fmtDate(pub.expires_at)}</>}</dd>
        <dt>Vault</dt><dd className="break-all">{d.item.vault_path}{pub.vault_commit && <span className="hint"> · {pub.vault_commit.slice(0, 8)}</span>}</dd></>}
    </dl>
    <h4 className="mt-5.5 mb-2 text-sm font-bold">{viewing ? `Version ${viewing.version}` : pub ? 'Published text' : 'Text'}{viewing && <button className="text-orange text-xs font-semibold ml-2" onClick={() => setViewing(null)}>Back to published</button>}</h4>
    <div className="whitespace-pre-wrap bg-canvas border border-line rounded-[14px] p-3.5 max-h-[300px] overflow-auto text-ink-2 text-[13.5px]">{(viewing ? viewing.text : pub?.text) || <span className="hint">No text.</span>}</div>
    <h4 className="mt-5.5 mb-2 text-sm font-bold">Versions</h4>
    <ol className="grid gap-2">{d.versions.map(v => (
      <li key={v.id} className="flex flex-wrap items-center gap-2 text-[13.5px]"><b>v{v.version}</b><StatusChip s={v.status} /><span className="hint">{fmtDate(v.published_at || v.created_at)}{v.approved_by_name ? ` · approved by ${v.approved_by_name}` : ''}</span>
        {v.change_note && <span className="text-ink-2">— {v.change_note}</span>}<span className="flex-1" />
        <button className="btn ghost sm" onClick={() => show(v.id, v.version)}>Read</button>
        {manage && v.status === 'archived' && <button className="btn sm" onClick={() => restore(v)}>Restore</button>}</li>))}</ol>
    {d.proposals.length > 0 && <><h4 className="mt-5.5 mb-2 text-sm font-bold">Changes</h4>
      <ol className="grid gap-1.5">{d.proposals.map(p => <li key={p.id} className="text-[13.5px] flex gap-2 items-center"><StatusChip s={p.status} />{KIND[p.kind]}<span className="hint">{fmtDate(p.submitted_at)} · {p.submitted_by_name}</span></li>)}</ol></>}
    <div className="flex flex-wrap gap-3 mt-6">
      {can(me, 'propose_knowledge') && <button className="btn primary" onClick={() => { close(); session.set('qb_update', JSON.stringify({ item_id: d.item.id })); location.hash = '#/add'; }}><Icon name="pen" size={15} /> Propose a change</button>}
      {manage && pub && <button className="btn" onClick={reindex}>Reindex</button>}
      {manage && pub && <button className="btn ghost" onClick={archive}>Archive</button>}
    </div>
  </div>);
}

/* ---------------- Add information (text or upload -> proposal -> review) ---------------- */
type Form = { title: string; category: string; sensitivity: string; provenance: string; info: string; effective: string; expires: string; note: string; high: boolean };

export function AddPage() {
  const { departments } = useApp();
  const [prefill] = useState(() => {
    try {
      const update = JSON.parse(session.get('qb_update') || 'null'); session.set('qb_update', null);
      const p = JSON.parse(session.get('qb_prefill') || 'null'); session.set('qb_prefill', null);
      return { update, title: p?.title as string | undefined, gap: p?.gap_id as string | undefined };
    } catch { return { update: null, title: undefined, gap: undefined }; }
  });
  const updating: string | null = prefill.update?.item_id || null;
  const meta = useLoad(() => listing('&status=published'));
  const existing = useLoad(() => updating ? api<DocDetail>(`/v1/knowledge/documents/${updating}`) : Promise.resolve(null), [updating]);
  const [tab, setTab] = useState(0);
  const blank: Form = { title: prefill.title || '', category: '', sensitivity: '', provenance: '', info: '', effective: '', expires: '', note: '', high: false };
  const [f, setF] = useState<Form>(blank); const [dept, setDept] = useState<string[]>([]); const [loaded, setLoaded] = useState(false);
  const [file, setFile] = useState<File | null>(null); const [ok, setOk] = useState<React.ReactNode>(null); const a = useAction();
  if (existing.data && !loaded) {
    const d = existing.data; setLoaded(true);
    setF({ ...blank, title: d.item.title, category: d.item.category || '', sensitivity: d.item.sensitivity === 'unclassified' ? '' : d.item.sensitivity, provenance: d.item.provenance || '', info: d.published?.text || '' });
    setDept(departments.filter(x => d.item.departments.includes(x.name)).map(x => x.id));
  }
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setOk(null);
    if (!dept.length) { a.setError('Pick at least one department.'); return; }
    if (!f.sensitivity) { a.setError('Choose who may see it (access level).'); return; }
    await a.run(async () => {
      let r: { proposal_id: string; high_impact: boolean };
      if (tab === 1) {
        if (!file) throw new Error('Choose a file to upload.');
        const fd = new FormData(); fd.append('file', file); fd.append('department_ids', dept.join(',')); fd.append('sensitivity', f.sensitivity);
        if (f.title) fd.append('title', f.title); if (f.category) fd.append('category', f.category); if (f.provenance) fd.append('provenance', f.provenance);
        if (f.effective) fd.append('effective_date', f.effective); if (f.expires) fd.append('expires_at', f.expires + 'T00:00:00Z'); if (f.note) fd.append('change_note', f.note);
        if (updating) fd.append('item_id', updating); fd.append('high_impact', String(f.high)); if (prefill.gap) fd.append('gap_id', prefill.gap);
        r = await api('/v1/knowledge/proposals/upload', { method: 'POST', form: fd });
      } else {
        if (!f.info.trim()) throw new Error('Write the information first.');
        r = await api('/v1/knowledge/proposals', { method: 'POST', body: { item_id: updating, title: f.title, body: f.info, department_ids: dept, sensitivity: f.sensitivity,
          category: f.category || null, provenance: f.provenance || null, effective_date: f.effective || null, expires_at: f.expires ? f.expires + 'T00:00:00Z' : null,
          change_note: f.note || null, high_impact: f.high, gap_id: prefill.gap || null } });
      }
      setOk(<>Sent for review{r.high_impact ? ' — this is a high-impact topic, so two people must approve it' : ''}. <a className="underline" href="#/approvals">Follow it in Approvals</a></>);
      if (!updating) { setF(blank); setDept([]); } setFile(null);
    });
  };
  const levels = meta.data?.sensitivity_levels || [];
  return (
    <div className="page max-w-[860px]">
      <PageHead title={updating ? 'Propose a change' : 'Add information'} sub="Write it or upload a document. Reviewers check it before employees can get answers from it." />
      <div className="tabs" role="tablist">{['Write', 'Upload document'].map((t, k) => <button key={t} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => { setTab(k); a.setError(null); setOk(null); }}>{t}</button>)}</div>
      <form className="card grid gap-4.5" onSubmit={submit}>
        {prefill.gap && <Banner kind="ok" className="!bg-orange-50 !text-ink">This answers a question employees asked without getting an approved answer. When it is published, the question is marked resolved.</Banner>}
        {updating && existing.data && <Banner kind="ok" className="!bg-orange-50 !text-ink">Changing <b>{existing.data.item.title}</b> (published v{existing.data.published?.version ?? '—'}). Reviewers will see exactly what changed.</Banner>}
        <div className="field"><label htmlFor="ad-t">Title</label><input id="ad-t" className="input" required={tab === 0} value={f.title} onChange={set('title')} placeholder={tab === 1 ? 'Defaults to the file name' : 'e.g. Refund policy'} /></div>
        <div className="field"><label>Departments that may use it</label><DeptChecks depts={departments} value={dept} onChange={setDept} /></div>
        <div className="grid grid-cols-2 gap-3.5 max-sm:grid-cols-1">
          <div className="field"><label htmlFor="ad-s">Access level</label>
            <select id="ad-s" className="select" required value={f.sensitivity} onChange={set('sensitivity')}><option value="" disabled>Choose…</option>{levels.map(l => <option key={l}>{l}</option>)}</select>
            <span className="hint">Confidential levels are only seen by the roles allowed for them.</span></div>
          <div className="field"><label htmlFor="ad-c">Category</label><input id="ad-c" className="input" list="ad-cats" value={f.category} onChange={set('category')} placeholder="e.g. Pricing, Scripts, SOPs" />
            <datalist id="ad-cats">{(meta.data?.categories || []).map(c => <option key={c} value={c} />)}</datalist></div>
        </div>
        <div className="field"><label htmlFor="ad-p">Source <span className="hint">(where this comes from)</span></label><input id="ad-p" className="input" value={f.provenance} onChange={set('provenance')} placeholder="e.g. HR handbook 2026, CEO decision 12 Oct" /></div>
        {tab === 0 ? (
          <div className="field"><label htmlFor="ad-i">Information <span className="hint">(Markdown: # headings make good sections)</span></label><textarea id="ad-i" className="textarea min-h-[240px]" value={f.info} onChange={set('info')} placeholder="Write the knowledge here…" /></div>
        ) : (
          <div className="field"><label>File</label>
            <label className="block text-center rounded-2xl border-2 border-dashed border-orange bg-orange-50 p-5 cursor-pointer min-h-11"
              onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); setFile(e.dataTransfer.files[0] || null); }}>
              <div className="text-orange flex justify-center"><Icon name="cloud" size={34} /></div>
              <b>{file ? file.name : 'Choose a file or drop it here'}</b><div className="hint">PDF, DOCX, TXT or Markdown. Scanned PDFs without text are rejected.</div>
              <input type="file" hidden accept=".pdf,.docx,.txt,.md,.markdown" onChange={e => setFile(e.target.files?.[0] || null)} />
            </label></div>
        )}
        <div className="grid grid-cols-2 gap-3.5 max-sm:grid-cols-1">
          <div className="field"><label htmlFor="ad-e">Effective from <span className="hint">(optional)</span></label><input id="ad-e" className="input" type="date" value={f.effective} onChange={set('effective')} /></div>
          <div className="field"><label htmlFor="ad-x">Expires on <span className="hint">(optional)</span></label><input id="ad-x" className="input" type="date" value={f.expires} onChange={set('expires')} /></div>
        </div>
        <div className="field"><label htmlFor="ad-n">Note for reviewers <span className="hint">(what changed and why)</span></label><input id="ad-n" className="input" maxLength={1000} value={f.note} onChange={set('note')} /></div>
        <label className="check"><input type="checkbox" checked={f.high} onChange={e => setF({ ...f, high: e.target.checked })} /> High-impact (HR, pay, discounts, refunds, customer payments, security): needs two approvers. Detected automatically too.</label>
        {a.error && <Banner kind="err">{a.error}</Banner>}
        {ok && <Banner kind="ok">{ok}</Banner>}
        <div className="flex justify-end"><button className="btn primary" disabled={a.busy}>{tab === 1 ? <><Icon name="cloud" size={17} /> Upload for review</> : 'Send for review'}</button></div>
      </form>
    </div>
  );
}

/* ---------------- Approvals (§7: diffs, references, conflicts, submitter, reviewer) ---------------- */
export function ApprovalsPage() {
  const { me, setCounts } = useApp();
  const [view, setView] = useState('open');
  const { data, error, reload } = useLoad(() => api<{ proposals: Proposal[] }>('/v1/knowledge/proposals' + (view ? '?status=' + view : '')).then(r => {
    if (view === 'open') setCounts({ pending: r.proposals.filter(p => p.can_review).length }); return r.proposals; }), [view]);
  usePoll(!!data?.some(p => !p.indexed || p.status === 'approved' || p.status === 'publishing'), reload);
  return (
    <div className="page">
      <PageHead title="Approvals" sub="Changes to company knowledge wait here until the right people approve them. Nothing is published automatically.">
        <select className="select !w-52" value={view} onChange={e => setView(e.target.value)} aria-label="Show">
          <option value="open">Waiting for review</option><option value="approved">Approved, publishing</option><option value="published">Published</option>
          <option value="changes_requested">Changes requested</option><option value="rejected">Rejected</option><option value="failed">Publication failed</option><option value="">Everything</option></select>
      </PageHead>
      {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : data.length ? (
        <div className="grid gap-3.5">{data.map(p => (
          <button key={p.id} className="card text-left hover:border-orange transition-colors" onClick={() => openProposal(p.id, reload, me)}>
            <div className="flex flex-wrap items-center gap-2"><b className="text-base">{p.title}</b><span className="chip">{KIND[p.kind]}</span>
              {p.high_impact && <span className="chip red">High impact · {p.required_approvals} approvers</span>}<StatusChip s={p.status} />
              {!p.indexed && p.kind !== 'archive' && <span className="chip blue">Reading the document…</span>}</div>
            <div className="hint mt-1.5">{p.departments.join(', ')} · v{p.version} · {p.submitted_by_name || 'someone'} · {fmtDate(p.submitted_at)} · via {p.source}{p.filename ? ` · ${p.filename}` : ''}</div>
            {p.summary && <p className="text-ink-2 mt-1.5 line-clamp-2">{p.summary}</p>}
            {p.error && <p className="text-bad mt-1.5 text-[13.5px]">{p.error}</p>}
          </button>))}</div>
      ) : <Empty icon="check" title="All caught up" text={view === 'open' ? 'There is nothing waiting for your review.' : 'Nothing here.'} />}
    </div>
  );
}

async function openProposal(id: string, refresh: () => void, me: Me) {
  try { const p = await api<ProposalDetail>(`/v1/knowledge/proposals/${id}`); openDrawer(close => <ProposalDrawer p={p} me={me} close={close} refresh={refresh} />); }
  catch (e) { toast((e as Error).message); }
}

function DiffView({ lines }: { lines: string[] }) {
  if (!lines.length) return <p className="hint">The text did not change.</p>;
  return (<pre className="bg-canvas border border-line rounded-[14px] p-3 max-h-[340px] overflow-auto text-[12.5px] leading-[1.55] whitespace-pre-wrap">
    {lines.slice(2).map((l, i) => <div key={i} className={l.startsWith('+') ? 'bg-good-50 text-good' : l.startsWith('-') ? 'bg-bad-50 text-bad line-through decoration-1' : l.startsWith('@@') ? 'text-muted' : 'text-ink-2'}>{l}</div>)}
  </pre>);
}

function ProposalDrawer({ p, me, close, refresh }: { p: ProposalDetail; me: Me; close: () => void; refresh: () => void }) {
  const [note, setNote] = useState(''); const a = useAction();
  const decide = (action: 'approve' | 'reject' | 'request-changes') => a.run(async () => {
    const r = await api<{ status: string; waiting_for?: string[] }>(`/v1/admin/proposals/${p.id}/${action}`, { method: 'POST', body: { note: note.trim() || null } });
    toast(r.status === 'approved' ? 'Approved — publishing now' : r.status === 'open' ? `Approval recorded. Still needs ${r.waiting_for?.join(' and ')}` : r.status === 'rejected' ? 'Rejected' : 'Sent back for changes');
    close(); refresh();
  });
  const retry = () => a.run(async () => { await api(`/v1/admin/proposals/${p.id}/retry`, { method: 'POST' }); toast('Publishing again'); close(); refresh(); });
  const withdraw = () => a.run(async () => { await api(`/v1/knowledge/proposals/${p.id}/withdraw`, { method: 'POST' }); toast('Withdrawn'); close(); refresh(); });
  return (<div>
    <div className="flex items-start gap-3"><div className="flex-1 min-w-0"><h2 className="text-[21px] font-extrabold tracking-[-.01em]">{p.title}</h2>
      <div className="flex flex-wrap gap-1.5 mt-2"><span className="chip">{KIND[p.kind]}</span><StatusChip s={p.status} />{p.high_impact && <span className="chip red">High impact</span>}</div></div>
      <button className="btn ghost sm" onClick={close} aria-label="Close"><Icon name="x" size={18} /></button></div>
    <p className="hint mt-2">Proposed by {p.submitted_by_name} · {fmtDate(p.submitted_at)} · via {p.source}{p.filename ? ` · ${p.filename}` : ''}</p>
    {p.summary && <p className="mt-2 text-ink-2">{p.summary}</p>}
    {p.processing_error && <Banner kind="err" className="mt-3">This file could not be read: {p.processing_error}</Banner>}
    {p.diff.metadata_changes.length > 0 && <><h4 className="mt-5 mb-2 text-sm font-bold">Settings that change</h4>
      <dl className="kv text-[13.5px]">{p.diff.metadata_changes.map(c => <><dt key={c.field + 'k'}>{c.field}</dt><dd key={c.field}><span className="line-through text-muted">{c.from || '—'}</span> → <b>{c.to}</b></dd></>)}</dl></>}
    <h4 className="mt-5 mb-2 text-sm font-bold">{p.kind === 'archive' ? 'Text that will stop being used' : p.diff.before ? `What changes (v${p.diff.before.version} → v${p.diff.after.version})` : 'New text'}</h4>
    {p.diff.before || p.kind === 'archive' ? <DiffView lines={p.diff.unified} />
      : <div className="whitespace-pre-wrap bg-canvas border border-line rounded-[14px] p-3.5 max-h-[340px] overflow-auto text-ink-2 text-[13.5px]">{p.diff.after.text || <span className="hint">The document is still being read…</span>}</div>}
    {p.related.length > 0 && <><h4 className="mt-5 mb-2 text-sm font-bold">Related published knowledge <span className="hint font-normal">— check for conflicts or duplicates</span></h4>
      <ul className="grid gap-1.5">{p.related.map(r => <li key={r.item_id} className="text-[13.5px]"><button className="text-orange font-semibold" onClick={() => openDocument(r.item_id, () => {}, me)}>{r.title}</button> <span className="hint">v{r.version} · {Math.round(r.similarity * 100)}% similar</span></li>)}</ul></>}
    {p.decisions.length > 0 && <><h4 className="mt-5 mb-2 text-sm font-bold">Decisions ({p.decisions.filter(d => d.decision === 'approve').length} of {p.required_approvals} approvals)</h4>
      <ol className="grid gap-1.5">{p.decisions.map((d, i) => <li key={i} className="text-[13.5px]"><b>{d.full_name}</b> {d.decision.replace('_', ' ')}d{d.note && <> — “{d.note}”</>} <span className="hint">{fmtDate(d.at)} · {d.via}</span></li>)}</ol></>}
    {p.can_review && (<div className="mt-6 grid gap-3">
      <div className="field"><label htmlFor="pr-n">Note <span className="hint">(required to reject or ask for changes)</span></label><input id="pr-n" className="input" maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></div>
      {a.error && <Banner kind="err">{a.error}</Banner>}
      <div className="flex flex-wrap gap-3"><button className="btn good" disabled={a.busy || !p.indexed && p.kind !== 'archive'} onClick={() => decide('approve')}><Icon name="check" size={15} /> Approve</button>
        <button className="btn" disabled={a.busy} onClick={() => decide('request-changes')}>Ask for changes</button>
        <button className="btn bad" disabled={a.busy} onClick={() => decide('reject')}><Icon name="x" size={15} /> Reject</button></div>
    </div>)}
    {!p.can_review && p.status === 'failed' && can(me, 'manage_documents') && <div className="mt-6"><button className="btn primary" disabled={a.busy} onClick={retry}>Try publishing again</button></div>}
    {p.mine && (p.status === 'open' || p.status === 'changes_requested') && <div className="mt-4"><button className="btn ghost" disabled={a.busy} onClick={withdraw}>Withdraw</button></div>}
  </div>);
}


/* ---------------- Missing knowledge (§7 Knowledge "inspect knowledge gaps", §9 gap loop) ---------------- */
type Gap = { id: string; question: string; department?: string | null; department_id?: string | null; status: string; occurrences: number; reports: number;
  first_seen: string; last_seen: string; comments: string[]; note?: string | null };

function GapsPanel() {
  const { me, departments } = useApp();
  const [view, setView] = useState('active');
  const { data, error, reload } = useLoad(() => api<{ gaps: Gap[] }>('/v1/admin/knowledge-gaps?status=' + view).then(r => r.gaps), [view]);
  const answer = (g: Gap) => { session.set('qb_prefill', JSON.stringify({ title: g.question, gap_id: g.id })); location.hash = '#/add'; };
  const patch = async (g: Gap, body: object, msg: string) => { try { await api(`/v1/admin/knowledge-gaps/${g.id}`, { method: 'PATCH', body }); toast(msg); reload(); } catch (e) { toast((e as Error).message); } };
  const dismiss = (g: Gap) => openModal('Dismiss this question?', close => <DismissGap close={close} save={note => patch(g, { status: 'dismissed', note }, 'Dismissed')} />);
  const triage = can(me, 'manage_knowledge_gaps');
  return (<>
    <div className="flex gap-2 mb-3">{[['active', 'Open'], ['resolved', 'Resolved'], ['dismissed', 'Dismissed']].map(([k, l]) =>
      <button key={k} className={`chipbtn ${view === k ? 'on' : ''}`} onClick={() => setView(k)}>{l}</button>)}</div>
    {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : data.length ? (
      <div className="grid gap-3">{data.map(g => (
        <div key={g.id} className="card !p-4">
          <div className="flex flex-wrap items-start gap-3"><div className="flex-1 min-w-[240px]"><b>“{g.question}”</b>
            <div className="hint mt-1">Asked {g.occurrences}× · reported {g.reports}× · last {fmtDate(g.last_seen)} · {g.department || 'No department yet'}{g.status === 'in_progress' ? ' · being answered' : ''}</div>
            {g.comments.length > 0 && <ul className="mt-1.5 text-[13.5px] text-ink-2">{g.comments.map((c, i) => <li key={i}>“{c}”</li>)}</ul>}
            {g.note && <p className="hint mt-1">{g.note}</p>}</div>
            {view === 'active' && <div className="flex flex-wrap gap-2">
              {can(me, 'propose_knowledge') && <button className="btn primary sm" onClick={() => answer(g)}>Answer it</button>}
              {triage && <select className="select !h-8 !w-44 text-[13px]" value={g.department_id || ''} aria-label="Department"
                onChange={e => patch(g, e.target.value ? { department_id: e.target.value } : { unassign: true }, 'Moved')}>
                <option value="">No department</option>{departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>}
              <button className="btn ghost sm" onClick={() => dismiss(g)}>Dismiss</button></div>}
          </div>
        </div>))}</div>
    ) : <Empty icon="check" title={view === 'active' ? 'No missing knowledge' : 'Nothing here'} text="Questions employees asked without getting an approved answer appear here." />}
  </>);
}

function DismissGap({ close, save }: { close: () => void; save: (note: string) => void }) {
  const [note, setNote] = useState('');
  return (<>
    <div className="field mb-4"><label htmlFor="dg-n">Why?</label><input id="dg-n" className="input" autoFocus maxLength={1000} placeholder="e.g. Out of scope, duplicate, small talk" value={note} onChange={e => setNote(e.target.value)} /></div>
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={!note.trim()} onClick={() => { close(); save(note.trim()); }}>Dismiss</button></div>
  </>);
}
