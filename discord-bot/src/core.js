/** Dependency-free, testable domain logic. No Discord SDK calls in this module. */
const STOP = new Set(['the','and','for','with','that','this','you','your','i','me','my','our','are','can','we','bro','hey','yo','have','was','were','from','want','need','will','would','could','its','just','like','some','there','they','them','here','what','when','how','do','to','a','an','is','it','of','in','on','at','as','be','or','so','but','if','get','got','im','ive','dont','please','about']);
export function words(s='') {
  return [...new Set((String(s).toLowerCase().match(/[\p{L}\p{N}]+/gu)||[]).filter(w => w.length > 2 && !STOP.has(w)))];
}
export function scoreOverlap(query, key) {
  const a = words(query), b = new Set(words(key));
  if (!a.length || !b.size) return 0;
  const overlap = a.filter(w => b.has(w)).length;
  // Intent phrases win ties; recency added by caller.
  return overlap / Math.sqrt(a.length * b.size);
}
export function retrieveKV(query, pairs, count=4) {
  return pairs.map((p,i)=>({...p, score:scoreOverlap(query,p.key), _index:i}))
    .filter(p=>p.score>0 && p.value && p.key)
    .sort((a,b)=>b.score-a.score || b._index-a._index)
    .slice(0,count).map(({_index,...p})=>p);
}
export function recentContext(messages, targetId, count=45) {
  const limited = targetId ? messages.filter(m=>BigInt(m.id)<=BigInt(targetId)) : messages;
  return limited.slice(-count);
}
export function pickRelevantOldMessages(query, messages, count=10, recentCount=45) {
  return messages.slice(0,Math.max(0,messages.length-recentCount))
    .map(m=>({...m, _score:scoreOverlap(query,m.content)}))
    .filter(m=>m._score>0)
    .sort((a,b)=>b._score-a._score)
    .slice(0,count).sort((a,b)=>Number(BigInt(a.id)>BigInt(b.id))-Number(BigInt(a.id)<BigInt(b.id)))
    .map(({_score,...m})=>m);
}
export function makeSameChatPairs(messages, customerId, count=300) {
  const pairs=[];
  for(let i=0;i<messages.length-1;i++) {
    const m=messages[i], n=messages[i+1];
    if (m.authorId===customerId && n.authorId!==customerId && !n.isBot && m.content && n.content) {
      pairs.push({key:m.content.slice(0,650),value:n.content.slice(0,650),sourceMessageId:m.id,reviewStatus:'UNREVIEWED_EXAMPLE'});
    }
  }
  return pairs.slice(-count);
}
const slang= /\b(bro|bruh|fr|ngl|lol|lmao|hru|wtf|rn|wanna|gonna|idk|yo)\b/i;
export function inferStyle(customerMessages) {
  const samples=customerMessages.filter(m=>String(m.content||'').trim()).slice(-20);
  if (!samples.length) return {language:'unknown',tone:'neutral',length:'short',reason:'No customer messages available'};
  const joined=samples.map(m=>m.content).join(' ');
  const avg = samples.reduce((n,m)=>n+m.content.length,0)/samples.length;
  const romanUrdu=/\b(kya|hai|nahi|karna|chahiye|bhai|scene|bhej|mujhe|apka|tumhara|kitna|acha|theek)\b/i.test(joined);
  return {language:romanUrdu?'Roman Urdu / mixed':'English / unknown',tone:slang.test(joined)?'casual/slang':'neutral/friendly',length:avg>180?'medium':'short',reason:`Inferred from ${samples.length} recent customer messages; observation only`};
}
export function extractExplicitFacts(customerMessage) {
  const text=String(customerMessage||''); const out=[];
  // Candidate observations only. Order-specific budget must not be interpreted as income or lifetime spending.
  const budget=text.match(/(?:\b(?:budget|only have|only got|can spend|got|have|spend|afford|under|around|max)\b[^\n.!?]{0,38}?)\s*\$\s*(\d{1,6})/i) || text.match(/\$\s*(\d{1,6})[^\n.!?]{0,45}\b(?:budget|banner|emote|overlay|avatar|character)\b/i);
  if(budget) out.push({key:'stated_budget_usd',value:String(Number(budget[1])),status:'observed',scope:'this conversation/order',evidence:budget[0].slice(0,150)});
  const styles=['cyberpunk','anime','fantasy','neon','minimalist','furry','retro','gothic','cartoon'];
  for(const style of styles) if(new RegExp(`\\b${style}\\b`,'i').test(text) && /\b(like|love|prefer|want|looking for|thinking|need|into)\b/i.test(text)) {
    out.push({key:`art_style_${style}`,value:style,status:'observed',scope:'this conversation',evidence:text.slice(0,180)});
  }
  for(const game of ['valorant','fortnite','minecraft','league of legends','gta','apex legends']) if(text.toLowerCase().includes(game)) {
    out.push({key:`game_mentioned_${game.replaceAll(' ','_')}`,value:game,status:'observed',scope:'this conversation',evidence:text.slice(0,180)});
  }
  return out;
}
const promise=/(\b(?:guarantee|guaranteed|promise|definitely|100%)\b.{0,65}\b(?:deliver|delivery|ready|finish|refund|discount|ship|complete)\b|\b(?:deliver|delivery|ready|finish|completed|refund)\b.{0,50}\b(?:tomorrow|tonight|today|within\s+\d+\s+(?:hours|days)|by\s+\w+day)\b)/i;
const negative=/\b(?:cannot|can't|won't|not|need to check|before i promise|confirm first|let me check|can't guarantee)\b/i;
export function validateDraft(draft) {
  if(typeof draft!=='string'||!draft.trim()) return {ok:false,reason:'Draft empty'};
  if(draft.length>1800) return {ok:false,reason:'Draft too long for review'};
  if(promise.test(draft) && !negative.test(draft)) return {ok:false,reason:'Possible unsupported guarantee or deadline; requires verified CRM approval'};
  if(/\b(?:payment (?:is|was) (?:confirmed|received)|your payment went through|already paid)\b/i.test(draft) && !negative.test(draft)) return {ok:false,reason:'Unverified payment-status claim'};
  return {ok:true,reason:''};
}
export function formatForPrompt(messages, max=90) {
  return messages.slice(-max).map(m=>`[${m.createdAt}] [${m.authorId}] ${String(m.content).replace(/\s+/g,' ').slice(0,900)}`).join('\n');
}
