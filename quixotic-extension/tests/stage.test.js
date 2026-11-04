import test from 'node:test';import assert from 'node:assert/strict';
import {stageOf,STAGES} from '../lib/stage.js';
import {buildConversationQuestion} from '../lib/conversation.js';
import {draftFromChat} from '../lib/draft.js';

const c=(id,content)=>({id,author:'fox',isBot:false,isStaff:false,content});
const s=(id,content)=>({id,author:'Sara',isBot:false,isStaff:true,content});
const one=t=>stageOf([s('1','hey'),c('2',t)]);

test('stage and intent come from the latest customer message (prompt pack §8)',()=>{
  const cases=[
    ['My fox VTuber is ready but the overlay still looks generic','NEEDS','art_need'],
    ['can u make emotes?','INTEREST','art_question'],
    ['do you have examples of your work?','INTEREST','asks_examples'],
    ['how much for a banner?','SCOPING','quote_request'],
    ['how long would that take?','SCOPING','deadline_question'],
    ["That's more than I planned",'OBJECTION','price_objection'],
    ['Is this just AI art?','OBJECTION','trust_objection'],
    ["still waiting on my emotes, it's been 2 weeks",'SUPPORT','needs_support'],
    ['Have you played Phasmophobia?','RAPPORT','gaming_question'],
    ['haha yeah same','RAPPORT','casual_chat'],
  ];
  for(const [t,stage,intent] of cases){
    const r=one(t);
    assert.equal(r.stage,stage,t);assert.equal(r.intent,intent,t);
    assert.deepEqual(r.evidence,['2']);
    assert.ok(STAGES[r.stage].next,t);
  }
});

test('first contact with no staff message yet is DISCOVERY',()=>{
  assert.equal(stageOf([c('1','yo whats up')]).stage,'DISCOVERY');
});

test('opt-out is CLOSED and payment request is READY (same rules as the gate)',()=>{
  assert.deepEqual([one('not interested').stage,one('not interested').intent],['CLOSED','customer_declines']);
  assert.deepEqual([one('where do i pay?').stage,one('where do i pay?').intent],['READY','wants_payment_link']);
});

test('support wins over a sale: an angry delay is SUPPORT even when it mentions price',()=>{
  assert.equal(one('i paid and its late, where is my order').stage,'SUPPORT');
});

test('the prompt names the stage and says the history may be partial (pack §5, scenario 12)',()=>{
  const q=buildConversationQuestion([c('1','how much for a banner?')],'1',{stage:'SCOPING'});
  assert.match(q,/stage[^\n]*SCOPING/i);
  assert.match(q,/older messages may be missing/i);
  assert.ok(q.length<=4000);
});

test('draft returns the stage and passes it to the AI',async()=>{
  const calls=[];const ask=async q=>{calls.push(q);return {answer:'sure, what size?',confidence:'high'};};
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:'how much for a banner?'}],staffNames:'Sara',ask});
  assert.equal(out.stage.stage,'SCOPING');
  assert.match(calls[0],/SCOPING/);
});
