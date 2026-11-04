import test from 'node:test';import assert from 'node:assert/strict';
import {draftReply} from '../src/draft.js';
import {NotLinkedError} from '../src/quixotic.js';

const config={apiUrl:'https://ai.example.test',apiKey:'k',staffUserMap:{'111':'emp-1'}};
const fakeAsk=answer=>{const calls=[];const fn=async(cfg,args)=>{calls.push(args);return {queryId:'q1',answer,confidence:'high'};};fn.calls=calls;return fn;};

test('sends the customer message as the question for the invoking staff member',async()=>{
  const ask=fakeAsk('yo, happy to help with the banner');
  const out=await draftReply({config,discordUserId:'111',question:'can u do a banner?'},ask);
  assert.deepEqual(ask.calls[0],{question:'can u do a banner?',discordUserId:'111'});
  assert.equal(out.ok,true);
  assert.match(out.text,/NOT SENT/);
  assert.match(out.text,/yo, happy to help with the banner/);
  assert.match(out.text,/high/);
});

test('empty customer message never calls Quixotic AI',async()=>{
  const ask=fakeAsk('x');
  const out=await draftReply({config,discordUserId:'111',question:'   '},ask);
  assert.equal(out.ok,false);assert.equal(ask.calls.length,0);
  assert.match(out.text,/no text/i);
});

test('unsupported delivery promise is blocked, not shown as a draft',async()=>{
  const out=await draftReply({config,discordUserId:'111',question:'when?'},fakeAsk('Guaranteed delivery tomorrow!'));
  assert.equal(out.ok,false);
  assert.match(out.text,/blocked/i);
  assert.doesNotMatch(out.text,/Guaranteed delivery tomorrow/);
});

test('mass mentions are stripped from the draft',async()=>{
  const out=await draftReply({config,discordUserId:'111',question:'hi'},fakeAsk('hey @everyone and @here'));
  assert.doesNotMatch(out.text,/@everyone|@here/);
});

test('unlinked staff get a clear message instead of a generic error',async()=>{
  const ask=async()=>{throw new NotLinkedError();};
  const out=await draftReply({config,discordUserId:'999',question:'hi'},ask);
  assert.equal(out.ok,false);assert.match(out.text,/not linked/);
});

test('other failures propagate so the bot shows its safe generic error',async()=>{
  const ask=async()=>{throw new Error('Quixotic AI HTTP 503');};
  await assert.rejects(draftReply({config,discordUserId:'111',question:'hi'},ask),/503/);
});

test('output fits in one Discord message',async()=>{
  const out=await draftReply({config,discordUserId:'111',question:'hi'},fakeAsk('a'.repeat(1500)));
  assert.ok(out.text.length<=1950);
});
