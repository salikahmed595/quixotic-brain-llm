// Visible chat -> labelled conversation -> Quixotic AI -> guarded private draft. Never sends anything to the chat app.
import {parseStaffNames,labelMessages} from './labels.js';
import {buildConversationQuestion} from './conversation.js';
import {validateDraft} from './guard.js';
import {gateFor} from './gate.js';
import {stageOf} from './stage.js';
import {evidenceFor} from './evidence.js';
import {parseOptions} from './options.js';

const THREE_WAY=new Set(['reply','answer_only']);
const ALT_LABELS=['Short','Warm'];

// Models sometimes wrap the reply as a quote or label it; employees should get text they can paste as is.
export function cleanDraft(text){
  let t=String(text||'').trim().replace(/^(?:>+\s*)+/,'').replace(/^staff:\s*/i,'').trim();
  if(/^["“].*["”]$/s.test(t)) t=t.slice(1,-1).trim();
  return t.replace(/\s*[—–]\s*/g,', ').replace(/,\s*,/g,',');
}

const isCustomer=m=>!m.isBot&&!m.isStaff&&String(m.content||'').trim();

export async function draftFromChat({messages,staffNames,ask,goal,tone,app,clientFacts=[],style='',previous='',answerOnly=false}){
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
    return {...base,ok:true,status:'HUMAN_HANDOFF',draft:gate.reply,text:gate.reply,evidence:gate.evidence,reason:gate.reason};
  const res=await ask(buildConversationQuestion(chat,target.id,{goal:answerOnly?'answer_only':goal,tone,app,clientFacts,style,previous,stage:base.stage.stage}));
  const clean=t=>cleanDraft(t).replace(/@everyone|@here/g,'[mention removed]');
  const many=THREE_WAY.has(answerOnly?'answer_only':goal||'reply');
  const [first,...rest]=many?parseOptions(res.answer).map(clean):[clean(res.answer)];
  const draft=first;
  const check=validateDraft(draft);
  if(!check.ok) return {ok:false,text:`Draft blocked for review: ${check.reason}`};
  // Prompt pack §12/§21: Short and Warm alternatives; one that fails the guard is dropped, never shown.
  const alternatives=rest.slice(0,2).map((text,i)=>({label:ALT_LABELS[i],text})).filter(a=>a.text&&validateDraft(a.text).ok);
  return {...base,ok:true,status:'SUGGEST',draft,alternatives,evidence:evidenceFor(chat,target,draft),confidence:res.confidence,text:draft};
}
