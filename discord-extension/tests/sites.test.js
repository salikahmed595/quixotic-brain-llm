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

test('Twitch (channel, popout chat and creator dashboard) uses its own chat reader',()=>{
  for(const u of ['https://www.twitch.tv/somechannel','https://www.twitch.tv/popout/somechannel/chat','https://dashboard.twitch.tv/u/me/stream-manager']){
    const s=siteFor(u);assert.equal(s.app,'Twitch',u);assert.equal(s.file,'readers/twitch.js');assert.equal(s.builtIn,true);
  }
});
