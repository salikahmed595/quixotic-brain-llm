import test from 'node:test';import assert from 'node:assert/strict';
import {customerOf,matchClient,lookupClient,createClient,makeApi,FACT_LABELS} from '../lib/client.js';

const chat=[
  {id:'1',author:'Cinnamon Angel ♡',authorId:'999',isBot:false,content:'hey'},
  {id:'2',author:'riggs',authorId:'5',isBot:false,content:'yo'},
  {id:'3',author:'MEE6',authorId:'7',isBot:true,content:'level up'},
  {id:'4',author:'Cinnamon Angel ♡',authorId:'999',isBot:false,content:'ok send examples'}];

// Client Brain step 1 (owner 2026-10-30): find the customer of the open chat and their Mini Brain.
test('the customer is the author of the latest non-staff, non-bot message',()=>{
  assert.deepEqual(customerOf(chat,'riggs'),{name:'Cinnamon Angel ♡',discordId:'999',avatar:''});
  assert.equal(customerOf(chat.slice(1,3),'riggs'),null);
  assert.deepEqual(customerOf([{id:'1',author:'',content:'hi'}],'riggs'),null);   // highlighted text without a name
});

test('match by Discord id first; by exact name only for a client saved without an id',()=>{
  const c=[{id:'a',display_name:'Cinnamon Angel ♡',discord_handle:'111'},{id:'b',display_name:'Other',discord_handle:'999'},
    {id:'c',display_name:'cinnamon angel ♡',discord_handle:null}];
  assert.equal(matchClient(c,{name:'Cinnamon Angel ♡',discordId:'999'}).id,'b');
  assert.equal(matchClient(c,{name:'Cinnamon Angel ♡',discordId:'222'}).id,'c');
  assert.equal(matchClient(c.slice(0,2),{name:'Cinnamon Angel ♡',discordId:'222'}),null);   // same name, different person
});

const fakeFetch=routes=>{const calls=[];const fn=async(url,opts)=>{calls.push({url,opts});const r=routes(url,opts);
  return {ok:r.status<300,status:r.status,json:async()=>r.body};};fn.calls=calls;return fn;};

test('api helper sends the session cookie and CSRF token and explains errors',async()=>{
  const f=fakeFetch(u=>u.endsWith('/denied')?{status:403,body:{detail:'you can only add clients to your own departments'}}:
    u.endsWith('/gone')?{status:401,body:{}}:{status:200,body:{ok:1}});
  const api=makeApi({apiUrl:'https://q.example/',csrf:'tok',fetchFn:f});
  assert.deepEqual(await api('/v1/x'),{ok:1});
  assert.equal(f.calls[0].url,'https://q.example/v1/x');assert.equal(f.calls[0].opts.credentials,'include');
  assert.equal(f.calls[0].opts.headers['X-CSRF-Token'],'tok');
  await assert.rejects(api('/denied'),/own departments/);
  await assert.rejects(api('/gone'),/sign in/i);
});

test('lookup searches by Discord id, then loads the matched client\'s facts',async()=>{
  const f=fakeFetch(u=>u.includes('/v1/clients?q=')?{status:200,body:{clients:[{id:'b',display_name:'Cinnamon Angel ♡',discord_handle:'999'}]}}:
    {status:200,body:{client:{id:'b',display_name:'Cinnamon Angel ♡'},facts:[{category:'game',statement:'Plays Valorant',status:'confirmed'}]}});
  const out=await lookupClient({customer:{name:'Cinnamon Angel ♡',discordId:'999'},api:makeApi({apiUrl:'https://q',csrf:'t',fetchFn:f})});
  assert.equal(f.calls[0].url,'https://q/v1/clients?q=999');
  assert.equal(f.calls[1].url,'https://q/v1/clients/b');
  assert.equal(out.client.id,'b');assert.equal(out.facts[0].statement,'Plays Valorant');
});

test('no match: nothing is created until the employee asks; create sends name, Discord id and department',async()=>{
  const f=fakeFetch((u,o)=>o.method==='POST'?{status:201,body:{id:'n',display_name:'Cinnamon Angel ♡'}}:{status:200,body:{clients:[]}});
  const api=makeApi({apiUrl:'https://q',csrf:'t',fetchFn:f});
  const out=await lookupClient({customer:{name:'Cinnamon Angel ♡',discordId:''},api});
  assert.deepEqual(out,{client:null,facts:[]});
  assert.equal(f.calls[0].url,'https://q/v1/clients?q=Cinnamon%20Angel%20%E2%99%A1');
  assert.equal(f.calls.length,1);
  const made=await createClient({customer:{name:'Cinnamon Angel ♡',discordId:'999'},department:'Sales',api});
  assert.deepEqual(JSON.parse(f.calls[1].opts.body),{display_name:'Cinnamon Angel ♡',discord_handle:'999',department:'Sales'});
  assert.deepEqual(made,{client:{id:'n',display_name:'Cinnamon Angel ♡'},facts:[]});
});

test('every backend fact category has a plain label',()=>{
  for(const c of ['art_preference','platform','game','communication','budget','deadline','commitment','objection','other']) assert.ok(FACT_LABELS[c],c);
});
