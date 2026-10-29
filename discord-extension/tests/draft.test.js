import test from 'node:test';import assert from 'node:assert/strict';
import {parseStaffNames,labelMessages} from '../lib/labels.js';
import {askQuixotic} from '../lib/quixotic.js';
import {draftFromChat} from '../lib/draft.js';

const chat=[
  {id:'1001',author:'ali_gamer',isBot:false,content:'yo can u make a valorant banner?'},
  {id:'1002',author:'Sara | Quixotic',isBot:false,content:'sure! what size?'},
  {id:'1003',author:'TicketTool',isBot:true,content:'Ticket claimed'},
  {id:'1004',author:'ali_gamer',isBot:false,content:'twitch size, budget $70 rn'}
];
const fakeAsk=answer=>{const calls=[];const fn=async q=>{calls.push(q);return {answer,confidence:'high'};};fn.calls=calls;return fn;};

test('staff names: comma or newline separated, trimmed, case-insensitive, blanks ignored',()=>{
  const names=parseStaffNames(' Sara | Quixotic ,\nbilal\n\n');
  assert.deepEqual([...names],['sara | quixotic','bilal']);
  const out=labelMessages(chat,names);
  assert.deepEqual(out.map(m=>m.isStaff),[false,true,false,false]);
});

test('draft is built from the labelled chat and ends on the latest customer message',async()=>{
  const ask=fakeAsk('yo bet, purple twitch banner fits $70 👀');
  const out=await draftFromChat({messages:chat,staffNames:'Sara | Quixotic',ask});
  assert.equal(out.ok,true);
  const q=ask.calls[0];
  assert.match(q,/Customer: yo can u make a valorant banner\?\nStaff: sure! what size\?\nCustomer: twitch size, budget \$70 rn$/);
  assert.doesNotMatch(q,/Ticket claimed/);
  assert.match(out.text,/purple twitch banner/);
  assert.equal(out.draft,'yo bet, purple twitch banner fits $70 👀');
});

test('no staff names set: refuse instead of guessing who is staff',async()=>{
  const ask=fakeAsk('x');
  const out=await draftFromChat({messages:chat,staffNames:'  ',ask});
  assert.equal(out.ok,false);assert.match(out.text,/staff names/i);assert.equal(ask.calls.length,0);
});

test('no customer message in view: nothing is sent',async()=>{
  const ask=fakeAsk('x');
  const out=await draftFromChat({messages:chat.slice(1,3),staffNames:'Sara | Quixotic',ask});
  assert.equal(out.ok,false);assert.match(out.text,/no customer message/i);assert.equal(ask.calls.length,0);
});

test('unsafe promise from the model is blocked',async()=>{
  const out=await draftFromChat({messages:chat,staffNames:'Sara | Quixotic',ask:fakeAsk('we guarantee delivery tomorrow!')});
  assert.equal(out.ok,false);assert.match(out.text,/blocked/i);assert.equal(out.draft,undefined);
});

test('mass mentions are stripped',async()=>{
  const out=await draftFromChat({messages:chat,staffNames:'Sara | Quixotic',ask:fakeAsk('hey @everyone')});
  assert.doesNotMatch(out.draft,/@everyone/);
});

test('client posts the question to /v1/ask with the given auth headers',async()=>{
  const calls=[];
  const f=async(url,init)=>{calls.push({url,init});return {ok:true,status:200,json:async()=>({query_id:'q',answer:'hi',confidence:'low'})};};
  const out=await askQuixotic({apiUrl:'https://ai.example.test/',headers:{Authorization:'Bearer t'},question:'Q'},f);
  assert.deepEqual(out,{answer:'hi',confidence:'low'});
  assert.equal(calls[0].url,'https://ai.example.test/v1/ask');
  assert.equal(calls[0].init.headers.Authorization,'Bearer t');
  assert.deepEqual(JSON.parse(calls[0].init.body),{question:'Q'});
});

test('client errors carry the status only; 401 asks to sign in',async()=>{
  const f=status=>async()=>({ok:false,status,json:async()=>({detail:'x'})});
  await assert.rejects(askQuixotic({apiUrl:'https://a',headers:{},question:'Q'},f(401)),/sign in/i);
  await assert.rejects(askQuixotic({apiUrl:'https://a',headers:{},question:'Q'},f(503)),/503/);
  await assert.rejects(askQuixotic({apiUrl:'https://a',headers:{},question:'Q'},async()=>({ok:true,status:200,json:async()=>({})})),/no answer/);
});
