// Draft Sales Reply: the customer message goes to Quixotic AI as the invoking employee; the result is a private
// draft the employee reviews and sends by hand (never auto-sent to the client; CLAUDE.md Rule 2).
import {validateDraft} from './core.js';
import {askQuixotic,NotLinkedError} from './quixotic.js';

export async function draftReply({config,discordUserId,customerText},ask=askQuixotic){
  const question=String(customerText||'').trim();
  if(!question) return {ok:false,text:'That message has no text to draft a reply for.'};
  let res;
  try{res=await ask(config,{question,discordUserId});}
  catch(e){if(e instanceof NotLinkedError) return {ok:false,text:e.message};throw e;}
  const draft=res.answer.replace(/@everyone|@here/g,'[mention removed]');
  const check=validateDraft(draft);
  if(!check.ok) return {ok:false,reason:check.reason,text:`⚠️ Draft blocked for review: ${check.reason}\nNo reply was sent to the customer.`};
  const text=`**Private AI Draft — NOT SENT**\n${draft}\n\n**Confidence:** ${res.confidence??'unknown'}\n\nCopy, edit and verify pricing/delivery before sending.`;
  return {ok:true,text:text.slice(0,1950)};
}
