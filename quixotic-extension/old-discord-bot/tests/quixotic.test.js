import test from 'node:test';import assert from 'node:assert/strict';
import {askQuixotic,loadQuixoticConfig,resolveUserId} from '../src/quixotic.js';

const env={QUIXOTIC_API_URL:'https://ai.example.test/',QUIXOTIC_API_KEY:'qx_test_key',STAFF_USER_MAP:'{"111":"emp-1"}'};
const config=loadQuixoticConfig(env);

function fakeFetch(status,body){
  const calls=[];
  const fn=async(url,init)=>{calls.push({url,init});return {ok:status>=200&&status<300,status,json:async()=>body};};
  fn.calls=calls;return fn;
}

test('config fails loudly when a required Quixotic setting is missing',()=>{
  for(const k of Object.keys(env)){
    const partial={...env};delete partial[k];
    assert.throws(()=>loadQuixoticConfig(partial),new RegExp(k));
  }
});

test('config rejects a staff map that is not a JSON object of strings',()=>{
  assert.throws(()=>loadQuixoticConfig({...env,STAFF_USER_MAP:'not json'}),/STAFF_USER_MAP/);
  assert.throws(()=>loadQuixoticConfig({...env,STAFF_USER_MAP:'["emp-1"]'}),/STAFF_USER_MAP/);
});

test('unmapped Discord staff member is refused instead of acting as the key owner',()=>{
  assert.equal(resolveUserId(config,'111'),'emp-1');
  assert.throws(()=>resolveUserId(config,'999'),/not linked/);
});

test('ask posts question and mapped employee user_id with X-API-Key to /v1/ask',async()=>{
  const f=fakeFetch(200,{query_id:'q1',answer:'Draft text',confidence:'high'});
  const out=await askQuixotic(config,{question:'client asks about price',discordUserId:'111',mode:'sales_coach'},f);
  assert.deepEqual(out,{queryId:'q1',answer:'Draft text',confidence:'high'});
  const {url,init}=f.calls[0];
  assert.equal(url,'https://ai.example.test/v1/ask');
  assert.equal(init.method,'POST');
  assert.equal(init.headers['X-API-Key'],'qx_test_key');
  assert.equal(init.headers.Authorization,undefined);
  assert.deepEqual(JSON.parse(init.body),{question:'client asks about price',user_id:'emp-1',mode:'sales_coach'});
});

test('unmapped staff never reaches the API',async()=>{
  const f=fakeFetch(200,{});
  await assert.rejects(askQuixotic(config,{question:'hi',discordUserId:'999'},f),/not linked/);
  assert.equal(f.calls.length,0);
});

test('API errors surface the status without leaking the key',async()=>{
  for(const status of [401,403,429,503]){
    const f=fakeFetch(status,{detail:'nope'});
    await assert.rejects(askQuixotic(config,{question:'hi',discordUserId:'111'},f),err=>{
      assert.match(err.message,new RegExp(String(status)));
      assert.doesNotMatch(err.message,/qx_test_key/);
      return true;
    });
  }
});

test('response without an answer is rejected',async()=>{
  const f=fakeFetch(200,{query_id:'q1'});
  await assert.rejects(askQuixotic(config,{question:'hi',discordUserId:'111'},f),/no answer/);
});
