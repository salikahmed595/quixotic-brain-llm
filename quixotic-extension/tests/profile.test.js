import test from 'node:test';import assert from 'node:assert/strict';
import {profileOf,STAGES,stagePayload,noteFact} from '../lib/profile.js';
import {highlightParts} from '../lib/highlight.js';
import {parseOptions} from '../lib/options.js';

const facts=[
  {id:'f1',category:'other',value:'Streamer',statement:'Client type: Streamer'},
  {id:'f2',category:'game',value:'Valorant',statement:'Mentioned Valorant'},
  {id:'f3',category:'art_preference',value:'purple',statement:'Mentioned purple'},
  {id:'f4',category:'art_preference',value:'banner',statement:'Mentioned banner'},
  {id:'f5',category:'other',value:'Exploring',statement:'Sales stage: Exploring'},
  {id:'f6',category:'communication',value:'slang',statement:'Writes casually with slang'}];

// Owner 2026-10-30 design: profile card shows client type, top interests as chips, and the sales stage.
test('profile: client type, interest chips and stage come from saved facts',()=>{
  assert.deepEqual(profileOf(facts),{type:'Streamer',tags:['Valorant','purple','banner'],stage:'Exploring',stageFactId:'f5'});
  assert.deepEqual(profileOf([]),{type:null,tags:[],stage:null,stageFactId:null});
});

test('stage is set by the employee and replaces the previous stage',()=>{
  assert.deepEqual(STAGES,['New','Exploring','Interested','Quote sent','Paid']);
  assert.deepEqual(stagePayload('Interested','f5'),{category:'other',value:'Interested',statement:'Sales stage: Interested',status:'confirmed',
    source_type:'employee_note',source_id:'',source_text:'Set by an employee in the reply assistant',supersedes_memory_id:'f5'});
  assert.equal(stagePayload('New',null).supersedes_memory_id,undefined);
  assert.throws(()=>stagePayload('Rich'),/stage/);
});

test('an employee can type a fact; it is saved as their note',()=>{
  assert.deepEqual(noteFact({category:'other',text:'  Client type:  Streamer '}),{category:'other',value:'',statement:'Client type: Streamer',
    status:'confirmed',source_type:'employee_note',source_id:'',source_text:'Client type: Streamer'});
  assert.throws(()=>noteFact({category:'game',text:'  '}),/Type/);
});

test('reply highlights the client\'s known interests, longest match first, case-insensitive',()=>{
  assert.deepEqual(highlightParts('since ur into Valorant and black & purple vibes',['purple','valorant','black & purple']),[
    {text:'since ur into ',hit:false},{text:'Valorant',hit:true},{text:' and ',hit:false},{text:'black & purple',hit:true},{text:' vibes',hit:false}]);
  assert.deepEqual(highlightParts('hi',[]),[{text:'hi',hit:false}]);
});

test('numbered options are split into separate replies; plain text stays one',()=>{
  assert.deepEqual(parseOptions('1. yo bro\n2) what game u main?\n3. ok bet'),['yo bro','what game u main?','ok bet']);
  assert.deepEqual(parseOptions('just one reply'),['just one reply']);
});
