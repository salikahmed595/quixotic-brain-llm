// Reply checker (owner prompt pack 2026-11-03, §19 Prompt N, §24 "enforced in code"): every suggestion is checked in
// code before the employee sees it. A failing recommended reply is rewritten once by draft.js; a failing alternative is dropped.
import {unsupportedTerms,repeatsQuestion} from './warnings.js';

const CLICHE=/\bi totally understand\b|\bthat'?s amazing\b|\bgame[- ]changer\b|\belevate your\b|\bthanks for reaching out\b|\bhope this (?:message )?finds you\b|\bdon'?t hesitate\b|\bi'?d be (?:happy|delighted) to\b|\bnext level\b/i;
const LINK=/https?:\/\/|\bwww\.|\bdiscord\.gg\/|\b[\w-]+\.(?:com|net|org|gg|io|me|art|link|ly)\b/i;
const FAKE=/\bi (?:saw|watched|caught) (?:your|ur) stream|\bbeen watching (?:you|u|ur|your)\b|\bi main\b|\b(?:i'?m|im|i am) (?:a )?(?:big |huge )?fan\b|\b(?:i'?m|im|i am) (?:subbed|subscribed)\b|\bi follow (?:you|u)\b/i;
const ART=/\bcommissions?\b|\bemotes?\b|\bbanners?\b|\boverlays?\b|\bartwork\b|\b(?:our|my) (?:art|work|projects?|portfolio)\b|\bcustom (?:art|emotes?|designs?)\b|\billustrations?\b|\blogos?\b|\bvtuber model\b/i;
const LONG_OK=new Set(['SCOPING','OBJECTION','SUPPORT','READY']);   // owner: explain properly for prices, concerns, terms
const NO_PITCH=new Set(['DISCOVERY','RAPPORT']);
const THEIRS=/\b(?:your|ur) budget\b|\byou (?:mentioned|said)\b|\bbudget of\b/i;
const SECRET=/\bpasswords?\b|\bapi[- ]?keys?\b|\btokens?\b|\bdatabase\b|\bsystem prompt\b|\binternal (?:notes?|prompts?|instructions)\b/i;
const OWN_ARTIST=/\b(?:my|a) (?:friend|artist|bf|gf|sister|brother|cousin|partner)\b[^.?!]{0,30}\b(?:makes?|draws?|did|does|made)\b|\bi (?:already )?have an artist\b/i;
const PUT_DOWN=/\bbetter than\b|\bcheaper than\b|\binstead of\b|\breplace\b/i;
const OFFER=/\bwe (?:can|could) (?:make|do|draw)\b|\bi (?:can|could) (?:make|draw)\b|\bquote\b|\bwanna see\b|\bcommission\b/i;
const BUDGET_OK=new Set(['SCOPING','INTEREST','OBJECTION','READY']);
const UPSELL=/\b(?:also|btw|another|more|add(?:-on)?|upgrade|new) (?:\w+ )?(?:emotes?|banners?|overlays?|art|commissions?|pack|set|designs?)\b|\bdiscount\b|\bwanna see\b|\bportfolio\b|\bour (?:other|new) \w+/i;

const text=m=>String(m?.content||'');
// A real question has at least 3 words before its "?"; "Ohh nice??" is a reaction, not a question.
const questionCount=s=>(String(s).match(/[^?.!]*\?+/g)||[]).filter(q=>q.trim().split(/\s+/).length>=3).length;

export function verifyReply(draft,{chat=[],stage=null,facts=[],noSales=false,role=null}={}){
  const d=String(draft||''),v=[];
  const add=(check,why)=>v.push({check,text:why});
  if(CLICHE.test(d)||(d.match(/!/g)||[]).length>2) add('tone','Sounds like an AI script (stock phrase or too many "!").');
  if(LINK.test(d)) add('link','Contains a link; only the team shares real links.');
  if(FAKE.test(d)) add('honesty','Claims to watch, follow, be a fan or play their game; only say that if it is true.');
  if(questionCount(d)>1) add('questions','Asks more than one question.');
  const words=d.trim().split(/\s+/).filter(Boolean).length;
  if(words>(LONG_OK.has(stage)?110:65)) add('length',`Too long (${words} words).`);
  const terms=unsupportedTerms({messages:chat,draft:d,facts});
  if(terms.length) add('grounding',`Mentions ${terms.join(', ')}, which is not in the chat or Mini Brain.`);
  // Scenario 7: an amount only the customer typed is not our approved price; it may be repeated only as their budget.
  const customerOnly=unsupportedTerms({messages:chat.filter(m=>m.isStaff),draft:d,facts}).filter(t=>/\d/.test(t)&&!terms.includes(t));
  if(customerOnly.length&&!THEIRS.test(d)) add('grounding',`States ${customerOnly.join(', ')} as our price, but only the customer said it.`);
  if(SECRET.test(d)) add('secret','Mentions passwords, keys, tokens, databases or internal prompts.');
  if(repeatsQuestion({messages:chat,draft:d})) add('repeat','Repeats a question already asked in the chat.');
  const customerRaisedArt=chat.some(m=>!m.isBot&&!m.isStaff&&ART.test(text(m)));
  if(noSales&&ART.test(d)) add('pitch','Mentions art in a no-sales reply.');
  else if(NO_PITCH.has(stage)&&!customerRaisedArt&&ART.test(d)) add('pitch','Brings up art before the customer did.');
  // Seller role (pack §14 Fresh seller, §10/§15 support before any sale).
  if((role==='support'||stage==='SUPPORT')&&UPSELL.test(d)) add('upsell','Sells something during a support chat; fix their issue first.');
  // Scenario 16: respect an existing artist; no put-downs and no replacement pitch.
  if(chat.some(m=>!m.isBot&&!m.isStaff&&OWN_ARTIST.test(text(m)))&&(PUT_DOWN.test(d)||OFFER.test(d)))
    add('respect','Pitches against the artist they already have.');
  const customerMentionedBudget=chat.some(m=>!m.isBot&&!m.isStaff&&/\bbudget\b|\$\s?\d|\bhow much\b|\bprice\b/i.test(text(m)));
  if(role==='fresh'&&!BUDGET_OK.has(stage)&&!customerMentionedBudget&&/\bbudget\b[^.!]*\?/i.test(d)) add('budget','Asks for a budget before there is a project to price.');
  return {verdict:v.length?'REVISE':'PASS',violations:v};
}
