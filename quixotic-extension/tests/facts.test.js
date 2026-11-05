import test from 'node:test';import assert from 'node:assert/strict';
import {suggestFacts,factPayload,saveFacts} from '../lib/facts.js';

const c=(id,content,extra={})=>({id,author:'ali',authorId:'9',isBot:false,isStaff:false,content,...extra});

// Client Brain step 2 (owner 2026-10-30): facts are suggested from the customer's own words, each with the exact
// message it came from; nothing is saved until the employee ticks it. Rule-based until the backend suggestion slice lands.
test('finds games, platforms, art styles, colours, budget, deadline and concerns in customer messages',()=>{
  const facts=suggestFacts([
    c('1','yo i main valorant and some fortnite on twitch'),
    c('2','want a chibi emote, purple and black, budget $70'),
    c('3','need it by friday'),
    c('4','are you here trying to sell me your art?'),
  ]);
  const got=facts.map(f=>`${f.category}:${f.value}`);
  for(const want of ['game:Valorant','game:Fortnite','platform:Twitch','art_preference:chibi','art_preference:emote',
    'art_preference:purple','art_preference:black','budget:$70','deadline:by friday','objection:sales pitch'])
    assert.ok(got.includes(want),`${want} in ${got}`);
  const budget=facts.find(f=>f.category==='budget');
  assert.equal(budget.statement,'Mentioned a budget of $70');
  assert.equal(budget.source_id,'2');assert.equal(budget.source_text,'want a chibi emote, purple and black, budget $70');
});

test('staff and bot messages are never a source; each fact appears once',()=>{
  const facts=suggestFacts([c('1','we do valorant banners',{isStaff:true}),c('2','valorant pls'),c('3','valorant!!'),c('4','twitch',{isBot:true})]);
  assert.deepEqual(facts.map(f=>[f.value,f.source_id]),[['Valorant','2']]);
});

test('facts already in the Mini Brain are not suggested again',()=>{
  const facts=suggestFacts([c('1','valorant and apex')],[{category:'game',value:'Valorant',statement:'Plays Valorant'}]);
  assert.deepEqual(facts.map(f=>f.value),['Apex Legends']);
});

test('does not guess: numbers without money words and colour-like words in other senses are ignored',()=>{
  const got=suggestFacts([c('1','i have 2 channels and 300 followers'),c('2','feeling blue today lol')]).map(f=>f.category);
  assert.ok(!got.includes('budget'));
});

test('save payload: confirmed by the employee, Discord message id as the source; other apps keep only the text',()=>{
  const f=suggestFacts([c('123456789012345678','budget is 50 bucks')])[0];
  assert.deepEqual(factPayload(f,'Discord'),{category:'budget',statement:'Mentioned a budget of $50',value:'$50',status:'confirmed',
    source_type:'discord_message',source_id:'123456789012345678',source_text:'budget is 50 bucks'});
  assert.deepEqual(factPayload(f,'Twitch'),{category:'budget',statement:'Mentioned a budget of $50',value:'$50',status:'confirmed',
    source_type:'employee_note',source_id:'',source_text:'Twitch chat: budget is 50 bucks'});
});

test('saveFacts posts each ticked fact to the client and reports which failed',async()=>{
  const calls=[];
  const api=async(path,o)=>{calls.push([path,o.body.value]);if(o.body.value==='$50') throw new Error('budget already set');return {id:'m'};};
  const facts=suggestFacts([c('1','valorant, budget $50')]);
  const out=await saveFacts({clientId:'cl1',facts,app:'Discord',api});
  assert.deepEqual(calls.map(x=>x[0]),['/v1/clients/cl1/memories','/v1/clients/cl1/memories']);
  assert.equal(out.saved,1);assert.deepEqual(out.errors,['$50: budget already set']);
});

// Owner 2026-10-30: the Mini Brain also keeps the client type and how they write (seen in their messages, not guessed).
test('suggests the client type and how they write, quoting the message that shows it',()=>{
  const facts=suggestFacts([c('1','yo bro got any cool ideas for my stream? 👀🔥'),c('2','ngl i want it fr'),c('3','lol ok')]);
  const type=facts.find(f=>f.statement.startsWith('Client type'));
  assert.equal(type.statement,'Client type: Streamer');assert.equal(type.category,'other');assert.equal(type.source_id,'1');
  const talk=facts.filter(f=>f.category==='communication').map(f=>f.statement);
  assert.ok(talk.includes('Writes casually with slang (yo, bro, ngl, fr, lol)'),talk);
  assert.ok(talk.includes('Uses emoji'),talk);
  assert.ok(talk.includes('Writes short messages'),talk);
});

test('never suggests personality guesses: style comes only from words actually used',()=>{
  const facts=suggestFacts([c('1','Hello, I would like a logo for my business, please.')]);
  assert.ok(!facts.some(f=>f.category==='communication'));
  assert.ok(!facts.some(f=>/rich|poor|angry|lazy/i.test(f.statement)));
});
