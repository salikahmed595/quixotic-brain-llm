import test from 'node:test';import assert from 'node:assert/strict';
import {readWith} from '../lib/read.js';
import {siteFor} from '../lib/sites.js';

const fakeRun=results=>{const calls=[];const fn=async f=>{calls.push(f);return results[f];};fn.calls=calls;return fn;};

test('an app reader that finds the chat is used as is',async()=>{
  const run=fakeRun({'readers/x.js':[{id:'1',content:'hi'}]});
  assert.deepEqual(await readWith(siteFor('https://x.com/messages/1'),run),[{id:'1',content:'hi'}]);
  assert.deepEqual(run.calls,['readers/x.js']);
});

// A site redesign (or a page the reader doesn't know, like Twitch whispers) still works by highlighting.
test('when an app reader finds nothing, the highlighted text is read instead',async()=>{
  const run=fakeRun({'readers/twitch.js':[],'readers/selection.js':[{id:'1',content:'yo'}]});
  assert.deepEqual(await readWith(siteFor('https://www.twitch.tv/c'),run),[{id:'1',content:'yo'}]);
  assert.deepEqual(run.calls,['readers/twitch.js','readers/selection.js']);
});

test('other sites read the highlight once; nothing found gives an empty list',async()=>{
  const run=fakeRun({});
  assert.deepEqual(await readWith(siteFor('https://web.whatsapp.com/'),run),[]);
  assert.deepEqual(run.calls,['readers/selection.js']);
});
