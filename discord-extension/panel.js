// Side panel (owner design 2026-10-29): a 3-step guide, then goal + tone, Suggest Reply, and a draft to copy.
import {draftFromChat} from './lib/draft.js';
import {askQuixotic} from './lib/quixotic.js';
import {signIn,signOut,QUIXOTIC_URL} from './lib/auth.js';

const $=id=>document.getElementById(id);
const state={signedIn:false,staffNames:'',editingStaff:false,goal:'reply',tone:'match'};
const authStatus=t=>{$('authStatus').textContent=t;};
const status=t=>{$('status').textContent=t;};
function toast(t){$('toast').textContent=t;$('toast').hidden=false;clearTimeout(toast.t);toast.t=setTimeout(()=>{$('toast').hidden=true;},2300);}

// Which step to do next: sign in -> staff names -> use it.
function render(){
  const step=!state.signedIn?1:(!state.staffNames.trim()||state.editingStaff)?2:3;
  for(const li of document.querySelectorAll('#steps .step')){
    const n=Number(li.dataset.step);
    li.className='step'+(n<step?' done':n===step?' current':'');
    li.querySelector('.now').hidden=n!==step;
    if(n===step) li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');
  }
  $('signin').hidden=step!==1;$('staffForm').hidden=step!==2;$('app').hidden=step!==3;
}

chrome.storage.local.get(['csrf','staffNames']).then(({csrf,staffNames})=>{
  state.signedIn=Boolean(csrf);state.staffNames=staffNames||'';$('staff').value=state.staffNames;render();
});

$('signin').addEventListener('submit',async e=>{
  e.preventDefault();$('login').disabled=true;authStatus('Signing in…');
  try{
    const {csrf}=await signIn({identifier:$('ident').value,password:$('pw').value});
    await chrome.storage.local.set({csrf});
    state.signedIn=true;authStatus('');render();
  }catch(err){authStatus(err.message);}
  finally{$('pw').value='';$('login').disabled=false;}
});

$('staffForm').addEventListener('submit',async e=>{
  e.preventDefault();
  if(!$('staff').value.trim()){authStatus('Type at least your own Discord name.');return;}
  state.staffNames=$('staff').value;state.editingStaff=false;
  await chrome.storage.local.set({staffNames:state.staffNames});
  authStatus('');render();toast('Saved. Now open the customer chat and click Suggest Reply.');
});
$('editStaff').addEventListener('click',()=>{state.editingStaff=true;render();});

async function endSession(message){
  await chrome.storage.local.remove('csrf');state.signedIn=false;render();authStatus(message);
}
$('logout').addEventListener('click',async()=>{
  const {csrf}=await chrome.storage.local.get('csrf');
  try{if(csrf) await signOut({csrf});}catch{/* still forget it locally */}
  await endSession('Signed out.');
});

for(const [group,key] of [['goals','goal'],['tones','tone']]){
  for(const b of document.querySelectorAll(`#${group} .chip`)) b.addEventListener('click',()=>{
    state[key]=b.dataset[key];
    for(const x of document.querySelectorAll(`#${group} .chip`)) x.setAttribute('aria-pressed',String(x===b));
  });
}

async function readChat(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id) throw new Error('Open the customer chat on discord.com in this tab first.');
  try{return (await chrome.tabs.sendMessage(tab.id,{type:'quixotic-read-chat'})).messages;}
  catch{throw new Error('Open the customer chat on discord.com in this tab. Just installed? Reload the Discord page once.');}
}

async function ask(question){
  const {csrf}=await chrome.storage.local.get('csrf');
  return askQuixotic({apiUrl:QUIXOTIC_URL,headers:{'X-CSRF-Token':csrf},question});
}

async function suggest(){
  $('go').disabled=true;$('go').textContent='✦ Reading the conversation…';status('');
  try{
    const out=await draftFromChat({messages:await readChat(),staffNames:state.staffNames,ask,goal:state.goal,tone:state.tone});
    if(!out.ok){status(out.text);$('result').hidden=true;return;}
    $('replyText').textContent=out.draft;$('result').hidden=false;$('whyToggle').hidden=false;
    $('contextTitle').textContent=`${out.messagesRead} messages read from this chat`;
    $('contextSub').textContent='Only what is on screen; nothing is stored';
    $('why').textContent=`Based on the last ${out.messagesRead} messages on screen and Quixotic AI's approved company knowledge. Confidence: ${out.confidence??'unknown'}.`;
    $('result').scrollIntoView({block:'nearest',behavior:'smooth'});
  }catch(e){
    if(/sign in/i.test(e.message)) await endSession(e.message);
    status(e.message);
  }finally{$('go').disabled=false;$('go').textContent='✦ Suggest Reply →';}
}
$('go').addEventListener('click',suggest);
$('again').addEventListener('click',suggest);
$('whyToggle').addEventListener('click',()=>{$('why').hidden=!$('why').hidden;});

$('copy').addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText($('replyText').textContent);toast('Copied! Paste it into Discord, check it, then send.');}
  catch{toast('Select the reply text and copy it with Ctrl+C.');}
});
