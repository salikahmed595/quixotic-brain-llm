// Panel warnings (owner master prompt 2026-10-30, "Warnings"): worked out in code from the visible chat, the
// Mini Brain and the draft, so they never depend on the AI noticing. They inform the employee; nothing is blocked.
const FINANCIAL=/\bcan'?t afford\b|\bdon'?t have (?:any |the )?(?:money|cash|funds)\b|\bno money\b|\bbroke\b|\bspent (?:too much|a lot)\b|\bmore money (?:into|than)\b|\btight on (?:money|cash)\b|\bbudget is tight\b/i;
const REFUSAL=/\bnot interested\b|\bno thanks\b|\b(?:pls|please) stop\b|\bstop asking\b|\bdon'?t want (?:it|to buy|any)\b|\bleave me alone\b/i;
const MONEY=/\$\s?\d+(?:\.\d+)?|\b\d+\s?(?:usd|dollars?|bucks)\b|\b\d+\s?%\s?off\b/gi;
const TERMS=/\b(discount|deposit|instal+ments?|payment plan)\b/gi;
const PAYMENT=/\b(?:got|received) (?:your|the) payment\b|\bpayment (?:is|was|has been) (?:received|confirmed|verified)\b|\byou(?:'ve| have) (?:already )?paid\b/i;
const DEADLINE=/\b(?:ready|done|deliver\w*|finish\w*|send (?:it|you))\b.{0,40}\b(?:by (?:mon|tues|wednes|thurs|fri|satur|sun)day|tomorrow|tonight|today|within \d+ (?:hours?|days?)|in \d+ (?:hours?|days?))\b/i;
const STOP=new Set(['btw','haha','ohh','yo','bro','so','like','the','a','an','and','or','do','you','u','ur','your','is','are','what','which','how','any','some','^^','xd']);

const words=s=>String(s).toLowerCase().replace(/[^\p{L}\p{N}\s]/gu,' ').split(/\s+/).filter(w=>w&&!STOP.has(w));
const questions=s=>String(s).split(/(?<=\?)/).filter(q=>q.includes('?')).map(words).filter(w=>w.length);
const similar=(a,b)=>{const A=new Set(a),B=new Set(b),both=[...A].filter(x=>B.has(x)).length;return both/Math.max(new Set([...A,...B]).size,1)>=0.6;};
const norm=s=>s.toLowerCase().replace(/\s+/g,'');

const customerText=messages=>messages.filter(m=>!m.isBot&&!m.isStaff).map(m=>String(m.content||'')).join('\n');
const staffTexts=messages=>messages.filter(m=>m.isStaff).map(m=>String(m.content||''));

// Money amounts and payment terms in the draft that appear nowhere in the chat or the Mini Brain (also used by verify.js).
export function unsupportedTerms({messages,draft,facts=[]}){
  const known=norm(customerText(messages)+'\n'+staffTexts(messages).join('\n')+'\n'+facts.map(f=>`${f.statement} ${f.value||''}`).join('\n'));
  return [...[...String(draft).matchAll(MONEY)],...[...String(draft).matchAll(TERMS)]].map(m=>m[0]).filter(t=>!known.includes(norm(t)));
}
export function repeatsQuestion({messages,draft}){
  const asked=staffTexts(messages).flatMap(questions);
  return questions(draft).some(q=>asked.some(a=>similar(q,a)));
}

export function warningsFor({messages,draft,facts=[]}){
  const customer=customerText(messages);
  const out=[];
  if(FINANCIAL.test(customer)) out.push({kind:'financial',text:'Money concern: reassure, no pressure, no payment talk.'});
  if(REFUSAL.test(customer)) out.push({kind:'refusal',text:'They said no: respect it and stop pitching.'});
  const terms=unsupportedTerms({messages,draft,facts});
  if(terms.length) out.push({kind:'price',text:`Check with the owner before sending: ${terms.join(', ')} is not in the chat or Mini Brain.`});
  if(PAYMENT.test(draft)) out.push({kind:'payment',text:'Says payment arrived: only send if the payment is verified.'});
  if(DEADLINE.test(draft)) out.push({kind:'deadline',text:'Promises a time: only send if the owner confirmed it.'});
  if(repeatsQuestion({messages,draft})) out.push({kind:'repeat',text:'This question was already asked in the chat.'});
  return out;
}
