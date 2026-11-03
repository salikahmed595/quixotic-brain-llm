// Side panel (owner design 2026-10-30): setup steps, then the client's profile, AI Reply / Client Brain / History /
// Artwork Ideas tabs. Reads the open chat only on click; replies are copied by the employee, never sent.
import {draftFromChat} from './lib/draft.js';
import {askQuixotic} from './lib/quixotic.js';
import {signIn,signOut,QUIXOTIC_URL} from './lib/auth.js';
import {siteFor} from './lib/sites.js';
import {readWith} from './lib/read.js';
import {customerOf,lookupClient,createClient,makeApi,FACT_LABELS} from './lib/client.js';
import {suggestFacts,saveFacts} from './lib/facts.js';
import {parseStaffNames,labelMessages} from './lib/labels.js';
import {profileOf,STAGES,stagePayload,noteFact} from './lib/profile.js';
import {highlightParts} from './lib/highlight.js';
import {parseOptions} from './lib/options.js';
import {warningsFor} from './lib/warnings.js';
import {STAGES as CONV_STAGES,INTENTS} from './lib/stage.js';

const $=id=>document.getElementById(id);
const el=(tag,props={},...kids)=>{const n=Object.assign(document.createElement(tag),props);n.append(...kids);return n;};
const state={signedIn:false,staffNames:'',editingStaff:false,goal:'reply',tone:'match',style:'',draft:'',answerOnly:false,chat:[]};
const authStatus=t=>{$('authStatus').textContent=t;};
const status=t=>{$('status').textContent=t;};
function toast(t){$('toast').textContent=t;$('toast').hidden=false;clearTimeout(toast.t);toast.t=setTimeout(()=>{$('toast').hidden=true;},2300);}

// ---- setup: sign in -> staff names -> use it ----
function render(){
  const step=!state.signedIn?1:(!state.staffNames.trim()||state.editingStaff)?2:3;
  for(const li of document.querySelectorAll('#steps .step')){
    const n=Number(li.dataset.step);
    li.className='step'+(n<step?' done':n===step?' current':'');
    li.querySelector('.now').hidden=n!==step;
    if(n===step) li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');
  }
  $('setup').hidden=step===3;$('signin').hidden=step!==1;$('staffForm').hidden=step!==2;$('app').hidden=step!==3;
  $('conn').textContent=state.signedIn?'Connected':'Signed out';$('conn').classList.toggle('on',state.signedIn);
}

chrome.storage.local.get(['csrf','staffNames','style']).then(({csrf,staffNames,style})=>{
  state.signedIn=Boolean(csrf);state.staffNames=staffNames||'';state.style=style||'';$('staff').value=state.staffNames;render();
});

// "My reply style" (owner master prompt 2026-10-30): the employee's own writing style, kept only in this browser.
$('editStyle').addEventListener('click',()=>{menu(false);$('styleText').value=state.style;$('styleForm').hidden=false;$('styleText').focus();});
$('styleCancel').addEventListener('click',()=>{$('styleForm').hidden=true;});
$('styleForm').addEventListener('submit',async e=>{
  e.preventDefault();state.style=$('styleText').value.trim();
  await chrome.storage.local.set({style:state.style});$('styleForm').hidden=true;toast('Saved. Every suggestion now follows your style.');
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

const menu=open=>{$('menu').hidden=!open;$('settings').setAttribute('aria-expanded',String(open));};
$('settings').addEventListener('click',()=>menu($('menu').hidden));
$('closePanel').addEventListener('click',()=>window.close());
$('editStaff').addEventListener('click',()=>{menu(false);state.editingStaff=true;render();});

async function endSession(message){
  await chrome.storage.local.remove('csrf');state.signedIn=false;render();authStatus(message);
}
$('logout').addEventListener('click',async()=>{
  menu(false);
  const {csrf}=await chrome.storage.local.get('csrf');
  try{if(csrf) await signOut({csrf});}catch{/* still forget it locally */}
  await endSession('Signed out.');
});

// ---- tabs ----
const TABS={reply:'tabReply',brain:'tabBrain',history:'tabHistory',ideas:'tabIdeas'};
function showTab(name){
  for(const b of document.querySelectorAll('.tab')) b.setAttribute('aria-selected',String(b.dataset.tab===name));
  for(const [k,id] of Object.entries(TABS)) $(id).hidden=k!==name;
  if(name==='history') loadHistory();
}
for(const b of document.querySelectorAll('.tab')) b.addEventListener('click',()=>showTab(b.dataset.tab));
$('viewProfile').addEventListener('click',()=>showTab('brain'));

// ---- reading the chat (only on click; any messaging site) ----
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
async function quixoticApi(){const {csrf}=await chrome.storage.local.get('csrf');return makeApi({apiUrl:QUIXOTIC_URL,csrf});}

// ---- Mini Brain: profile card, facts, suggestions ----
const brain={customer:null,client:null,facts:[],messages:[],app:null,suggested:[]};
const confirmed=()=>brain.facts.filter(f=>!f.status||f.status==='confirmed');

function setAvatar(node,customer){
  node.replaceChildren();
  if(customer?.avatar){node.append(el('img',{src:customer.avatar,alt:'',className:'avatar',style:'width:100%;height:100%;box-shadow:none'}));}
  else node.textContent=(customer?.name||'?').trim().charAt(0).toUpperCase()||'?';
}

function renderProfile(){
  const c=brain.customer,p=profileOf(brain.facts);
  setAvatar($('pAvatar'),c);
  $('pName').textContent=c?.name||'Open a customer chat';
  $('pApp').hidden=!brain.app;$('pApp').textContent=brain.app||'';
  $('pSub').textContent=c?([p.type,...p.tags.slice(0,2)].filter(Boolean).join(' • ')||(brain.client?'No facts saved yet':'New customer, no Mini Brain yet')):'Then click Suggest Reply. I read only what is on screen.';
  $('pChips').replaceChildren(...p.tags.slice(0,5).map(t=>el('span',{className:'chip-t',textContent:t})),
    ...(p.tags.length>5?[el('span',{className:'chip-t',textContent:`+${p.tags.length-5}`})]:[]));
  $('pRow').hidden=!brain.client;
  $('pStage').replaceChildren(el('option',{value:'',textContent:'● Set stage'}),...STAGES.map(s=>el('option',{value:s,textContent:`● ${s}`})));
  $('pStage').value=p.stage||'';
}

function renderBrain(){
  const {client,customer}=brain;
  $('brainTitle').textContent=client?`🧠 ${client.display_name}'s Mini Brain`:customer?`🧠 ${customer.name}`:'Client Brain';
  $('brainSub').textContent=client?(client.department?`Shared with ${client.department}. Replies use the confirmed facts.`:'Replies use the confirmed facts.'):
    customer?'New customer':'Click Suggest Reply on a customer chat to load their Mini Brain.';
  $('brainNew').hidden=!customer||Boolean(client);$('addFact').hidden=!client;
  $('facts').replaceChildren(...brain.facts.map(f=>el('li',{},el('span',{className:'tag',textContent:FACT_LABELS[f.category]||f.category}),
    el('span',{textContent:f.statement}),...(f.status&&f.status!=='confirmed'?[el('span',{className:'unsure',textContent:f.status})]:[]))));
  $('brainNote').textContent=client&&!brain.facts.length?'No saved facts yet. Tick suggested facts or add what you know.':'';
  brain.suggested=client?suggestFacts(labelMessages(brain.messages,parseStaffNames(state.staffNames)),brain.facts):[];
  $('suggest').hidden=!brain.suggested.length;
  $('suggestList').replaceChildren(...brain.suggested.map((f,i)=>{
    const box=el('input',{type:'checkbox',id:`sf${i}`});box.dataset.i=String(i);
    const label=el('label',{htmlFor:`sf${i}`,title:`From: "${f.source_text}"`},el('span',{className:'tag',textContent:FACT_LABELS[f.category]}),el('span',{textContent:f.statement}));
    return el('li',{},box,label);
  }));
  renderProfile();
}

async function loadBrain(messages,app){
  const customer=customerOf(messages,state.staffNames);
  Object.assign(brain,{customer,messages,app,client:null,facts:[]});
  if(!customer){renderBrain();return;}
  try{Object.assign(brain,await lookupClient({customer,api:await quixoticApi()}));}
  catch(e){renderBrain();$('brainNote').textContent=e.message;return;}
  renderBrain();
}
async function reloadBrain(){
  Object.assign(brain,await lookupClient({customer:brain.customer,api:await quixoticApi()}));renderBrain();
}

for(const cat of Object.keys(FACT_LABELS)) $('addCat').append(el('option',{value:cat,textContent:FACT_LABELS[cat]}));
$('addFact').addEventListener('submit',async e=>{
  e.preventDefault();
  try{
    await (await quixoticApi())(`/v1/clients/${brain.client.id}/memories`,{method:'POST',body:noteFact({category:$('addCat').value,text:$('addText').value})});
    $('addText').value='';await reloadBrain();toast('Added to the Mini Brain.');
  }catch(err){$('brainNote').textContent=err.message;}
});

$('saveFacts').addEventListener('click',async()=>{
  const ticked=[...document.querySelectorAll('#suggestList input:checked')].map(b=>brain.suggested[Number(b.dataset.i)]);
  if(!ticked.length){$('brainNote').textContent='Tick the facts that are right, then save.';return;}
  $('saveFacts').disabled=true;
  try{
    const out=await saveFacts({clientId:brain.client.id,facts:ticked,app:brain.app,api:await quixoticApi()});
    await reloadBrain();
    if(out.errors.length) $('brainNote').textContent=`Not saved: ${out.errors.join('; ')}`;
    if(out.saved) toast(`Saved ${out.saved} fact${out.saved>1?'s':''} to the Mini Brain.`);
  }catch(err){$('brainNote').textContent=err.message;}
  finally{$('saveFacts').disabled=false;}
});

$('pStage').addEventListener('change',async()=>{
  if(!$('pStage').value) return;
  try{
    await (await quixoticApi())(`/v1/clients/${brain.client.id}/memories`,{method:'POST',body:stagePayload($('pStage').value,profileOf(brain.facts).stageFactId)});
    await reloadBrain();toast(`Stage set to ${$('pStage').value}.`);
  }catch(err){status(err.message);renderProfile();}
});

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
        sel.replaceChildren(...names.map(n=>el('option',{value:n,textContent:n})));
        sel.hidden=false;$('brainNote').textContent="Choose the client's department, then click Create again.";return;
      }
      department=names[0]||null;
    }
    Object.assign(brain,await createClient({customer:brain.customer,department,api}));
    sel.hidden=true;renderBrain();toast('Mini Brain created. Tick the facts that are right.');
  }catch(e){$('brainNote').textContent=e.message;}
  finally{$('brainCreate').disabled=false;}
});

async function loadHistory(){
  if(!brain.client){$('history').replaceChildren();$('historyNote').textContent='Load a client with Suggest Reply first.';return;}
  try{
    const {memories=[]}=await (await quixoticApi())(`/v1/clients/${brain.client.id}/history`);
    const rows=[...memories].sort((a,b)=>String(b.observed_at||'').localeCompare(String(a.observed_at||'')));
    $('history').replaceChildren(...rows.map(m=>el('li',{},el('span',{textContent:`${FACT_LABELS[m.category]||m.category}: ${m.statement}`}),
      el('small',{textContent:[m.observed_at?new Date(m.observed_at).toLocaleString():'',m.deleted_at?'removed':m.superseded_by?'replaced':m.status].filter(Boolean).join(' · ')}))));
    $('historyNote').textContent=rows.length?'':'Nothing saved yet.';
  }catch(e){$('historyNote').textContent=e.message;}
}

// ---- replies ----
for(const b of document.querySelectorAll('#tones .chip')) b.addEventListener('click',()=>{
  state.tone=b.dataset.tone;
  for(const x of document.querySelectorAll('#tones .chip')) x.setAttribute('aria-pressed',String(x===b));
  if(!$('result').hidden) suggest(state.goal);
});

function showReply(text){
  state.draft=text;
  const warns=warningsFor({messages:state.chat,draft:text,facts:confirmed()});
  $('warnings').hidden=!warns.length;$('warnings').replaceChildren(...warns.map(w=>el('li',{textContent:w.text})));
  const terms=[...profileOf(confirmed()).tags,...confirmed().filter(f=>f.category==='art_preference').map(f=>f.value)].filter(Boolean);
  $('replyText').replaceChildren(...highlightParts(text,terms).map(p=>p.hit?el('mark',{textContent:p.text}):document.createTextNode(p.text)));
}
function copyText(t,msg='Copied! Paste it into the chat, check it, then send.'){
  navigator.clipboard.writeText(t).then(()=>toast(msg),()=>toast('Select the text and copy it with Ctrl+C.'));
}

async function generate(goal){
  const {app,messages}=await readChat();
  await loadBrain(messages,app);
  const out=await draftFromChat({messages,staffNames:state.staffNames,ask,goal,tone:state.tone,app,clientFacts:confirmed(),
    style:state.style,previous:state.draft,answerOnly:state.answerOnly});
  if(out.chat) state.chat=out.chat;
  return out;
}

async function suggest(goal='reply'){
  state.goal=goal;
  const busy=$('go');busy.disabled=true;busy.textContent='✦ Reading the conversation…';status('');
  try{
    const out=await generate(goal);
    showGate(out);
    if(out.latest) showUnderstood(out);
    if(out.status==='NO_REPLY'){$('result').hidden=true;return;}
    if(!out.ok){status(out.text);$('result').hidden=true;return;}
    const options=goal==='variations'?parseOptions(out.draft):[out.draft];
    showReply(options[0]);
    $('variants').hidden=options.length<2;
    $('variants').replaceChildren(...options.slice(1).map(o=>{const b=el('button',{type:'button',textContent:'Use'});
      b.addEventListener('click',()=>showReply(o));return el('div',{className:'variant'},el('span',{textContent:o}),b);}));
    $('personal').hidden=!confirmed().length;
    $('result').hidden=false;
    $('why').textContent=`Based on the last ${out.messagesRead} messages on screen`+(confirmed().length?`, ${confirmed().length} confirmed facts from the Mini Brain`:'')+
      ` and Quixotic AI's approved company knowledge. Confidence: ${out.confidence??'unknown'}.`;
    $('result').scrollIntoView({block:'nearest',behavior:'smooth'});
  }catch(e){
    if(/sign in/i.test(e.message)) await endSession(e.message);
    status(e.message);
  }finally{busy.disabled=false;busy.textContent='✦ Suggest Reply →';}
}
// Prompt pack §27: what the assistant understood, so the employee can see why the reply fits.
function showUnderstood(out){
  $('latestCard').hidden=false;setAvatar($('lAvatar'),brain.customer);$('lText').textContent=out.latest.content||'';
  $('contextSub').textContent=`${out.messagesRead} messages read · only what is on screen; nothing is stored`;
  const st=out.stage,closed=st.stage==='CLOSED';
  const rows=[['Chat stage',CONV_STAGES[st.stage].label],['They want',INTENTS[st.intent]||st.intent],
    ['History','Partial: only the messages on screen'],
    ['Boundaries',closed?'Opted out: no sales':'No opt-out in the messages on screen'],['Next step',st.next]];
  $('convMeta').replaceChildren(...rows.flatMap(([k,v])=>[el('dt',{textContent:k}),el('dd',{textContent:v,className:closed&&k!=='History'?'stop':''})]));
  $('convMeta').hidden=false;
}
// Prompt pack §7/§17: the gate result is shown to the employee; NO_REPLY gives no text to send.
function showGate(out){
  const gate=out.status==='NO_REPLY'||out.status==='HUMAN_HANDOFF';
  $('gateCard').hidden=!gate;$('answerOnly').hidden=out.status!=='NO_REPLY';
  if(!gate) return;
  $('gateTitle').textContent=out.status==='NO_REPLY'?'No sales reply: the customer opted out':'Hand off to the team: the customer wants to pay';
  $('gateText').textContent=(out.status==='NO_REPLY'?'Respect it: no pitch and no follow-up.':out.reason);
  const said=out.chat?.find(m=>m.id===out.evidence?.[0]);
  if(said) $('gateText').textContent+=` They said: "${said.content}"`;
}
$('go').addEventListener('click',()=>{state.answerOnly=false;suggest('reply');});
$('answerOnly').addEventListener('click',()=>{state.answerOnly=true;suggest('reply');});
$('again').addEventListener('click',()=>suggest(state.goal));
for(const b of document.querySelectorAll('#goals .opt')) b.addEventListener('click',()=>suggest(b.dataset.goal));
for(const b of document.querySelectorAll('#rewrites .mini')) b.addEventListener('click',()=>{if(state.draft) suggest(b.dataset.rewrite);});
$('whyToggle').addEventListener('click',()=>{$('why').hidden=!$('why').hidden;});
$('copy').addEventListener('click',()=>copyText($('replyText').textContent));
$('copyMini').addEventListener('click',()=>copyText($('replyText').textContent));

$('getIdeas').addEventListener('click',async()=>{
  $('getIdeas').disabled=true;$('ideasStatus').textContent='Thinking of ideas…';
  try{
    const out=await generate('ideas');
    if(!out.ok){$('ideasStatus').textContent=out.text;return;}
    $('ideas').replaceChildren(...parseOptions(out.draft).map(i=>{const b=el('button',{type:'button',textContent:'Copy'});
      b.addEventListener('click',()=>copyText(i,'Idea copied.'));return el('div',{className:'idea'},el('span',{textContent:i}),b);}));
    $('ideasStatus').textContent='';
  }catch(e){if(/sign in/i.test(e.message)) await endSession(e.message);$('ideasStatus').textContent=e.message;}
  finally{$('getIdeas').disabled=false;}
});
