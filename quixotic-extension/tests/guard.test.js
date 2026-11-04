import test from 'node:test';
import assert from 'node:assert/strict';
import {validateDraft} from '../lib/guard.js';
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
