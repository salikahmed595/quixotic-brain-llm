// Side panel: sign in to Quixotic AI, then on click read the open Discord chat, ask Quixotic AI, show a draft to copy.
import {draftFromChat} from './lib/draft.js';
import {askQuixotic} from './lib/quixotic.js';
import {signIn,signOut,QUIXOTIC_URL} from './lib/auth.js';

const $=id=>document.getElementById(id);
const status=t=>{$('status').textContent=t;};
const authStatus=t=>{$('authStatus').textContent=t;};

function showSignedIn(on){$('signin').hidden=on;$('app').hidden=!on;}
chrome.storage.local.get(['csrf','staffNames']).then(({csrf,staffNames})=>{
  $('staff').value=staffNames||'';showSignedIn(Boolean(csrf));
});
$('staff').addEventListener('change',()=>chrome.storage.local.set({staffNames:$('staff').value}));

$('signin').addEventListener('submit',async e=>{
  e.preventDefault();$('login').disabled=true;authStatus('Signing in…');
  try{
    const {csrf}=await signIn({identifier:$('ident').value,password:$('pw').value});
    await chrome.storage.local.set({csrf});
    showSignedIn(true);authStatus('');
  }catch(err){authStatus(err.message);}
  finally{$('pw').value='';$('login').disabled=false;}
});

async function endSession(message){
  await chrome.storage.local.remove('csrf');showSignedIn(false);authStatus(message);
}
$('logout').addEventListener('click',async()=>{
  const {csrf}=await chrome.storage.local.get('csrf');
  try{if(csrf) await signOut({csrf});}catch{/* still forget it locally */}
  await endSession('Signed out.');
});

async function readChat(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id) throw new Error('Open a Discord chat in this tab first.');
  try{return (await chrome.tabs.sendMessage(tab.id,{type:'quixotic-read-chat'})).messages;}
  catch{throw new Error('Open a Discord chat on discord.com in this tab (reload the page once after installing).');}
}

async function ask(question){
  const {csrf}=await chrome.storage.local.get('csrf');
  return askQuixotic({apiUrl:QUIXOTIC_URL,headers:{'X-CSRF-Token':csrf},question});
}

$('go').addEventListener('click',async()=>{
  $('go').disabled=true;$('copy').disabled=true;$('draft').value='';status('Reading the chat…');
  try{
    const out=await draftFromChat({messages:await readChat(),staffNames:$('staff').value,ask});
    if(out.ok){$('draft').value=out.draft;$('copy').disabled=false;status(`Confidence: ${out.confidence??'unknown'}`);}
    else status(out.text);
  }catch(e){
    if(/sign in/i.test(e.message)) await endSession(e.message);
    status(e.message);
  }
  finally{$('go').disabled=false;}
});

$('copy').addEventListener('click',async()=>{
  await navigator.clipboard.writeText($('draft').value);
  status('Copied. Paste it into Discord, check it, then send it yourself.');
});
