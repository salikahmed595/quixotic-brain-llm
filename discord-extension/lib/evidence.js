// Evidence for the employee (owner prompt pack 2026-11-03, §20/§21 exact_relevant_evidence_ids): the latest customer
// message, plus up to 3 earlier customer messages that share a content word with the reply. Worked out in code.
const STOP=new Set(['the','and','you','your','are','for','but','not','lol','got','its','that','this','with','have','was','what',
  'can','just','like','yeah','haha','also','mine','some','any','how','too','out','all','get','one','yes','sure','okay','about','would','could']);
const words=s=>new Set(String(s).toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(w=>w.length>=3&&!STOP.has(w)).map(w=>w.replace(/s$/,'')));
const isCustomer=m=>!m.isBot&&!m.isStaff&&String(m.content||'').trim();

export function evidenceFor(chat,target,draft){
  const used=words(draft);
  const before=chat.slice(0,chat.findIndex(m=>m.id===target.id));
  const earlier=before.filter(m=>isCustomer(m)&&[...words(m.content)].some(w=>used.has(w)));
  return [...earlier.slice(-3).map(m=>m.id),target.id];
}
