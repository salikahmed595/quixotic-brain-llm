// Conversation stage + intent (owner prompt pack 2026-11-03, §3 STAGES, §8 Prompt C), worked out in code from the
// latest customer message so the employee sees it and the AI gets it as a hint. Readiness and opt-outs reuse the gate.
import {gateFor} from './gate.js';

export const STAGES={
  DISCOVERY:{label:'Discovery',next:'Chat about what they said; no sales pitch.'},
  RAPPORT:{label:'Rapport',next:'Be genuine and keep it natural; only bring up art if they do.'},
  NEEDS:{label:'Needs',next:'Ask one relevant question about what they need.'},
  INTEREST:{label:'Interest',next:'Answer, offer a real example if one is approved, and suggest one next step.'},
  SCOPING:{label:'Scoping',next:'Ask the next single missing detail; no price unless the team approved one.'},
  OBJECTION:{label:'Objection',next:'Answer the actual concern honestly, with no pressure.'},
  READY:{label:'Ready',next:'Hand off to the team for the official quote and payment instructions.'},
  SUPPORT:{label:'Support',next:'Fix their issue first; do not sell anything.'},
  CLOSED:{label:'Closed',next:'Respect their no: send nothing salesy and no follow-up.'}
};
export const INTENTS={casual_chat:'Casual chat',gaming_question:'Gaming question',art_need:'Described an art need',
  art_question:'Art question',asks_examples:'Wants examples',quote_request:'Asked about price',deadline_question:'Asked about timing',
  price_objection:'Price concern',trust_objection:'Trust concern',wants_payment_link:'Wants to pay',customer_declines:'Said no',
  needs_support:'Needs help with an order'};

// First match wins; support comes before any sales intent (§10: no cross-sell before the support issue is solved).
const RULES=[
  ['SUPPORT','needs_support',/\bstill waiting\b|\bwhere is my\b|\blate\b|\bdelay(?:ed)?\b|\brefund\b|\bnot received\b|\bhaven'?t (?:got|received)\b|\bwrong (?:file|size|colou?r)\b|\bit'?s been \d+ (?:days?|weeks?)\b/i],
  ['OBJECTION','price_objection',/\bmore than i (?:planned|thought|expected)\b|\btoo (?:expensive|much|pricey)\b|\bcan'?t afford\b|\b(?:out of|over) (?:my )?budget\b|\bcheaper\b/i],
  ['OBJECTION','trust_objection',/\bai art\b|\bjust ai\b|\bis (?:this|it) ai\b|\bscam\b|\blegit\b|\bcan i trust\b|\bhuman artist\b/i],
  ['SCOPING','deadline_question',/\bhow long\b|\bturnaround\b|\bdeadline\b|\bwhen (?:can|will|would) (?:it|you|u)\b/i],
  ['SCOPING','quote_request',/\bhow much\b|\bprices?\b|\bcost\b|\bquote\b|\brates?\b/i],
  ['INTEREST','asks_examples',/\bexamples?\b|\bportfolio\b|\bsamples?\b|\byour work\b|\bshow me\b|\bwanna see\b/i],
  ['INTEREST','art_question',/\bcan (?:you|u) (?:make|draw|do)\b|\bcommissions?\b|\bemotes?\b|\bbanners?\b|\boverlays?\b.*\?|\blogo\b.*\?/i],
  ['NEEDS','art_need',/\blooks? (?:generic|bad|old|boring)\b|\b(?:don'?t|doesn'?t) match\b|\bneed (?:a |new |some |an )|\blooking for\b|\bwant (?:a |new |some |an )|\bredo\b|\bupgrade\b|\bupdate my\b/i],
  ['RAPPORT','gaming_question',/\b(?:play(?:ed|ing)?|game|stream(?:ing)?|ranked)\b[^?]*\?/i]
];

const text=m=>String(m?.content||'');
const isCustomer=m=>!m.isBot&&!m.isStaff&&text(m).trim();

export function stageOf(chat){
  const latest=chat.filter(isCustomer).at(-1);
  const pack=(stage,intent,evidence=latest?[latest.id]:[])=>({stage,intent,evidence,next:STAGES[stage].next});
  const gate=gateFor(chat);
  if(gate.status==='NO_REPLY') return pack('CLOSED','customer_declines',gate.evidence);
  if(gate.status==='HUMAN_HANDOFF') return pack('READY','wants_payment_link',gate.evidence);
  const hit=RULES.find(([,,re])=>re.test(text(latest)));
  if(hit) return pack(hit[0],hit[1]);
  return pack(chat.some(m=>m.isStaff)?'RAPPORT':'DISCOVERY','casual_chat');
}
