// Visible chat -> labelled conversation -> Quixotic AI -> guarded private draft. Never sends anything to the chat app.
import {parseStaffNames,labelMessages} from './labels.js';
import {buildConversationQuestion} from './conversation.js';
import {validateDraft} from './guard.js';
import {gateFor} from './gate.js';
import {stageOf} from './stage.js';
import {evidenceFor} from './evidence.js';
import {parseOptions} from './options.js';
import {verifyReply} from './verify.js';

const THREE_WAY=new Set(['reply','answer_only']);
const ALT_LABELS=['Short','Warm'];

// Models sometimes wrap the reply as a quote or label it; employees should get text they can paste as is.
export function cleanDraft(text){
  let t=String(text||'').trim().replace(/^(?:>+\s*)+/,'').replace(/^staff:\s*/i,'').trim();
  if(/^["“].*["”]$/s.test(t)) t=t.slice(1,-1).trim();
  return t.replace(/\s*[—–]\s*/g,', ').replace(/,\s*,/g,',');
}

const isCustomer=m=>!m.isBot&&!m.isStaff&&String(m.content||'').trim();

export async function draftFromChat({messages,staffNames,ask,goal,tone,app,clientFacts=[],style='',previous='',answerOnly=false,role=null}){
  const names=parseStaffNames(staffNames);
  if(!names.size) return {ok:false,text:'Add the staff names (as shown in the chat) first, so I know who is the customer.'};
  const chat=labelMessages(messages,names);
  const target=chat.filter(isCustomer).at(-1);
  if(!target) return {ok:false,text:'No customer message in view. Scroll to the chat and try again.'};
  const messagesRead=chat.filter(m=>!m.isBot&&String(m.content||'').trim()).length;
  const base={messagesRead,latest:target,chat,stage:stageOf(chat)};
  // Prompt pack §7/§17: opt-outs and payment requests are decided in code before the AI is asked anything.
  const gate=gateFor(chat);
  if(gate.status==='NO_REPLY'&&!answerOnly)
    return {...base,ok:false,status:'NO_REPLY',draft:null,evidence:gate.evidence,text:`No sales reply: the customer opted out. ${gate.reason}`};
  if(gate.status==='HUMAN_HANDOFF')
    return {...base,ok:true,status:'HUMAN_HANDOFF',kind:gate.kind,draft:gate.reply,text:gate.reply,evidence:gate.evidence,reason:gate.reason};
  const g=answerOnly?'answer_only':goal||'reply';
  const opts={goal:g,tone,app,clientFacts,style,previous,stage:base.stage.stage,role};
  const clean=t=>cleanDraft(t).replace(/@everyone|@here/g,'[mention removed]');
  const split=answer=>THREE_WAY.has(g)?parseOptions(answer).map(clean):[clean(answer)];
  // Prompt pack §19: checked in code; ideas are a staff-only list, not a chat message, so they are not checked.
  const verify=t=>g==='ideas'?{verdict:'PASS',violations:[]}:verifyReply(t,{chat,stage:base.stage.stage,facts:clientFacts,noSales:answerOnly,role});
  let res=await ask(buildConversationQuestion(chat,target.id,opts));
  let [draft,...rest]=split(res.answer);
  if(!validateDraft(draft).ok) return {ok:false,text:`Draft blocked for review: ${validateDraft(draft).reason}`};
  let check=verify(draft),revised=false;
  if(check.verdict!=='PASS'){
    // One rewrite that names what failed (§26 orchestrator); if it fails again the employee writes it themselves.
    res=await ask(buildConversationQuestion(chat,target.id,{...opts,fix:check.violations.map(v=>v.text)}));
    [draft,...rest]=split(res.answer);revised=true;
    if(!validateDraft(draft).ok) return {ok:false,text:`Draft blocked for review: ${validateDraft(draft).reason}`};
    check=verify(draft);
    if(check.verdict!=='PASS') return {...base,ok:false,status:'NEED_CONTEXT',draft:null,
      text:`No suggestion passed the checks (${check.violations.map(v=>v.text).join(' ')}) Please write it yourself.`};
  }
  // Prompt pack §12/§21: Short and Warm alternatives; one that fails the guard or the checker is dropped, never shown.
  const alternatives=rest.slice(0,2).map((text,i)=>({label:ALT_LABELS[i],text}))
    .filter(a=>a.text&&validateDraft(a.text).ok&&verify(a.text).verdict==='PASS');
  return {...base,ok:true,status:'SUGGEST',draft,alternatives,evidence:evidenceFor(chat,target,draft),
    check:{verdict:'PASS',revised},confidence:res.confidence,text:draft};
}
