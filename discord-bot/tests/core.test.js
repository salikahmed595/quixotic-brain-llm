import test from 'node:test';
import assert from 'node:assert/strict';
import {extractExplicitFacts,scoreOverlap,retrieveKV,inferStyle,validateDraft,makeSameChatPairs,recentContext,pickRelevantOldMessages} from '../src/core.js';
const M=(id,authorId,content)=>({id:String(id),authorId,content,createdAt:'2026-10-29T12:00:00Z'});
test('key-value retrieval selects budget conversation over unrelated gaming topic',()=>{
 const rows=[{key:'do you play valorant',value:'i do'},{key:'i have $60 for a Twitch banner',value:'offer a static design'}];
 assert.equal(retrieveKV('i have $70 for a twitch banner',rows)[0].value,'offer a static design');
});
test('key-value retrieval does not insert unrelated examples',()=>assert.deepEqual(retrieveKV('zzzzzzz',[{key:'rainy day',value:'hi'}]),[]));
test('recency scopes conversation to selected message',()=>assert.deepEqual(recentContext([M(1,'a','one'),M(2,'b','two'),M(3,'a','three')],'2').map(x=>x.id),['1','2']));
test('style only reflects observed chat features',()=>{
 assert.equal(inferStyle([M(1,'client','yo bro, im on valorant rn')]).tone,'casual/slang');
 assert.equal(inferStyle([]).language,'unknown');
});
test('budget extraction preserves observed evidence without class or wealth guesses',()=>{
 const facts=extractExplicitFacts('bro i only got $70 for my cyberpunk banner');
 assert.equal(facts.find(f=>f.key==='stated_budget_usd')?.value,'70');
 assert.ok(facts.every(f=>!f.key.includes('income')&&!f.key.includes('wealth')));
});
test('contradicting budgets stay distinct events until source-aware selection',()=>{
 assert.equal(extractExplicitFacts('my budget is $300')[0].value,'300');
 assert.equal(extractExplicitFacts('my budget is $70')[0].value,'70');
});
test('historical conversation pair requires customer message followed by nonbot human',()=>{
 const rows=[M(1,'client','banner question'),M(2,'seller','a helpful reply'),M(3,'seller','more'),M(4,'client','thanks')];
 assert.equal(makeSameChatPairs(rows,'client').length,1);
 assert.equal(makeSameChatPairs(rows,'client')[0].value,'a helpful reply');
});
test('draft validator blocks unsupported delivery promises',()=>{
 assert.equal(validateDraft('we guarantee delivery tomorrow!').ok,false);
 assert.equal(validateDraft('we will deliver tomorrow').ok,false);
 assert.equal(validateDraft('let me check with the team before i promise tomorrow').ok,true);
});
test('draft validator blocks unsupported payment claims',()=>{
 assert.equal(validateDraft('your payment went through').ok,false);
});
test('draft validator rejects empty or gigantic message',()=>{
 assert.equal(validateDraft('').ok,false);assert.equal(validateDraft('x'.repeat(2000)).ok,false);
});
test('older excerpts rank on relevance rather than only latest',()=>{
 const rows=[M(1,'client','purple cyberpunk for twitch'),M(2,'seller','great'),M(3,'client','I will be back'),M(4,'seller','okay'),M(5,'client','hello')];
 assert.equal(pickRelevantOldMessages('purple cyberpunk overlay',rows,1,2)[0].id,'1');
});
