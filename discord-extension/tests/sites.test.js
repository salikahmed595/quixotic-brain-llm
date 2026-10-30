import test from 'node:test';import assert from 'node:assert/strict';
import {siteFor} from '../lib/sites.js';

// Owner 2026-10-30: works on every messaging site. Known apps get their own reader; any other site reads the
// text the employee highlights. Browser pages (chrome://, the Web Store) can't be read by any extension.
test('Discord uses its own chat reader',()=>{
  assert.deepEqual(siteFor('https://discord.com/channels/1/2'),{app:'Discord',file:'readers/discord.js',origin:'https://discord.com/*',builtIn:true});
});

test('any other website reads the highlighted conversation and needs the employee to allow that site',()=>{
  assert.deepEqual(siteFor('https://web.whatsapp.com/'),{app:null,file:'readers/selection.js',origin:'https://web.whatsapp.com/*',builtIn:false});
  assert.equal(siteFor('http://localhost:3000/chat').origin,'http://localhost:3000/*');
});

test('browser pages and missing URLs cannot be read',()=>{
  for(const u of ['chrome://extensions','https://chromewebstore.google.com/x','about:blank','',undefined,'not a url']) assert.equal(siteFor(u),null,String(u));
});
