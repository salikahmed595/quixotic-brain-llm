import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';

const src=readFileSync(new URL('../readers/selection.js',import.meta.url),'utf8');
function readSelected(text){
  const dom=new JSDOM(`<body><div id="c"></div></body>`,{runScripts:'outside-only'});
  const d=dom.window.document,c=d.getElementById('c');
  c.textContent=text;
  if(text){const r=d.createRange();r.selectNodeContents(c);dom.window.getSelection().addRange(r);}
  dom.window.eval(src);
  return JSON.parse(JSON.stringify(dom.window.quixoticReadChat(d)));
}

test('"Name: message" lines become messages with their author; following lines join the message',()=>{
  assert.deepEqual(readSelected('ali: hi can u do a banner?\nSara: sure, what size?\nali: twitch size\nbudget 70'),[
    {id:'1',author:'ali',isBot:false,content:'hi can u do a banner?'},
    {id:'2',author:'Sara',isBot:false,content:'sure, what size?'},
    {id:'3',author:'ali',isBot:false,content:'twitch size budget 70'}]);
});

test('copied timestamps like [10:42 PM] are dropped from the name',()=>{
  assert.equal(readSelected('[10:42 PM] ali: yo')[0].author,'ali');
});

test('text without names is one customer message',()=>{
  assert.deepEqual(readSelected('do you make logos?\nhow much'),[{id:'1',author:'',isBot:false,content:'do you make logos? how much'}]);
});

test('nothing highlighted reads nothing',()=>{
  assert.deepEqual(readSelected(''),[]);
});
