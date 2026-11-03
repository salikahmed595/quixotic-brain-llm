import test from 'node:test';import assert from 'node:assert/strict';
import {verifyReply} from '../lib/verify.js';
import {buildConversationQuestion} from '../lib/conversation.js';
import {draftFromChat} from '../lib/draft.js';

const c=(id,content)=>({id,author:'fox',isBot:false,isStaff:false,content});
const s=(id,content)=>({id,author:'Sara',isBot:false,isStaff:true,content});
const needs=[c('1',"Mostly the overlays. Mine don't match the fox theme.")];
const checks=(draft,chat=needs,stage='NEEDS')=>verifyReply(draft,{chat,stage}).violations.map(v=>v.check);

test('a natural, grounded reply passes (prompt pack §19)',()=>{
  const r=verifyReply('Makes sense, the overlay should feel like part of the fox look. Cute and cozy or more dark fantasy?',{chat:needs,stage:'NEEDS'});
  assert.equal(r.verdict,'PASS');assert.deepEqual(r.violations,[]);
});

test('AI clichés and too many exclamation marks fail the tone check',()=>{
  assert.ok(checks("I totally understand! That's amazing!").includes('tone'));
  assert.ok(checks('This overlay will be a game-changer for you').includes('tone'));
  assert.ok(checks('love it!!! so cool!!').includes('tone'));
});

test('links are never allowed in a suggestion (§4 never invent links)',()=>{
  for(const t of ['see https://quixotic.example/work','check www.example.com','join discord.gg/abc']) assert.ok(checks(t).includes('link'),t);
});

test('invented viewer or gamer claims fail the honesty check (§3 STYLE, example 1 and 2)',()=>{
  for(const t of ['I saw your stream last night, the overlay could pop','yeah I main it every night','been watching you for a while haha','im a big fan of your streams'])
    assert.ok(checks(t).includes('honesty'),t);
});

test('more than one question fails (answer first, at most one question)',()=>{
  assert.ok(checks('What colours do you like? And when do you need it?').includes('questions'));
  assert.ok(!checks('Ohh nice?? what vibe are you going for?').includes('questions'));
});

test('too long fails, with more room when explaining a price, concern or order issue',()=>{
  const long=Array(70).fill('word').join(' ');
  assert.ok(checks(long).includes('length'));
  assert.ok(!checks(long,needs,'OBJECTION').includes('length'));
});

test('a price, discount or deposit not in the chat fails grounding (scenario 7 and 13)',()=>{
  assert.ok(checks('we can do it for $50').includes('grounding'));
  assert.ok(!checks('the $50 you mentioned works as a starting point',[c('1','my budget is $50')]).includes('grounding'));
});

test('repeating a question staff already asked fails (scenario 5)',()=>{
  const chat=[s('1','what colours do you want?'),c('2','purple, like I said')];
  assert.ok(checks('ohh nice, what colours do you want?',chat,'SCOPING').includes('repeat'));
});

test('pitching art when the customer never raised it fails (scenario 3, §12 step 3)',()=>{
  const chat=[c('1','have you played phasmophobia?')];
  assert.ok(checks('not yet haha, btw we do custom emotes if you ever need some',chat,'RAPPORT').includes('pitch'));
  assert.ok(!checks('not yet haha, is it scary?',chat,'RAPPORT').includes('pitch'));
});

test('the rewrite prompt lists what the last attempt got wrong',()=>{
  const q=buildConversationQuestion(needs,'1',{fix:['Too many questions','Has a link']});
  assert.match(q,/last attempt/i);assert.match(q,/Too many questions/);assert.match(q,/Has a link/);
});

const askSeq=(...answers)=>{const calls=[];const fn=async q=>{calls.push(q);return {answer:answers[calls.length-1],confidence:'high'};};fn.calls=calls;return fn;};

test('draft: a failing reply is rewritten once, and the passing rewrite is shown',async()=>{
  const ask=askSeq('1. I totally understand! check https://x.example','1. Makes sense, cute and cozy or more dark fantasy?');
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:"my overlays don't match the fox theme"}],staffNames:'Sara',ask});
  assert.equal(ask.calls.length,2);
  assert.match(ask.calls[1],/last attempt/i);
  assert.equal(out.ok,true);
  assert.equal(out.draft,'Makes sense, cute and cozy or more dark fantasy?');
  assert.equal(out.check.verdict,'PASS');
  assert.equal(out.check.revised,true);
});

test('draft: if the rewrite also fails, nothing is suggested (NEED_CONTEXT, pack §26)',async()=>{
  const ask=askSeq('I totally understand!','see https://x.example');
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:"my overlays don't match"}],staffNames:'Sara',ask});
  assert.equal(ask.calls.length,2);
  assert.equal(out.ok,false);assert.equal(out.status,'NEED_CONTEXT');
  assert.match(out.text,/write it yourself|checks/i);
});

test('draft: an alternative that fails the checker is dropped without a retry',async()=>{
  const ask=askSeq('1. cute and cozy or dark fantasy?\n2. www.example.com\n3. That makes sense, what vibe are you going for?');
  const out=await draftFromChat({messages:[{id:'1',author:'fox',content:"my overlays don't match the fox theme"}],staffNames:'Sara',ask});
  assert.equal(ask.calls.length,1);
  assert.deepEqual(out.alternatives.map(a=>a.label),['Warm']);
});
