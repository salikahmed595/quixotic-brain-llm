import { useState } from 'react';
import { api } from '../../api';
import { Icon } from '../../icons';
import { useApp } from '../../state';
import { Banner, can, confirmModal, DeptChecks, Empty, fmtDate, Loading, openModal, PageHead, StatusChip, toast, useAction, useLoad, usePoll } from '../../ui';
import { DocRow, openDocument } from './Knowledge';
import type { Me } from '../../types';

/* PRD §7 Documents: upload, parse status, permissions, versions, archive, reindex; Obsidian import (§14 P0). */
const PROC: Record<string, [string, string]> = { pending: ['Waiting', 'amber'], processing: ['Reading', 'blue'], ready: ['Read', 'green'], failed: ['Unreadable', 'red'] };

export function DocumentsPage() {
  const { me } = useApp();
  const { data, error, reload } = useLoad(() => api<{ documents: DocRow[] }>('/v1/knowledge/documents?limit=500').then(r => r.documents));
  usePoll(!!data?.some(d => d.processing_status === 'pending' || d.processing_status === 'processing' || d.open_proposals > 0), reload, 5000);
  const del = (d: DocRow) => confirmModal('Delete this unpublished document?', 'It was never published, so nothing else depends on it. This cannot be undone.', 'Delete', async () => {
    await api(`/v1/admin/documents/${d.item_id}`, { method: 'DELETE' }); toast('Deleted'); reload();
  });
  const { departments } = useApp();
  const importVault = () => openModal('Import Obsidian notes', close => <ObsidianImport me={me} departments={departments} close={close} done={reload} />, { wide: true });
  const unclassified = (data || []).filter(d => d.sensitivity === 'unclassified');
  const classify = () => openModal('Classify documents', close => <Classify docs={unclassified} close={close} done={reload} />, { wide: true });
  return (
    <div className="page">
      <PageHead title="Documents" sub="Every document, its version, who may see it, and whether it is ready to answer questions.">
        <div className="flex gap-2.5"><button className="btn" onClick={importVault}><Icon name="book" size={17} /> Import Obsidian notes</button>
          <a className="btn primary" href="#/add"><Icon name="cloud" size={17} /> Upload document</a></div>
      </PageHead>
      {unclassified.length > 0 && (me.can_publish || me.role === 'founder_ceo') && <Banner kind="err" className="mb-4 flex flex-wrap items-center gap-3">
        <span className="flex-1"><b>{unclassified.length} document{unclassified.length === 1 ? ' has' : 's have'} no access level yet</b> and {unclassified.length === 1 ? 'is' : 'are'} not used in answers until classified.</span>
        <button className="btn sm primary" onClick={classify}>Classify now</button></Banner>}
      {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : data.length ? (
        <div className="table-wrap"><table><thead><tr><th>Document</th><th>Departments</th><th>Access</th><th>Status</th><th>Search index</th><th>Updated</th><th /></tr></thead>
          <tbody>{data.map(d => { const [pl, pc] = PROC[d.processing_status || ''] || ['Text', ''];
            return (<tr key={d.item_id} className="click" onClick={() => openDocument(d.item_id, reload, me)}>
              <td><b>{d.title}</b><div className="hint">{d.filename || 'Written in the app'} · v{d.version}</div></td><td>{d.departments.join(', ')}</td>
              <td><span className={`chip ${d.sensitivity === 'unclassified' ? 'red' : ''}`}>{d.sensitivity === 'unclassified' ? 'Needs classification' : d.sensitivity}</span></td>
              <td><StatusChip s={d.status} />{d.open_proposals > 0 && <div className="hint mt-1">change waiting</div>}</td>
              <td>{d.filename && d.processing_status !== 'ready' ? <span className={`chip dot ${pc}`}>{pl}</span> : d.indexed ? <span className="chip dot green">Indexed</span> : <span className="chip dot amber">Not indexed</span>}</td>
              <td>{fmtDate(d.updated_at)}</td>
              <td onClick={e => e.stopPropagation()}>{can(me, 'manage_documents') && d.status !== 'published' && d.status !== 'archived' && !d.published_at &&
                <button className="btn ghost sm" title="Delete" aria-label={`Delete ${d.title}`} onClick={() => del(d)}><Icon name="trash" size={16} /></button>}</td></tr>); })}</tbody></table></div>
      ) : <Empty icon="doc" title="No documents yet" text="Upload a PDF, Word, text or Markdown file, or import your Obsidian notes." action={<a className="btn primary" href="#/add">Upload document</a>} />}
    </div>
  );
}

function ObsidianImport({ me, departments, close, done }: { me: Me; departments: { id: string; name: string }[]; close: () => void; done: () => void }) {
  const [files, setFiles] = useState<FileList | null>(null); const [dept, setDept] = useState<string[]>([]); const [level, setLevel] = useState('');
  const [approve, setApprove] = useState(false); const [res, setRes] = useState<{ note: string; ok: boolean; error?: string; duplicate?: boolean }[] | null>(null);
  const levels = useLoad(() => api<{ sensitivity_levels: string[] }>('/v1/knowledge/documents?limit=1').then(r => r.sensitivity_levels));
  const a = useAction();
  const submit = () => a.run(async () => {
    if (!files?.length) throw new Error('Choose .md notes or a .zip of your vault.');
    const fd = new FormData(); Array.from(files).forEach(f => fd.append('files', f)); fd.append('department_ids', dept.join(','));
    if (level) fd.append('sensitivity', level); fd.append('approve', String(approve));
    const r = await api<{ results: typeof res }>('/v1/admin/documents/import-obsidian', { method: 'POST', form: fd }); setRes(r.results); done();
  });
  return (<>
    <p className="text-ink-2 mb-4">Each note becomes a document change for review. Front matter (<code>title</code>, <code>departments</code>, <code>sensitivity</code>, <code>category</code>,
      <code> source</code>, <code>effective_date</code>, <code>expires</code>) fills the details; the choices below are used when a note has none.</p>
    <div className="grid gap-4">
      <div className="field"><label>Notes</label><input type="file" multiple accept=".md,.zip" onChange={e => setFiles(e.target.files)} className="input !h-auto py-2" /></div>
      <div className="field"><label>Departments for notes without any</label><DeptChecks depts={departments} value={dept} onChange={setDept} /></div>
      <div className="field"><label htmlFor="ob-l">Access level for notes without one</label><select id="ob-l" className="select" value={level} onChange={e => setLevel(e.target.value)}><option value="">From the note only</option>{(levels.data || []).map(l => <option key={l}>{l}</option>)}</select></div>
      {(me.can_publish || me.role === 'founder_ceo') && <label className="check"><input type="checkbox" checked={approve} onChange={e => setApprove(e.target.checked)} /> These notes are already approved: record my approval (high-impact notes still need a second approver)</label>}
    </div>
    {a.error && <Banner kind="err" className="mt-3">{a.error}</Banner>}
    {res && <div className="mt-4 max-h-[220px] overflow-auto"><ul className="grid gap-1 text-[13.5px]">{res.map(r => <li key={r.note}>{r.ok ? (r.duplicate ? '↺' : '✓') : '✗'} {r.note}{r.error && <span className="text-bad"> — {r.error}</span>}{r.duplicate && <span className="hint"> — already imported</span>}</li>)}</ul></div>}
    <div className="flex justify-end gap-3 mt-5"><button className="btn" onClick={close}>{res ? 'Close' : 'Cancel'}</button>{!res && <button className="btn primary" disabled={a.busy} onClick={submit}>Import</button>}</div>
  </>);
}

/* PRD §7 Sales memory. Answers from past chats are OFF (owner, 2026-10-17); imports stay available for later review. */
const JOB: Record<string, [string, string]> = { queued: ['Waiting', 'amber'], running: ['Processing', 'blue'], succeeded: ['Ready', 'green'], failed: ['Failed', 'red'] };
type Import = { id: string; filename?: string; department?: string; status: string; error?: string; stored: number; created_at: string; progress_done?: number; progress_total?: number };

export function SalesPage() {
  const { departments } = useApp();
  const { data, error, reload } = useLoad(() => api<{ imports: Import[] }>('/v1/sales-memory/imports').then(r => r.imports));
  usePoll(!!data?.some(r => r.status === 'queued' || r.status === 'running'), reload);
  const [dept, setDept] = useState(''); const [file, setFile] = useState<File | null>(null); const [detect, setDetect] = useState('');
  const [ok, setOk] = useState(false); const a = useAction();
  const pick = async (f: File | null) => {
    setFile(f); setDetect(''); if (!f) return;
    try { const d = JSON.parse(await f.text()); const recs = Array.isArray(d) ? d : [];
      setDetect(recs.length ? `Detected: ${new Set(recs.map((r: { conversation_id?: string }) => r.conversation_id)).size.toLocaleString()} conversations, ${recs.length.toLocaleString()} messages` : 'This file is not a list of chat records.');
    } catch { setDetect('This file is not valid JSON.'); }
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault(); setOk(false);
    a.run(async () => {
      if (!file) throw new Error('Choose a JSON file.');
      const fd = new FormData(); fd.append('file', file); fd.append('department_id', dept);
      await api('/v1/sales-memory/imports', { method: 'POST', form: fd }); setOk(true); setFile(null); setDetect(''); reload();
    });
  };
  const del = (r: Import) => confirmModal('Remove these chats?', 'The chats from this file are removed. You can upload the file again later.', 'Remove', async () => {
    await api(`/v1/sales-memory/imports/${r.id}`, { method: 'DELETE' }); toast('Removed'); reload();
  });
  return (
    <div className="page max-w-[980px]">
      <PageHead title="Sales memory" sub="Past sales chats, imported per department." />
      <Banner kind="ok" className="!bg-orange-50 !text-ink mb-4">Answers written from past sales chats are switched off. Employees get answers only from approved company knowledge.</Banner>
      <form className="card grid gap-4.5 mb-5.5" onSubmit={submit}>
        <div className="field"><label htmlFor="sm-d">Department</label>
          <select id="sm-d" className="select" required value={dept} onChange={e => setDept(e.target.value)}><option value="">Choose who these chats are for…</option>{departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
        <div className="field"><label>Chats file (JSON)</label>
          <label className="block text-center rounded-2xl border-2 border-dashed border-orange bg-orange-50 p-5 cursor-pointer" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); pick(e.dataTransfer.files[0] || null); }}>
            <div className="text-orange flex justify-center"><Icon name="cloud" size={34} /></div><b>{file ? file.name : 'Choose a JSON file or drop it here'}</b>
            <div className="hint">{detect || 'One object per message: customer_message, agent_response, scenario, outcome…'}</div>
            <input type="file" accept=".json" hidden onChange={e => pick(e.target.files?.[0] || null)} />
          </label></div>
        {a.error && <Banner kind="err">{a.error}</Banner>}
        {ok && <Banner kind="ok">Uploaded. The chats are being processed below; large files take a few minutes.</Banner>}
        <div className="flex justify-end"><button className="btn primary" disabled={a.busy}><Icon name="cloud" size={17} /> Process conversations</button></div>
      </form>
      <h3 className="font-bold mb-2.5">Imports</h3>
      {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : data.length ? (
        <div className="table-wrap"><table><thead><tr><th>File</th><th>Department</th><th>Status</th><th>Chats stored</th><th>Uploaded</th><th /></tr></thead>
          <tbody>{data.map(r => { const [l, c] = JOB[r.status] || [r.status, '']; const prog = r.status === 'running' && r.progress_total ? ` ${Math.round(100 * (r.progress_done || 0) / r.progress_total)}%` : '';
            return (<tr key={r.id}><td><b>{r.filename || 'chats.json'}</b></td><td>{r.department || '—'}</td>
              <td><span className={`chip dot ${c}`}>{l}{prog}</span>{r.error && <div className="hint !text-bad">{r.error}</div>}</td><td>{Number(r.stored).toLocaleString()}</td><td>{fmtDate(r.created_at)}</td>
              <td>{(r.status === 'succeeded' || r.status === 'failed') && r.stored > 0 && <button className="btn ghost sm" title="Remove these chats" aria-label="Remove these chats" onClick={() => del(r)}><Icon name="trash" size={16} /></button>}</td></tr>); })}</tbody></table></div>
      ) : <Empty icon="msg" title="No chats imported yet" text="Upload a JSON file of past sales chats and choose the department it belongs to." />}
    </div>
  );
}


/* PRD §8 / §10: documents from before access levels existed are hidden from answers until a publisher classifies them. */
function Classify({ docs, close, done }: { docs: DocRow[]; close: () => void; done: () => void }) {
  const [sel, setSel] = useState<Set<string>>(new Set(docs.map(d => d.item_id))); const [level, setLevel] = useState('');
  const levels = useLoad(() => api<{ sensitivity_levels: string[] }>('/v1/knowledge/documents?limit=1').then(r => r.sensitivity_levels));
  const a = useAction();
  const toggle = (id: string, on: boolean) => { const s = new Set(sel); if (on) s.add(id); else s.delete(id); setSel(s); };
  return (<>
    <p className="text-ink-2 mb-3">Choose who may see these documents. They start being used in answers right away for the people allowed.</p>
    <div className="field mb-3"><label htmlFor="cl-l">Access level</label><select id="cl-l" className="select" value={level} onChange={e => setLevel(e.target.value)}>
      <option value="" disabled>Choose…</option>{(levels.data || []).map(l => <option key={l}>{l}</option>)}</select></div>
    <div className="max-h-[300px] overflow-auto border border-line rounded-[14px] p-2 mb-3">
      <label className="check font-semibold"><input type="checkbox" checked={sel.size === docs.length} onChange={e => setSel(e.target.checked ? new Set(docs.map(d => d.item_id)) : new Set())} /> All ({docs.length})</label>
      {docs.map(d => <label key={d.item_id} className="check"><input type="checkbox" checked={sel.has(d.item_id)} onChange={e => toggle(d.item_id, e.target.checked)} /> {d.title} <span className="hint">· {d.departments.join(', ')}</span></label>)}</div>
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex justify-end gap-3"><button className="btn" onClick={close}>Cancel</button>
      <button className="btn primary" disabled={a.busy || !level || !sel.size} onClick={() => a.run(async () => {
        const r = await api<{ classified: number }>('/v1/admin/documents/classify', { method: 'POST', body: { item_ids: [...sel], sensitivity: level } });
        close(); toast(`${r.classified} document${r.classified === 1 ? '' : 's'} classified as ${level}`); done(); })}>Classify {sel.size}</button></div>
  </>);
}
