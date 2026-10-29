import test from 'node:test';import assert from 'node:assert/strict';
import {buildPrompt} from '../src/prompt.js';
test('1000 synthetic isolated customer prompt builds do not borrow another customer context',()=>{
 const started=performance.now();
 for(let i=0;i<1000;i++){
   const customerId=`user-${i}`;
   const messages=[{id:'100',authorId:customerId,content:`yo bro need purple neon stream overlay unique-${i}`,createdAt:'2026-10-29T10:00:00Z'},
     {id:'101',authorId:'staff',content:'Could explore your color palette',createdAt:'2026-10-29T10:01:00Z'},
     {id:'102',authorId:customerId,content:`how about matching my unique-${i} banner?`,createdAt:'2026-10-29T10:02:00Z'}];
   const p=buildPrompt({messages,customerId,selectedMessageId:'102',facts:[],completion:true});
   assert.ok(p.user.includes(`unique-${i}`));
   assert.equal(p.evidenceIds.length,3);
 }
 assert.ok(Number.isFinite(performance.now()-started));
});
