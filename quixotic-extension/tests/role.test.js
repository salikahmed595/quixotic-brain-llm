import test from 'node:test';import assert from 'node:assert/strict';
import {ROLES} from '../lib/conversation.js';
import {buildConversationQuestion} from '../lib/conversation.js';
import {verifyReply} from '../lib/verify.js';
import {draftFromChat} from '../lib/draft.js';

const c=(id,content)=>({id,author:'fox',isBot:false,isStaff:false,content});
const checks=(draft,{chat,stage,role})=>verifyReply(draft,{chat,stage,role}).violations.map(v=>v.check);

test('three seller roles from the prompt pack (§14, §15, support)',()=>{
  assert.deepEqual(Object.keys(ROLES),['fresh','upseller','support']);
});

test('the prompt carries the role playbook',()=>{
  const q=r=>buildConversationQuestion([c('1','hi')],'1',{role:r});
  assert.match(q('fresh'),/first seller/i);assert.match(q('fresh'),/budget/i);
  assert.match(q('upseller'),/returning customer/i);assert.match(q('upseller'),/confirmed facts/i);
  assert.match(q('support'),/do not sell/i);
  assert.throws(()=>q('closer'),/Unknown role/);
});

test('no role chosen keeps the prompt as before',()=>{
  const q=buildConversationQuestion([c('1','hi')],'1',{});
  assert.doesNotMatch(q,/first seller|returning customer/i);
});

test('support role: selling during a support chat fails the checker (§10, scenario 15)',()=>{
  const chat=[c('1',"still waiting on my emotes, it's been 2 weeks")];
  assert.ok(checks('so sorry, checking with the artist now. btw wanna see our new banner pack?',{chat,stage:'SUPPORT',role:'support'}).includes('upsell'));
  assert.ok(!checks('so sorry about the wait, checking with the artist now and will update you today',{chat,stage:'SUPPORT',role:'support'}).includes('upsell'));
});

test('fresh seller: asking for a budget before there is a project fails (§14)',()=>{
  const chat=[c('1','yo whats up, how was your weekend')];
  assert.ok(checks('pretty chill haha, whats your budget for art?',{chat,stage:'RAPPORT',role:'fresh'}).includes('budget'));
  const scoping=[c('1','how much for a twitch banner?')];
  assert.ok(!checks('depends on the size, whats your budget?',{chat:scoping,stage:'SCOPING',role:'fresh'}).includes('budget'));
});

test('draft passes the role to the AI and the checker',async()=>{
  const calls=[];const ask=async q=>{calls.push(q);return {answer:'so sorry, checking now',confidence:'high'};};
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:'still waiting on my emotes'}],staffNames:'Sara',ask,role:'support'});
  assert.equal(out.ok,true);
  assert.match(calls[0],/do not sell/i);
});
