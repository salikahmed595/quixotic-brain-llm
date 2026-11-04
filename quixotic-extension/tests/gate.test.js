import test from 'node:test';import assert from 'node:assert/strict';
import {gateFor,HANDOFF_REPLY} from '../lib/gate.js';
import {draftFromChat} from '../lib/draft.js';

const c=(id,content)=>({id,author:'fox',isBot:false,isStaff:false,content});
const s=(id,content)=>({id,author:'Sara',isBot:false,isStaff:true,content});
const fakeAsk=answer=>{const calls=[];const fn=async q=>{calls.push(q);return {answer,confidence:'high'};};fn.calls=calls;return fn;};

test('ordinary chat continues to a suggestion',()=>{
  assert.equal(gateFor([c('1','my overlays dont match the fox theme')]).status,'SUGGEST');
});

test('prompt pack example 3 and scenario 4: an opt-out gives NO_REPLY with the evidence message',()=>{
  for(const t of ["Don't add me if you're selling art",'not interested, thanks','pls stop dming me','no sales pls','dont sell me stuff','leave me alone']){
    const g=gateFor([s('1','hey'),c('2',t)]);
    assert.equal(g.status,'NO_REPLY',t);
    assert.deepEqual(g.evidence,['2']);
  }
});

test('staff saying no does not count as the customer opting out',()=>{
  assert.equal(gateFor([s('1','not interested in that deal haha'),c('2','lol ok')]).status,'SUGGEST');
});

test('latest boundary wins: re-inviting art talk after an opt-out continues',()=>{
  assert.equal(gateFor([c('1','not interested'),c('2','ok actually how much for an emote?')]).status,'SUGGEST');
  assert.equal(gateFor([c('1','how much for an emote?'),c('2','nah not interested anymore')]).status,'NO_REPLY');
});

test('prompt pack example 8 and scenario 6: a payment request gives HUMAN_HANDOFF and never a link',()=>{
  for(const t of ['Looks good. Where do I pay?','send me the payment link','how can i pay you','ok im ready to order']){
    const g=gateFor([c('1',t)]);
    assert.equal(g.status,'HUMAN_HANDOFF',t);
    assert.equal(g.reply,HANDOFF_REPLY);
    assert.doesNotMatch(g.reply,/https?:|www\./);
  }
});

test('"maybe later" is not readiness',()=>{
  assert.equal(gateFor([c('1','maybe later i will pay for it')]).status,'SUGGEST');
});

test('draft: NO_REPLY never calls the AI and gives no text to send',async()=>{
  const ask=fakeAsk('should not be used');
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:'not interested in art, stop'}],staffNames:'Sara',ask});
  assert.equal(ask.calls.length,0);
  assert.equal(out.ok,false);
  assert.equal(out.status,'NO_REPLY');
  assert.equal(out.draft,null);
  assert.match(out.text,/opted out|no sales/i);
});

test('draft: the employee can still ask for a non-sales reply after NO_REPLY',async()=>{
  const ask=fakeAsk('all good, enjoy the stream');
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:'not interested lol, anyway what game are u playing'}],staffNames:'Sara',ask,answerOnly:true});
  assert.equal(out.ok,true);
  assert.match(ask.calls[0],/no selling|do not mention artwork/i);
});

test('draft: HUMAN_HANDOFF gives the fixed acknowledgment without calling the AI',async()=>{
  const ask=fakeAsk('pay here https://evil.example');
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:'looks good, where do i pay?'}],staffNames:'Sara',ask});
  assert.equal(ask.calls.length,0);
  assert.equal(out.ok,true);
  assert.equal(out.status,'HUMAN_HANDOFF');
  assert.equal(out.draft,HANDOFF_REPLY);
});
