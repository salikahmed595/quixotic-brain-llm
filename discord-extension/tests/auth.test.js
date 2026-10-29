import test from 'node:test';import assert from 'node:assert/strict';
import {signIn,signOut,QUIXOTIC_URL} from '../lib/auth.js';
import {askQuixotic} from '../lib/quixotic.js';

const reply=(status,body={})=>{const calls=[];const f=async(url,init)=>{calls.push({url,init});return {ok:status>=200&&status<300,status,json:async()=>body};};f.calls=calls;return f;};

test('Quixotic AI address is the production site',()=>{
  assert.equal(QUIXOTIC_URL,'https://maqsad.quixoticcreatives.com');
});

test('sign-in posts to /v1/auth/login with cookies and keeps only the CSRF token',async()=>{
  const f=reply(200,{status:'ok',mfa:'none',csrf_token:'c1'});
  const out=await signIn({identifier:' sara ',password:'pw'},f);
  assert.deepEqual(out,{csrf:'c1'});
  const {url,init}=f.calls[0];
  assert.equal(url,QUIXOTIC_URL+'/v1/auth/login');
  assert.equal(init.method,'POST');
  assert.equal(init.credentials,'include');
  assert.deepEqual(JSON.parse(init.body),{identifier:'sara',password:'pw'});
});

test('sign-in errors are clear: wrong password, account state, throttled',async()=>{
  await assert.rejects(signIn({identifier:'a',password:'b'},reply(401,{detail:'invalid credentials'})),/wrong username or password/i);
  await assert.rejects(signIn({identifier:'a',password:'b'},reply(403,{detail:'Your account is waiting for approval.'})),/waiting for approval/);
  await assert.rejects(signIn({identifier:'a',password:'b'},reply(429,{detail:'Too many failed attempts.'})),/too many/i);
  await assert.rejects(signIn({identifier:'a',password:'b'},reply(500)),/500/);
});

test('accounts that need two-step sign-in are sent to the website',async()=>{
  await assert.rejects(signIn({identifier:'a',password:'b'},reply(200,{mfa:'verify',csrf_token:'c'})),/two-step/i);
});

test('empty username or password never calls the server',async()=>{
  const f=reply(200,{});
  await assert.rejects(signIn({identifier:' ',password:'x'},f),/username/i);
  await assert.rejects(signIn({identifier:'a',password:''},f),/password/i);
  assert.equal(f.calls.length,0);
});

test('sign-out posts /v1/auth/logout with the CSRF header and cookies; an expired session is fine',async()=>{
  const f=reply(200,{status:'signed_out'});
  await signOut({csrf:'c1'},f);
  assert.equal(f.calls[0].url,QUIXOTIC_URL+'/v1/auth/logout');
  assert.equal(f.calls[0].init.headers['X-CSRF-Token'],'c1');
  assert.equal(f.calls[0].init.credentials,'include');
  await signOut({csrf:'c1'},reply(401));
});

test('ask sends the session cookie',async()=>{
  const f=reply(200,{answer:'hi',confidence:'low'});
  await askQuixotic({apiUrl:QUIXOTIC_URL,headers:{'X-CSRF-Token':'c1'},question:'Q'},f);
  assert.equal(f.calls[0].init.credentials,'include');
  assert.equal(f.calls[0].init.headers['X-CSRF-Token'],'c1');
});
