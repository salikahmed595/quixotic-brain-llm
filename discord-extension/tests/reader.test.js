import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const src=readFileSync(new URL('../readers/discord.js',import.meta.url),'utf8');
// reader.js is a classic content script; run it inside a DOM window like Chrome would.
function readFrom(html){
  const dom=new JSDOM(html,{runScripts:'outside-only'});
  dom.window.eval(src);
  // JSON round-trip: arrays from the DOM window have that window's prototypes, which strict deepEqual rejects.
  return JSON.parse(JSON.stringify(dom.window.quixoticReadChat(dom.window.document)));
}
const fixture=readFileSync(new URL('./fixtures/discord-chat.html',import.meta.url),'utf8');

test('reads every message in order with its author, grouped messages inherit the author',()=>{
  const msgs=readFrom(fixture);
  assert.deepEqual(msgs.map(m=>[m.id,m.author]),[
    ['1001','ali_gamer'],['1002','ali_gamer'],['1003','Sara | Quixotic'],['1004','TicketTool'],['1005','ali_gamer'],['1006','ali_gamer']]);
});

test('message text keeps emoji names and drops the (edited) marker',()=>{
  const msgs=readFrom(fixture);
  assert.equal(msgs[0].content,'yo can u make a valorant banner? :fire:');
  assert.equal(msgs[2].content,'sure! what size do you need?');
});

test('reply previews are not mixed into the replying message',()=>{
  assert.equal(readFrom(fixture)[4].content,'twitch banner size, budget $70 rn');
});

test('bot/app messages are flagged',()=>{
  const msgs=readFrom(fixture);
  assert.equal(msgs[3].isBot,true);
  assert.equal(msgs[0].isBot,false);
});

test('image-only message has empty text (skipped later), not an error',()=>{
  assert.equal(readFrom(fixture)[5].content,'');
});

test('page without a chat gives an empty list',()=>{
  assert.deepEqual(readFrom('<html><body><p>Friends</p></body></html>'),[]);
});
