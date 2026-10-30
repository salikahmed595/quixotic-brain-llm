// Side panel (owner design 2026-10-29): a 3-step guide, then goal + tone, Suggest Reply, and a draft to copy.
import {draftFromChat} from './lib/draft.js';
import {askQuixotic} from './lib/quixotic.js';
import {signIn,signOut,QUIXOTIC_URL} from './lib/auth.js';
import {siteFor} from './lib/sites.js';
import {readWith} from './lib/read.js';
import {customerOf,lookupClient,createClient,makeApi,FACT_LABELS} from './lib/client.js';

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
  if(!$('staff').value.trim()){authStatus('Type at least your own name as the chat shows it.');return;}
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

// Reads the open tab only now, on click (owner 2026-10-30: any messaging site). Apps in lib/sites.js have their own
// reader; on other sites the employee highlights the conversation and allows that site once.
async function readChat(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id) throw new Error('Open the customer chat in this tab first.');
  if(!tab.url) throw new Error('Click the orange Q icon on the toolbar while the chat is open, so I can read that page.');
  const site=siteFor(tab.url);
  if(!site) throw new Error('Chrome does not let extensions read this page. Open the chat website in this tab.');
  if(!site.builtIn&&!await chrome.permissions.contains({origins:[site.origin]})){
    try{await chrome.permissions.request({origins:[site.origin]});}catch{/* the Q-icon click may still allow this tab */}
  }
  const run=async file=>{
    await chrome.scripting.executeScript({target:{tabId:tab.id},files:[file]});
    const [{result}]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>globalThis.quixoticReadChat(document)});
    return result;
  };
  let messages;
  try{messages=await readWith(site,run);}
  catch{throw new Error('I could not read this page. Allow this site when asked, or click the orange Q icon on the toolbar, then try again.');}
  if(!messages.length) throw new Error(site.builtIn?`No ${site.app} chat found on screen. Open the conversation, or highlight it, then try again.`:'Highlight the conversation on the page first, then click Suggest Reply.');
  return {app:site.app,messages};
}

async function ask(question){
  const {csrf}=await chrome.storage.local.get('csrf');
  return askQuixotic({apiUrl:QUIXOTIC_URL,headers:{'X-CSRF-Token':csrf},question});
}

// Client Brain card: looked up each time Suggest Reply reads the chat; never blocks the draft.
const brain={customer:null};
async function quixoticApi(){const {csrf}=await chrome.storage.local.get('csrf');return makeApi({apiUrl:QUIXOTIC_URL,csrf});}
function showBrain({client,facts},customer){
  $('brain').hidden=false;$('brainNote').textContent='';
  $('brainTitle').textContent=client?`${client.display_name}'s Mini Brain`:customer.name;
  $('brainSub').textContent=client?(client.department?`Shared with ${client.department}`:'Saved client'):'New customer';
  $('brainNew').hidden=Boolean(client);
  const list=$('facts');list.replaceChildren();
  for(const f of facts){
    const li=document.createElement('li'),tag=document.createElement('span'),text=document.createElement('span');
    tag.className='tag';tag.textContent=FACT_LABELS[f.category]||f.category;text.textContent=f.statement;
    li.append(tag,text);
    if(f.status&&f.status!=='confirmed'){const u=document.createElement('span');u.className='unsure';u.textContent=f.status;li.append(u);}
    list.append(li);
  }
  if(client&&!facts.length) $('brainNote').textContent='No saved facts yet. Facts you confirm will show here.';
}
async function loadBrain(messages){
  const customer=customerOf(messages,state.staffNames);
  brain.customer=customer;
  if(!customer){$('brain').hidden=true;return;}
  try{showBrain(await lookupClient({customer,api:await quixoticApi()}),customer);}
  catch(e){$('brain').hidden=false;$('facts').replaceChildren();$('brainNew').hidden=true;$('brainTitle').textContent='Client Brain';
    $('brainSub').textContent=customer.name;$('brainNote').textContent=e.message;}
}
async function departmentChoices(api){
  const me=await api('/v1/auth/me');
  if(me.departments?.length) return me.departments.map(d=>d.name);
  return (await api('/v1/auth/signup-options')).departments.map(d=>d.name);   // all-department roles
}
$('brainCreate').addEventListener('click',async()=>{
  if(!brain.customer) return;
  $('brainCreate').disabled=true;
  try{
    const api=await quixoticApi(),sel=$('brainDept');
    let department=sel.hidden?null:sel.value;
    if(sel.hidden){
      const names=await departmentChoices(api);
      if(names.length>1){
        sel.replaceChildren(...names.map(n=>Object.assign(document.createElement('option'),{value:n,textContent:n})));
        sel.hidden=false;$('brainNote').textContent="Choose the client's department, then click Create again.";return;
      }
      department=names[0]||null;
    }
    showBrain(await createClient({customer:brain.customer,department,api}),brain.customer);
    sel.hidden=true;toast('Mini Brain created.');
  }catch(e){$('brainNote').textContent=e.message;}
  finally{$('brainCreate').disabled=false;}
});

async function suggest(){
  $('go').disabled=true;$('go').textContent='✦ Reading the conversation…';status('');
  try{
    const {app,messages}=await readChat();
    loadBrain(messages);
    const out=await draftFromChat({messages,staffNames:state.staffNames,ask,goal:state.goal,tone:state.tone,app});
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
  try{await navigator.clipboard.writeText($('replyText').textContent);toast('Copied! Paste it into the chat, check it, then send.');}
  catch{toast('Select the reply text and copy it with Ctrl+C.');}
});
