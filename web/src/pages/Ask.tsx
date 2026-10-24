import { useEffect, useRef, useState } from 'react';
import { api, session } from '../api';
import { Icon } from '../icons';
import { Mascot } from '../components/Mascot';
import { go, replaceRoute, useApp, useRoute } from '../state';
import { Banner, can, copyWithToast, Loading, openDrawer, openModal, toast, useAction } from '../ui';
import type { Msg, Source } from '../types';

/* PRD §4.1 home screen + §6 chat. Suggestion cards submit example questions; they are never hard-coded answers (FR-CHAT-03). */
const SUGGESTIONS: [string, string, string][] = [
  ['msg', 'Customer says too expensive', 'A customer says the price is too expensive. How should I respond?'],
  ['doc', 'Booking script', 'What is the booking script?'],
  ['shield', 'Refund policy', 'What is our refund policy?'],
  ['users', 'Lead qualification', 'How do I qualify a lead?'],
];
/* Floating labels around the mascot; clicking one starts a question. Positions measured from the screenshots (px from centre). */
const BUBBLES = [
  { label: 'Scripts', icon: 'doc', side: 'l', x: -268, y: 36, fill: 'Show me the script for ' },
  { label: 'Policies', icon: 'shield', side: 'l', x: -229, y: 118, fill: 'What is our policy on ' },
  { label: 'Objections', icon: 'msg', side: 'r', x: 132, y: 30, fill: 'How do I handle this objection: ' },
  { label: 'SOPs', icon: 'doc', side: 'r', x: 133, y: 110, fill: 'What is the SOP for ' },
];
const MODES = [['general', 'Answer', 'Ask anything within your departments'], ['search', 'Search only', 'Show matching knowledge without writing an answer']];
// Owner-approved addition 2026-10-20 (docs/PRD_GAPS.md §0): shown only to upsellers and fresh sellers; the server checks again.
const TRANSLATE_MODE = ['translate', 'Translate', 'Any language → any language you type, ready to send'];
// QA 2026-10-24 (QAI-01): same list as the server (backend/api/v1/translate.py TARGET_LANGUAGES)
const TARGETS = ['English', 'Roman Urdu', 'Urdu', 'Spanish', 'German', 'French', 'Arabic', 'Portuguese', 'Italian', 'Turkish', 'Hindi', 'Chinese',
  'Japanese', 'Korean', 'Russian', 'Punjabi', 'Persian', 'Indonesian'];
const CONF: Record<string, [string, string]> = { high: ['High confidence', 'green'], medium: ['Medium confidence', 'amber'], low: ['Low confidence', 'red'], general: ['General AI answer', ''] };
const REASONS = ['Wrong answer', 'Not what I asked', 'Too long', 'Too short', 'Missing information'];

function fromStored(c: any): Msg {
  if (c.kind === 'search') return { role: 'ai', kind: 'search', question: c.question, results: c.results || [] };
  return { role: 'ai', kind: 'ask', question: c.question, query_id: c.query_id, answer: c.answer, confidence: c.confidence, sources: c.sources || [], found: !c.actions, gap_id: c.gap_id };
}

export function Ask({ resetKey }: { resetKey: number }) {
  const app = useApp(); const route = useRoute();
  const [thread, setThread] = useState<Msg[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [scope, setScope] = useState<string | null>(null);
  const [mode, setMode] = useState('general');
  const [target, setTarget] = useState('English');          // QAI-01: chosen translation language
  const [busy, setBusy] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const threadEnd = useRef<HTMLDivElement>(null);

  useEffect(() => { // open a saved chat, or start fresh on "New chat"
    if (!route.chat) { setThread([]); setConvId(null); return; }
    if (route.chat === convId) return;
    setLoadingChat(true);
    api(`/v1/chats/${route.chat}`).then(conv => {
      setThread(conv.messages.map((m: any) => m.role === 'user' ? { role: 'user', text: m.content.text } : fromStored(m.content)));
      setConvId(conv.id); setMode('general');
      const dep = conv.department_id && app.departments.find(d => d.id === conv.department_id); setScope(dep ? dep.name : null);
    }).catch(e => { toast(e.status === 404 ? 'That chat no longer exists.' : e.message); go('ask'); })
      .finally(() => setLoadingChat(false));
  }, [route.chat, resetKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { threadEnd.current?.scrollIntoView({ block: 'end' }); }, [thread]);

  const submit = async (text: string, forceMode?: string) => {
    const q = text.trim(); if (!q || busy) return;
    setBusy(true);
    setThread(t => [...t, { role: 'user', text: q }, { role: 'ai', loading: true }]);
    const m2 = forceMode || mode, body = { question: q, department: scope || undefined, conversation_id: convId || undefined };
    let msg: Msg;
    try {
      if (m2 === 'translate') {                     // not saved to chat history: client messages stay private
        const r = await api('/v1/translate', { method: 'POST', body: { text: q, target } });
        msg = { role: 'ai', kind: 'translate', question: q, english: r.english, target: r.target };
      } else if (m2 === 'search') {
        const r = await api('/v1/search', { method: 'POST', body });
        msg = { role: 'ai', kind: 'search', question: q, results: r.results }; saved(r);
      } else {
        const r = await api('/v1/ask', { method: 'POST', body: { ...body, mode: 'general' } });
        msg = { role: 'ai', kind: 'ask', question: q, query_id: r.query_id, answer: r.answer, confidence: r.confidence, sources: r.sources || [], found: !r.actions, gap_id: r.gap_id }; saved(r);
      }
    } catch (e) { msg = { role: 'ai', error: (e as Error).message, question: q }; }
    setThread(t => [...t.slice(0, -1), msg]); setBusy(false);
  };
  const saved = (r: { conversation_id?: string }) => {
    if (!r.conversation_id) return;
    if (!convId) { setConvId(r.conversation_id); replaceRoute('chat/' + r.conversation_id); }
    app.reloadChats();
  };
  const update = (i: number, patch: Partial<Msg>) => setThread(t => t.map((m, k) => (k === i ? ({ ...m, ...patch } as Msg) : m)));
  const retry = (i: number, question: string) => { setThread(t => t.slice(0, i - 1)); setTimeout(() => submit(question)); };

  const composer = (compact: boolean) => (
    <Composer compact={compact} busy={busy} mode={mode} setMode={setMode} target={target} setTarget={setTarget} scope={scope} setScope={setScope} onSend={submit} />
  );

  if (loadingChat) return <Loading />;

  if (!thread.length) return (
    <div className="hero-glow relative flex-1 flex flex-col overflow-hidden">
      <Waves />
      <div className="relative z-[1] flex flex-col items-center w-full max-w-[1000px] mx-auto px-5 pt-[85px] pb-10 max-md:pt-16">
        <h1 className="relative text-center font-extrabold tracking-[-0.035em] leading-[1.1] text-[clamp(38px,6vw,58px)]">
          Ask <span className="text-orange">Quixotic AI</span>
          <svg className="absolute left-[calc(100%+10px)] -top-[22px] w-[38px] h-[38px] text-orange max-md:w-7 max-md:h-7 max-md:left-[calc(100%+4px)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 1.5l2.4 8.1 8.1 2.4-8.1 2.4L12 22.5l-2.4-8.1L1.5 12l8.1-2.4z" />
          </svg>
        </h1>
        <p className="text-ink-2 text-center max-w-[600px] mt-3.5 text-[clamp(15px,2vw,18px)] leading-[1.5]">
          Get instant answers from your call center knowledge base — scripts, objections, SOPs, policies and more.
        </p>
        {/* mascot stage: 216 px tall on desktop; on small screens the labels reflow under the mascot (PRD §4.4) */}
        <div className="relative w-full h-[216px] flex-none max-md:h-auto max-md:flex max-md:flex-col max-md:items-center max-md:py-4">
          <Mascot className="mascot md:absolute md:left-1/2 md:top-[21px] md:-ml-[77px]" width={155} />
          <div className="max-md:flex max-md:flex-wrap max-md:justify-center max-md:gap-2 max-md:mt-3">
            {BUBBLES.map(b => (
              <button key={b.label} className={`bubble ${b.side} max-md:!static max-md:after:hidden`} style={{ left: `calc(50% + ${b.x}px)`, top: b.y }}
                onClick={() => { const el = document.getElementById('q') as HTMLTextAreaElement | null; if (el) { el.value = b.fill; el.dispatchEvent(new Event('input', { bubbles: true })); el.focus(); } }}>
                <Icon name={b.icon} />{b.label}
              </button>
            ))}
          </div>
        </div>
        <div className="w-full max-w-[960px]">{composer(false)}</div>
        <div className="w-full max-w-[960px] mt-[26px]">
          <p className="text-muted text-sm mb-2.5">Try asking about...</p>
          <div className="grid grid-cols-4 gap-3 max-lg:grid-cols-2 max-sm:flex max-sm:overflow-x-auto max-sm:snap-x max-sm:pb-2">
            {SUGGESTIONS.map(s => (
              <button key={s[1]} className="tcard max-sm:min-w-[220px] max-sm:snap-start" onClick={() => submit(s[2])}>
                <span className="w-10 h-10 rounded-xl bg-orange-50 text-orange grid place-items-center flex-none"><Icon name={s[0]} size={20} /></span>
                <span>{s[1]}</span>
                <span className="ml-auto text-orange"><Icon name="chevr" size={18} /></span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="hero-glow relative flex-1 flex flex-col">
      <div className="relative z-[1] flex-1 flex flex-col max-w-[780px] w-full mx-auto px-5">
        <div className="flex-1 flex flex-col gap-[26px] pt-14 pb-6">
          {thread.map((m, i) => <Message key={i} m={m} i={i} last={i === thread.length - 1} update={update} retry={retry} submit={submit} />)}
          <div ref={threadEnd} />
        </div>
        <div className="sticky bottom-0 pt-2 pb-5 bg-gradient-to-b from-transparent to-canvas to-30%">
          {composer(true)}
          <p className="text-center text-muted text-xs mt-2.5">Company facts come only from approved knowledge; other answers are general AI help.</p>
        </div>
      </div>
    </div>
  );
}

function Waves() {
  return (
    <svg className="waves absolute inset-x-0 top-10 h-[380px] w-full pointer-events-none opacity-55" viewBox="0 0 1000 380" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 120C180 40 300 200 500 120S820 40 1000 130" /><path d="M0 170C200 90 320 250 520 170S840 90 1000 180" /><path d="M0 230C220 150 340 310 540 230S860 150 1000 240" />
    </svg>
  );
}

/* PRD §4.1 composer: + · Web Search · Company Knowledge on the left; microphone · send on the right. */
function Composer({ compact, busy, mode, setMode, target, setTarget, scope, setScope, onSend }: {
  compact: boolean; busy: boolean; mode: string; setMode: (m: string) => void; target: string; setTarget: (t: string) => void; scope: string | null; setScope: (s: string | null) => void; onSend: (q: string) => void;
}) {
  const app = useApp();
  const [text, setText] = useState(''); const [pop, setPop] = useState<'mode' | 'scope' | null>(null);
  const ta = useRef<HTMLTextAreaElement>(null); const box = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!compact) ta.current?.focus(); }, [compact]);
  useEffect(() => {
    const el = ta.current; if (!el) return;
    const sync = () => { setText(el.value); el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 200) + 'px'; };
    el.addEventListener('input', sync); return () => el.removeEventListener('input', sync);
  }, []);
  useEffect(() => {
    if (!pop) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setPop(null); };
    document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close);
  }, [pop]);
  const send = () => { if (!text.trim() || busy) return; onSend(text); setText(''); if (ta.current) { ta.current.value = ''; ta.current.style.height = 'auto'; } };

  return (
    <div className={`relative z-[2] w-full bg-white rounded-3xl border border-line px-4 pt-4 pb-3.5 ${compact ? 'shadow-card' : 'shadow-lift'}`}>
      <textarea id="q" ref={ta} rows={compact ? 1 : 2} aria-label="Your question"
        placeholder={mode === 'translate' ? `Write the text to translate into ${target}…` : 'Ask Quixotic AI about scripts, objections, SOPs, and company knowledge...'}
        className={`w-full border-0 outline-none resize-none bg-transparent px-2 py-1.5 text-base leading-normal placeholder:text-muted max-h-[200px] ${compact ? 'min-h-11' : 'min-h-14'}`}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
      <div ref={box} className="relative flex items-center gap-2.5 mt-1.5">
        <button className="circle-btn" aria-label="Answer mode" title="Answer mode" aria-expanded={pop === 'mode'} onClick={() => setPop(pop === 'mode' ? null : 'mode')}><Icon name="plus" size={20} /></button>
        {/* PRD §6 FR-CHAT-05: Web Search is governed in P1 (§14); until then it is shown but answers stay company-only. */}
        <button className="pill max-sm:px-3" title="Web Search" onClick={() => toast('Web Search is not enabled yet. Answers come only from approved company knowledge.')}>
          <Icon name="globe" size={17} /><span className="max-sm:hidden">Web Search</span>
        </button>
        <button className={`pill max-sm:px-3 ${scope ? 'on' : ''}`} aria-haspopup="listbox" aria-expanded={pop === 'scope'} onClick={() => setPop(pop === 'scope' ? null : 'scope')}>
          <Icon name="notes" size={17} /><span className="max-sm:hidden max-w-[180px] truncate">{scope || 'Company Knowledge'}</span><Icon name="chevd" size={15} />
        </button>
        {/* QAI-12: an X removes the selected mode at once (before, only a page refresh did) */}
        {mode === 'search' && <span className="chip orange gap-1">Search only
          <button className="ml-1 -mr-1 px-1 rounded-full hover:bg-white/60" aria-label="Cancel Search only" title="Cancel" onClick={() => setMode('general')}>✕</button></span>}
        {mode === 'translate' && <span className="chip orange gap-1">Translate to
          {/* owner 2026-10-24: any language - type it, or pick a suggestion */}
          <input className="bg-transparent font-semibold outline-none w-28 border-b border-current/30" aria-label="Translate to" list="qb-languages"
            value={target} onChange={e => setTarget(e.target.value)} onFocus={e => e.target.select()} placeholder="Any language" />
          <datalist id="qb-languages">{TARGETS.map(t => <option key={t} value={t} />)}</datalist>
          <button className="ml-1 -mr-1 px-1 rounded-full hover:bg-white/60" aria-label="Cancel translation mode" title="Cancel" onClick={() => setMode('general')}>✕</button></span>}
        <span className="flex-1" />
        {/* PRD §6 FR-CHAT-02: voice questions are P1 (§14). */}
        <button className="circle-btn" aria-label="Voice input" title="Voice input" onClick={() => toast('Voice questions are coming in a later release.')}><Icon name="mic" size={19} /></button>
        <button className="send-btn" aria-label="Send" disabled={!text.trim() || busy} onClick={send}><Icon name="send" size={20} /></button>

        {pop === 'mode' && (
          <div className="pop">
            <div className="ph">Mode</div>
            {(app.me.can_translate ? [...MODES, TRANSLATE_MODE] : MODES).map(m => (
              <button key={m[0]} className={mode === m[0] ? 'sel' : ''} onClick={() => { setMode(m[0]); setPop(null); }}>
                <span>{m[1]}<small>{m[2]}</small></span>{mode === m[0] && <Icon name="tick" size={16} className="ml-auto text-orange" />}
              </button>
            ))}
          </div>
        )}
        {pop === 'scope' && (
          /* PRD §6 FR-CHAT-06: only permitted scopes are listed; the server enforces the same rule. */
          <div className="pop" style={{ left: 104 }} role="listbox">
            <div className="ph">Search in</div>
            <button className={!scope ? 'sel' : ''} onClick={() => { setScope(null); setPop(null); }}>
              <span>Company Knowledge<small>Everything you are allowed to see</small></span>{!scope && <Icon name="tick" size={16} className="ml-auto text-orange" />}
            </button>
            {app.departments.map(d => (
              <button key={d.id} className={scope === d.name ? 'sel' : ''} onClick={() => { setScope(d.name); setPop(null); }}>
                <span>{d.name}</span>{scope === d.name && <Icon name="tick" size={16} className="ml-auto text-orange" />}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* Owner 2026-10-21 "2-3 messages, very easy": lines starting with ">> " are messages to send to the client. Each is its own bubble
   with a Copy button (one action per bubble, nothing to select by hand); everything else stays short plain text. */
function Inline({ text }: { text: string }) {
  /* **bold** like ChatGPT; everything else is plain text (no HTML is ever injected). */
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return <>{parts.map((p, k) => /^\*\*[^*]+\*\*$/.test(p) ? <strong key={k} className="font-semibold text-ink">{p.slice(2, -2)}</strong> : <span key={k}>{p}</span>)}</>;
}

/* Owner 2026-10-21 "like ChatGPT, bold headings, easy to copy, very simple": bold headings, real lists, and every message to send
   to the client (lines starting with ">> ") in its own bubble with a Copy button. */
function AnswerBody({ text, className = '' }: { text: string; className?: string }) {
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const L = list; list = null;
    out.push(L.ordered
      ? <ol key={out.length} className="list-decimal pl-5 space-y-1">{L.items.map((t, k) => <li key={k}><Inline text={t} /></li>)}</ol>
      : <ul key={out.length} className="list-disc pl-5 space-y-1">{L.items.map((t, k) => <li key={k}><Inline text={t} /></li>)}</ul>);
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    if (line.startsWith('>>')) {
      flush();
      const msg = line.replace(/^>>\s?/, '');
      out.push(
        <div key={out.length} className="flex items-start gap-2 rounded-2xl border border-line bg-white px-3.5 py-2.5 shadow-sm">
          <span className="flex-1 whitespace-pre-wrap">{msg}</span>
          <button className="btn ghost sm !px-2 shrink-0" title="Copy message" aria-label="Copy message"
            onClick={() => copyWithToast(msg.replace(/\*\*/g, ''))}><Icon name="copy" size={15} /></button>
        </div>);
      continue;
    }
    const ul = line.match(/^[-•]\s+(.*)$/), ol = line.match(/^\d+[.)]\s+(.*)$/);
    if (ul || ol) {
      const ordered = !!ol;
      if (!list || list.ordered !== ordered) { flush(); list = { ordered, items: [] }; }
      list.items.push((ul || ol)![1]);
      continue;
    }
    flush();
    const heading = /^\*\*[^*]+\*\*:?$/.test(line) || /^option\s*\d/i.test(line);
    out.push(heading
      ? <div key={out.length} className="font-semibold text-ink mt-1 -mb-1">{line.replace(/\*\*/g, '').replace(/:$/, '')}</div>
      : <p key={out.length}><Inline text={line} /></p>);
  }
  flush();
  return <div className={`answer flex flex-col gap-2 !whitespace-normal ${className}`}>{out}</div>;
}

/* Owner 2026-10-21 "very interactive": one tap refines the last answer in the same chat (the chat remembers the situation). */
const REFINE = ['Make it shorter', 'Make it friendlier', 'Make it more firm but still polite', 'Write the explanation in Roman Urdu'];
const REFINE_LABEL: Record<string, string> = { 'Make it shorter': 'Shorter', 'Make it friendlier': 'Friendlier',
  'Make it more firm but still polite': 'More firm (polite)', 'Write the explanation in Roman Urdu': 'In Roman Urdu' };

function SourceChip({ s, onClick }: { s: Source; onClick: () => void }) {
  return (
    <button className="src" onClick={onClick}>
      <Icon name="doc" size={15} />{s.title}{s.section && <small>· {s.section}</small>}<small>· v{s.version}</small>
    </button>
  );
}

/* PRD §6 FR-CHAT-07 cited-source drawer: title, section, version and updated date (FR-CHAT-04). */
function openSources(sources: Source[]) {
  openDrawer(close => (
    <div>
      <div className="flex items-center"><h2 className="text-xl font-extrabold">Sources</h2><span className="flex-1" />
        <button className="btn ghost sm" onClick={close} aria-label="Close"><Icon name="x" size={18} /></button></div>
      <p className="hint mt-1 mb-4">Approved company documents this answer was written from.</p>
      <div className="grid gap-3">
        {sources.map((s, k) => (
          <div key={k} className="card !p-4 shadow-none">
            <div className="flex items-center gap-2 font-bold"><span className="chip orange">{k + 1}</span>{s.title}</div>
            <dl className="kv mt-2.5 text-[13.5px]">
              <dt>Section</dt><dd>{s.section || '—'}</dd><dt>Version</dt><dd>v{s.version}</dd><dt>Effective</dt><dd>{s.updated ? new Date(s.updated).toLocaleDateString() : '—'}</dd>
            </dl>
          </div>
        ))}
      </div>
    </div>
  ));
}

function Message({ m, i, last = false, update, retry, submit }: { m: Msg; i: number; last?: boolean; update: (i: number, p: any) => void; retry: (i: number, q: string) => void; submit: (q: string, mode?: string) => void }) {
  const app = useApp();
  if (m.role === 'user') return <div className="msg-u">{m.text}</div>;
  const av = <span className="w-[30px] h-[30px] mt-0.5 rounded-full bg-orange text-white grid place-items-center flex-none"><svg viewBox="0 0 24 24" width="16" height="16" fill="#fff"><path d="M12 3l2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2z" /></svg></span>;
  const wrap = (body: React.ReactNode) => <div className="flex gap-3 items-start">{av}<div className="flex-1 min-w-0">{body}</div></div>;
  if ('loading' in m) return wrap(<div className="typing" aria-label="Writing an answer"><i /><i /><i /></div>);
  if ('error' in m) return wrap(<>
    <Banner kind="err">{m.error}</Banner>
    <button className="btn sm mt-2.5" onClick={() => retry(i, m.question)}><Icon name="refresh" size={15} /> Retry</button>
  </>);
  if (m.kind === 'translate') return wrap(<>
    <div className="label mb-2">{m.target || 'English'} translation</div>
    <div className="card !p-4 shadow-none whitespace-pre-wrap">{m.english}</div>
    <div className="flex items-center gap-2 mt-2.5">
      <button className="btn sm" onClick={() => copyWithToast(m.english)}><Icon name="copy" size={15} /> Copy</button>
      <small className="text-muted">Check names, prices and dates before sending.</small>
    </div>
  </>);
  if (m.kind === 'search') return wrap(m.results.length ? (<>
    <div className="label mb-2">Best match</div><Hit r={m.results[0]} k={0} />
    {m.results.length > 1 && <details className="more mt-2.5"><summary>Show {m.results.length - 1} more match{m.results.length > 2 ? 'es' : ''}</summary>
      <div className="flex flex-col gap-2.5 mt-2">{m.results.slice(1).map((r, k) => <Hit key={k} r={r} k={k + 1} />)}</div></details>}
  </>) : <div className="notice"><b>Nothing found.</b> No approved knowledge matches this search.</div>);

  const gap = m.found === false;                                   // offer Report missing information
  const low = m.confidence !== 'general' && (m.confidence === 'low' || gap);
  const [cl, cc] = CONF[m.confidence || 'low'] || CONF.low;
  const [first, ...rest] = m.answer.split('\n');
  const feedback = async (helpful: boolean) => {
    try { await api('/v1/feedback', { method: 'POST', body: { query_id: m.query_id, helpful } }); update(i, { helpful }); toast(helpful ? 'Thanks! I’ll remember what worked.' : 'Thanks — I’ll avoid this next time.'); }
    catch (e) { toast((e as Error).message); }
  };
  const reason = async (r: string) => {
    if ((m.reasons || []).includes(r)) return;
    try { await api('/v1/feedback', { method: 'POST', body: { query_id: m.query_id, note: r } }); update(i, { reasons: [...(m.reasons || []), r] }); toast('Noted: ' + r.toLowerCase()); }
    catch (e) { toast((e as Error).message); }
  };
  /* PRD §6 FR-CHAT-04 "Offer Report missing information": the question becomes a de-duplicated gap for its department's owners (§9).
     People who can add knowledge may also answer it straight away. */
  const report = () => openModal('Report missing information', close => <ReportGap m={m} canAdd={can(app.me, 'propose_knowledge')} close={close} />);
  return wrap(<>
    {low ? <div className="notice"><b>{first}</b>{rest.length > 0 && <AnswerBody text={rest.join('\n').trim()} className="mt-1.5" />}</div>
      : <AnswerBody text={m.answer} />}
    <div className="flex flex-wrap gap-2 items-center mt-3"><span className={`chip dot ${cc}`}>{cl}</span></div>
    {m.sources.length > 0 && (
      <div className="flex flex-wrap gap-2 mt-3">
        {m.sources.slice(0, 2).map((s, k) => <SourceChip key={k} s={s} onClick={() => openSources(m.sources)} />)}
        {m.sources.length > 2 && <button className="src !bg-canvas !text-ink-2 border border-line" onClick={() => openSources(m.sources)}>+{m.sources.length - 2} more</button>}
      </div>
    )}
    {gap ? (
      <div className="flex flex-wrap gap-2 mt-3.5">
        <button className="btn sm" onClick={report}><Icon name="plus" size={15} /> Report missing information</button>
        <button className="btn sm" onClick={() => submit(m.question, 'search')}><Icon name="search" size={15} /> Search documents</button>
      </div>
    ) : (<>
      <div className="flex items-center gap-1 mt-3.5 text-muted">
        <button className="btn ghost sm !px-2" title="Copy" aria-label="Copy answer" onClick={() => copyWithToast(m.answer.replace(/^>>\s?/gm, '').replace(/\*\*/g, ''))}><Icon name="copy" size={15} /></button>
        <button className={`btn ghost sm !px-2 ${m.helpful === true ? '!text-good' : ''}`} title="Helpful" aria-label="Helpful" aria-pressed={m.helpful === true} onClick={() => feedback(true)}><Icon name="up" size={15} /></button>
        <button className={`btn ghost sm !px-2 ${m.helpful === false ? '!text-bad' : ''}`} title="Not helpful" aria-label="Not helpful" aria-pressed={m.helpful === false} onClick={() => feedback(false)}><Icon name="down" size={15} /></button>
      </div>
      {last && (/quick questions|^\s*1[.)]/im.test(m.answer)
        ? <div className="flex flex-wrap gap-1.5 mt-2.5"><span className="hint w-full">Reply with the details, or:</span>
            <button className="chipbtn" onClick={() => submit('Skip the questions and just give me 3 options with your best assumptions.')}>Skip, just give me options</button></div>
        : <div className="flex flex-wrap gap-1.5 mt-2.5">{REFINE.map(r => <button key={r} className="chipbtn" onClick={() => submit(r)}>{REFINE_LABEL[r]}</button>)}</div>)}
      {m.helpful === false && (
        <div className="mt-2.5"><span className="hint">What was wrong? <span className="opacity-80">(optional — it helps me learn)</span></span>
          <div className="flex flex-wrap gap-1.5 mt-1.5">{REASONS.map(r => <button key={r} className={`chipbtn ${(m.reasons || []).includes(r) ? 'on' : ''}`} onClick={() => reason(r)}>{r}</button>)}</div>
        </div>
      )}
    </>)}
  </>);
}

function Hit({ r, k }: { r: { source: string; text: string }; k: number }) {
  return (
    <div className="border border-line rounded-[14px] px-3.5 py-3 bg-white">
      <div className="font-bold text-[13.5px] mb-1 flex gap-2 items-center"><span className="chip orange">{k + 1}</span>{r.source}</div>
      <div className="text-ink-2 text-sm">{r.text}</div>
    </div>
  );
}


function ReportGap({ m, canAdd, close }: { m: { question: string; query_id?: string; gap_id?: string }; canAdd: boolean; close: () => void }) {
  const [comment, setComment] = useState(''); const a = useAction();
  const send = () => a.run(async () => {
    await api('/v1/knowledge-gaps/report', { method: 'POST', body: { query_id: m.query_id, comment: comment.trim() || null } });
    close(); toast('Reported. The people who keep this knowledge up to date will see it.');
  });
  return (<>
    <p className="text-ink-2 mb-3">The knowledge owners for your department will see this question: <b>“{m.question}”</b></p>
    <div className="field mb-4"><label htmlFor="rg-c">Anything that would help? <span className="hint">(optional)</span></label>
      <textarea id="rg-c" className="textarea min-h-[90px]" maxLength={1000} value={comment} onChange={e => setComment(e.target.value)} placeholder="e.g. Customers ask this every day" /></div>
    {a.error && <Banner kind="err" className="mb-3">{a.error}</Banner>}
    <div className="flex flex-wrap justify-end gap-3">
      {canAdd && <button className="btn" onClick={() => { session.set('qb_prefill', JSON.stringify({ title: m.question, gap_id: m.gap_id })); close(); go('add'); }}>Add this information myself</button>}
      <button className="btn" onClick={close}>Cancel</button><button className="btn primary" disabled={a.busy || !m.query_id} onClick={send}>Report</button></div>
  </>);
}
