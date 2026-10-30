import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const src=readFileSync(new URL('../readers/twitch.js',import.meta.url),'utf8');
function readFrom(html){
  const dom=new JSDOM(html,{runScripts:'outside-only'});
  dom.window.eval(src);
  return JSON.parse(JSON.stringify(dom.window.quixoticReadChat(dom.window.document)));
}
const fixture=readFileSync(new URL('./fixtures/twitch-chat.html',import.meta.url),'utf8');

// Owner 2026-10-30: Twitch chat is read without highlighting. Fixture is synthetic, modelled on twitch.tv chat lines.
test('reads chat lines in order with display names; status lines and the input box are skipped',()=>{
  assert.deepEqual(readFrom(fixture).map(m=>[m.id,m.author]),[['1','Ali_Gamer'],['2','Nightbot'],['3','Sara_Quixotic'],['4','Ali_Gamer']]);
});

test('message text keeps mentions and emote names, drops the name, timestamp and badges',()=>{
  const m=readFrom(fixture);
  assert.equal(m[0].content,'yo can u make my stream overlay? PogChamp');
  assert.equal(m[2].content,'@Ali_Gamer sure, which colours?');
  assert.equal(m[3].content,'purple and black, budget $50');
});

test('well-known chat bots are marked as bots so they are never the customer',()=>{
  assert.deepEqual(readFrom(fixture).map(m=>m.isBot),[false,true,false,false]);
});

test('a page without Twitch chat reads nothing',()=>{
  assert.deepEqual(readFrom('<html><body><p>hi</p></body></html>'),[]);
});
