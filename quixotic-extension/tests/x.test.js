import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const src=readFileSync(new URL('../readers/x.js',import.meta.url),'utf8');
// jsdom has no layout: give the timeline a width and put each bubble left or right, as X draws DMs.
function readFrom(html){
  const dom=new JSDOM(html,{runScripts:'outside-only'});
  const w=dom.window,rect=(l,r)=>()=>({left:l,right:r,width:r-l,top:0,bottom:10,height:10});
  for(const el of w.document.querySelectorAll('[data-testid="DmActivityViewport"]')) el.getBoundingClientRect=rect(0,600);
  for(const el of w.document.querySelectorAll('[data-testid="messageEntry"]')){
    const r=el.dataset.side==='right'?rect(380,590):rect(10,220);
    for(const n of [el,...el.querySelectorAll('*')]) n.getBoundingClientRect=r;
  }
  w.eval(src);
  return JSON.parse(JSON.stringify(w.quixoticReadChat(w.document)));
}
const fixture=readFileSync(new URL('./fixtures/x-dm.html',import.meta.url),'utf8');

// Owner 2026-10-30: X DMs read without highlighting. X shows no names per message, so own messages are the ones
// on the right; they count as staff whatever the staff names say.
test('reads DM bubbles in order; own (right-side) messages are marked fromMe',()=>{
  assert.deepEqual(readFrom(fixture).map(m=>[m.id,m.fromMe,m.content]),[
    ['1',false,'hey do you do twitter headers?'],
    ['2',true,'yes! what style do you like?'],
    ['3',false,'anime style, dark colours 🔥']]);
});

test('image-only bubbles, times and the message box are not read as text',()=>{
  const m=readFrom(fixture);
  assert.equal(m.length,3);
  assert.ok(m.every(x=>!/AM|not sent/.test(x.content)));
});

test('a page without an X conversation reads nothing',()=>{
  assert.deepEqual(readFrom('<html><body><p>timeline</p></body></html>'),[]);
});
