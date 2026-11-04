import test from 'node:test';import assert from 'node:assert/strict';
import {buildConversationQuestion} from '../lib/conversation.js';
import {draftFromChat} from '../lib/draft.js';
import {evidenceFor} from '../lib/evidence.js';

const c=(id,content)=>({id,author:'fox',isBot:false,isStaff:false,content});
const s=(id,content)=>({id,author:'Sara',isBot:false,isStaff:true,content});
const fakeAsk=answer=>{const calls=[];const fn=async q=>{calls.push(q);return {answer,confidence:'high'};};fn.calls=calls;return fn;};
const chat=[{id:'1',author:'fox',content:"I'm working on a fox-themed Twitch stream."},
  {id:'2',author:'Sara',content:'Nice, what part of the channel are you changing?'},
  {id:'3',author:'fox',content:"Mostly the overlays. Mine don't match the fox theme."}];

test('a reply asks for the best reply plus a shorter and a warmer one (prompt pack §12 step 6)',()=>{
  const q=buildConversationQuestion([c('1','hi')],'1',{goal:'reply'});
  assert.match(q,/numbered 1\. 2\. 3\./);assert.match(q,/shorter/);assert.match(q,/warmer/);
  assert.match(q,/only the message text/);
});

test('draft splits the three versions into a recommended reply and labelled Short and Warm options',async()=>{
  const ask=fakeAsk('1. A fox theme across the overlays could tie it together, subtle woodland or bold?\n2. "Subtle or bold for the fox overlays?"\n3. That makes sense, keeping the fox theme everywhere would look so cozy. What vibe are you going for?');
  const out=await draftFromChat({messages:chat,staffNames:'Sara',ask});
  assert.equal(out.ok,true);
  assert.match(out.draft,/^A fox theme across the overlays/);
  assert.deepEqual(out.alternatives.map(a=>a.label),['Short','Warm']);
  assert.equal(out.alternatives[0].text,'Subtle or bold for the fox overlays?');
});

test('a single unnumbered answer still works, with no alternatives',async()=>{
  const out=await draftFromChat({messages:chat,staffNames:'Sara',ask:fakeAsk('subtle or bold for the fox overlays?')});
  assert.equal(out.draft,'subtle or bold for the fox overlays?');
  assert.deepEqual(out.alternatives,[]);
});

test('an alternative that fails the guard is dropped; a failing main reply blocks the draft',async()=>{
  const ok=await draftFromChat({messages:chat,staffNames:'Sara',ask:fakeAsk('1. subtle or bold?\n2. we guarantee delivery tomorrow\n3. what vibe are you going for?')});
  assert.equal(ok.draft,'subtle or bold?');
  assert.deepEqual(ok.alternatives.map(a=>a.label),['Warm']);
  const bad=await draftFromChat({messages:chat,staffNames:'Sara',ask:fakeAsk('1. we guarantee delivery tomorrow\n2. ok\n3. sure')});
  assert.equal(bad.ok,false);assert.match(bad.text,/blocked/i);
});

test('evidence: the latest customer message plus earlier customer messages the reply builds on (pack §21)',()=>{
  const labelled=[c('1',"I'm working on a fox-themed Twitch stream."),s('2','what part are you changing?'),
    c('3','also my cat is sick lol'),c('4',"Mostly the overlays. Mine don't match the fox theme.")];
  assert.deepEqual(evidenceFor(labelled,labelled[3],'A fox theme across the stream overlays, subtle or bold?'),['1','4']);
  assert.deepEqual(evidenceFor(labelled,labelled[3],'got it'),['4']);
});

test('draft returns evidence ids for the employee',async()=>{
  const out=await draftFromChat({messages:chat,staffNames:'Sara',ask:fakeAsk('A fox theme on the overlays and the stream, subtle or bold?')});
  assert.deepEqual(out.evidence,['1','3']);
});
