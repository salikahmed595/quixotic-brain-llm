import test from 'node:test';import assert from 'node:assert/strict';
import {buildPrompt} from '../src/prompt.js';
const ms=[{id:'100',authorId:'client',content:'I want a purple cyberpunk banner',createdAt:'2026-10-01'},
{id:'101',authorId:'staff',content:'What size banner?',createdAt:'2026-10-01'},
{id:'102',authorId:'client',content:'yo bro I have only $70 rn',createdAt:'2026-10-02'},
{id:'103',authorId:'staff',content:'let me ask the artist',createdAt:'2026-10-02'}];
test('prompt includes relevant scoped conversation and unreviewed KV disclaimer',()=>{
 const p=buildPrompt({messages:ms,customerId:'client',selectedMessageId:'102',facts:[],completion:false});
 assert.match(p.user,/\$70/);assert.match(p.user,/PARTIAL/);assert.match(p.system,/UNREVIEWED EXAMPLES/);
 assert.doesNotMatch(p.user,/let me ask the artist/); // after selected message
});
test('prompt does not invent a source memory',()=>{
 const p=buildPrompt({messages:ms,customerId:'client',selectedMessageId:'102',facts:[],completion:true});
 assert.match(p.user,/No extracted facts/);
});
