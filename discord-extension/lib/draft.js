// Visible chat -> labelled conversation -> Quixotic AI -> guarded private draft. Never sends anything to Discord.
import {parseStaffNames,labelMessages} from './labels.js';
import {buildConversationQuestion} from './conversation.js';
import {validateDraft} from './guard.js';

const isCustomer=m=>!m.isBot&&!m.isStaff&&String(m.content||'').trim();

export async function draftFromChat({messages,staffNames,ask,goal,tone}){
  const names=parseStaffNames(staffNames);
  if(!names.size) return {ok:false,text:'Add the staff names (as shown in Discord) first, so I know who is the customer.'};
  const chat=labelMessages(messages,names);
  const target=chat.filter(isCustomer).at(-1);
  if(!target) return {ok:false,text:'No customer message in view. Scroll to the chat and try again.'};
  const res=await ask(buildConversationQuestion(chat,target.id,{goal,tone}));
  const messagesRead=chat.filter(m=>!m.isBot&&String(m.content||'').trim()).length;
  const draft=res.answer.replace(/@everyone|@here/g,'[mention removed]');
  const check=validateDraft(draft);
  if(!check.ok) return {ok:false,text:`Draft blocked for review: ${check.reason}`};
  return {ok:true,draft,confidence:res.confidence,text:draft,messagesRead};
}
