// Side panel: on click, read the open Discord chat, ask Quixotic AI, show a private draft to copy.
import {draftFromChat} from './lib/draft.js';
import {askQuixotic} from './lib/quixotic.js';

const $=id=>document.getElementById(id);
const status=t=>{$('status').textContent=t;};

chrome.storage.local.get('staffNames').then(({staffNames})=>{$('staff').value=staffNames||'';});
$('staff').addEventListener('change',()=>chrome.storage.local.set({staffNames:$('staff').value}));

async function readChat(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id) throw new Error('Open a Discord chat in this tab first.');
  try{return (await chrome.tabs.sendMessage(tab.id,{type:'quixotic-read-chat'})).messages;}
  catch{throw new Error('Open a Discord chat on discord.com in this tab (reload the page once after installing).');}
}

async function ask(question){
  // Sign-in (apiUrl + session token) is set up in the next slice; until then this fails clearly.
  const {apiUrl,token}=await chrome.storage.local.get(['apiUrl','token']);
  if(!apiUrl||!token) throw new Error('Please sign in to Quixotic AI first.');
  return askQuixotic({apiUrl,headers:{Authorization:`Bearer ${token}`},question});
}

$('go').addEventListener('click',async()=>{
  $('go').disabled=true;$('copy').disabled=true;$('draft').value='';status('Reading the chat…');
  try{
    const out=await draftFromChat({messages:await readChat(),staffNames:$('staff').value,ask});
    if(out.ok){$('draft').value=out.draft;$('copy').disabled=false;status(`Confidence: ${out.confidence??'unknown'}`);}
    else status(out.text);
  }catch(e){status(e.message);}
  finally{$('go').disabled=false;}
});

$('copy').addEventListener('click',async()=>{
  await navigator.clipboard.writeText($('draft').value);
  status('Copied. Paste it into Discord, check it, then send it yourself.');
});
