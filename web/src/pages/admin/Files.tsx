import { useState } from 'react';
import { api } from '../../api';
import { Icon } from '../../icons';
import { useApp } from '../../state';
import { Banner, confirmModal, Empty, fmtDate, Loading, PageHead, StatusChip, toast, useAction, useLoad, usePoll } from '../../ui';

/* PRD §7 Documents: uploaded files, processing state, delete. */
const PROC: Record<string, [string, string]> = { pending: ['Waiting', 'amber'], processing: ['Processing', 'blue'], ready: ['Ready', 'green'], failed: ['Failed', 'red'] };
type Doc = { id: string; title: string; filename: string; departments: string[]; status: string; processing_status: string; processing_error?: string; size_bytes?: number; updated_at: string };

export function DocumentsPage() {
  const { rank } = useApp();
  const { data, error, reload } = useLoad(() => api<{ documents: Doc[] }>('/v1/documents?limit=200').then(r => r.documents));
  usePoll(!!data?.some(d => d.processing_status === 'pending' || d.processing_status === 'processing'), reload);
  const del = (d: Doc) => confirmModal('Delete this document?', 'The file, its text and its place in answers are removed. This cannot be undone.', 'Delete', async () => {
    await api(`/v1/documents/${d.id}`, { method: 'DELETE' }); toast('Deleted'); reload();
  });
  return (
    <div className="page">
      <PageHead title="Documents" sub="Uploaded files and whether they are ready to answer questions."><a className="btn primary" href="#/add"><Icon name="cloud" size={17} /> Upload document</a></PageHead>
      {error ? <Banner kind="err">{error}</Banner> : !data ? <Loading /> : data.length ? (
        <div className="table-wrap"><table><thead><tr><th>File</th><th>Departments</th><th>Status</th><th>Processing</th><th>Size</th><th>Updated</th>{rank >= 3 && <th />}</tr></thead>
          <tbody>{data.map(d => { const [pl, pc] = PROC[d.processing_status] || [d.processing_status, '']; return (
            <tr key={d.id}><td><b>{d.title}</b><div className="hint">{d.filename}</div></td><td>{d.departments.join(', ')}</td><td><StatusChip s={d.status} /></td>
              <td><span className={`chip dot ${pc}`}>{pl}</span>{d.processing_error && <div className="hint !text-bad">{d.processing_error}</div>}</td>
              <td>{d.size_bytes ? (d.size_bytes / 1048576).toFixed(1) + ' MB' : '—'}</td><td>{fmtDate(d.updated_at)}</td>
              {rank >= 3 && <td><button className="btn ghost sm" title="Delete" aria-label={`Delete ${d.title}`} onClick={() => del(d)}><Icon name="trash" size={16} /></button></td>}</tr>); })}</tbody></table></div>
      ) : <Empty icon="doc" title="No documents yet" text="Upload a PDF, Word, text, Markdown, JSON or CSV file." action={<a className="btn primary" href="#/add">Upload document</a>} />}
    </div>
  );
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
