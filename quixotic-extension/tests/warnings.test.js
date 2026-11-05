import test from 'node:test';import assert from 'node:assert/strict';
import {warningsFor} from '../lib/warnings.js';

const C=(id,content)=>({id,author:'ali',isStaff:false,isBot:false,content});
const S=(id,content)=>({id,author:'me',isStaff:true,isBot:false,content});
const w=(chat,draft,facts=[])=>warningsFor({messages:chat,draft,facts}).map(x=>x.kind);

// Owner master prompt Part 18.7: warnings in the panel, worked out in code from the chat and the draft.
test('money worries and refusals in the customer\'s messages are flagged',()=>{
  assert.deepEqual(w([C('1',"i don't have any money to commission anything rn")],'ohh no worries ❤️'),['financial']);
  assert.deepEqual(w([C('1',"i've already put more money into this channel than is good for me")],'ok'),['financial']);
  assert.deepEqual(w([C('1','not interested tbh, pls stop asking')],'ok'),['refusal']);
});

test('a price, discount or deposit in the draft that is not in the chat or Mini Brain is flagged',()=>{
  assert.deepEqual(w([C('1','how much for an overlay?')],'it would be $79 for static ^^'),['price']);
  assert.deepEqual(w([C('1','you said $79 right?')],'yeahh $79 ^^'),[]);
  assert.deepEqual(w([C('1','hi')],'i can do 20% off for you'),['price']);
  assert.deepEqual(w([C('1','ok')],'just send a small deposit to start'),['price']);
});

test('payment and deadline claims are flagged',()=>{
  assert.deepEqual(w([C('1','sent it')],'got your payment, thanks!'),['payment']);
  assert.deepEqual(w([C('1','when?')],"i'll have the draft ready by friday"),['deadline']);
});

test('a question the staff already asked, or the customer already answered, is flagged as repeated',()=>{
  assert.deepEqual(w([S('1','what games do you play?'),C('2','mostly valorant')],'btw what games do you play? ^^'),['repeat']);
  assert.deepEqual(w([C('1','hi')],'how was your day?'),[]);
});

test('every warning has a short message for the panel',()=>{
  const out=warningsFor({messages:[C('1',"can't afford it")],draft:'ok $50 then',facts:[]});
  assert.ok(out.every(x=>x.text&&x.text.length<120));
});
