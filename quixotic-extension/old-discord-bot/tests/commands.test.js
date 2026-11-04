import test from 'node:test';import assert from 'node:assert/strict';
import {COMMANDS,isCustomerMessage,pickLatestCustomerMessage} from '../src/commands.js';

const M=(id,o={})=>({id:String(id),authorId:'c1',isBot:false,isStaff:false,content:`msg ${id}`,...o});

test('only Draft Sales Reply and /suggest are registered; no storage or consent commands',()=>{
  assert.deepEqual(COMMANDS.map(c=>[c.name,c.type]),[['suggest',1],['Draft Sales Reply',3]]);
  assert.ok(COMMANDS.find(c=>c.name==='suggest').description);
});

test('customer message excludes bots, staff and empty text',()=>{
  assert.equal(isCustomerMessage(M(1)),true);
  assert.equal(isCustomerMessage(M(1,{isBot:true})),false);
  assert.equal(isCustomerMessage(M(1,{isStaff:true})),false);
  assert.equal(isCustomerMessage(M(1,{content:'  '})),false);
});

test('latest customer message is picked by snowflake order, skipping staff replies',()=>{
  const msgs=[M('900000000000000002'),M('900000000000000010',{isStaff:true}),M('900000000000000003'),M('900000000000000011',{isBot:true})];
  assert.equal(pickLatestCustomerMessage(msgs).id,'900000000000000003');
});

test('no customer message gives null',()=>{
  assert.equal(pickLatestCustomerMessage([M(1,{isStaff:true})]),null);
  assert.equal(pickLatestCustomerMessage([]),null);
});
