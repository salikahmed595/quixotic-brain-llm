import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
const manifest=JSON.parse(readFileSync(root+'manifest.json','utf8'));

test('Manifest V3 with a side panel opened from the toolbar button',()=>{
  assert.equal(manifest.manifest_version,3);
  assert.ok(manifest.name&&manifest.version&&manifest.description);
  assert.equal(manifest.side_panel.default_path,'panel.html');
  assert.equal(manifest.background.service_worker,'background.js');
  assert.ok(manifest.action);
  for(const f of ['panel.html','panel.js','background.js']) assert.ok(existsSync(root+f),f);
});

test('least privilege: reads a tab only when clicked; other sites only after the employee allows them',()=>{
  assert.deepEqual(manifest.permissions,['sidePanel','storage','scripting','activeTab']);
  assert.deepEqual(manifest.optional_host_permissions,['https://*/*','http://*/*']);
  for(const risky of ['tabs','cookies','history','webRequest','<all_urls>','debugger'])
    assert.ok(!JSON.stringify(manifest).includes(`"${risky}"`),risky);
  assert.equal(manifest.content_scripts,undefined);   // nothing runs on any page until Suggest Reply is clicked
});

test('panel has no inline script (MV3 CSP) and loads panel.js',()=>{
  const html=readFileSync(root+'panel.html','utf8');
  assert.match(html,/<script type="module" src="panel\.js"><\/script>/);
  assert.doesNotMatch(html,/<script>(?!<\/script>)/);
  assert.doesNotMatch(html,/\son\w+=/i);
});

test('background opens the panel when the toolbar button is clicked',()=>{
  assert.match(readFileSync(root+'background.js','utf8'),/setPanelBehavior\(\{\s*openPanelOnActionClick:\s*true\s*\}\)/);
});

test('readers only read: they never type, click, send or call the network',()=>{
  for(const f of ['readers/discord.js','readers/selection.js','readers/twitch.js','readers/x.js']){
    const js=readFileSync(root+f,'utf8');
    assert.match(js,/globalThis\.quixoticReadChat=/,f);
    assert.doesNotMatch(js,/textbox|contenteditable|dispatchEvent|\.click\(|fetch\(|XMLHttpRequest|sendMessage/i,f);
  }
});

test('panel never writes into Discord: it only copies to the clipboard',()=>{
  const js=readFileSync(root+'panel.js','utf8');
  assert.match(js,/navigator\.clipboard\.writeText/);
  assert.doesNotMatch(js,/dispatchEvent|textbox|insertText|execCommand/);
});

test('always-allowed sites: the Quixotic AI site and the apps with their own reader',()=>{
  assert.deepEqual(manifest.host_permissions,['https://maqsad.quixoticcreatives.com/*','https://discord.com/*','https://www.twitch.tv/*','https://dashboard.twitch.tv/*','https://x.com/*']);
});

test('panel never stores the password',()=>{
  const js=readFileSync(root+'panel.js','utf8');
  assert.doesNotMatch(js,/storage\.local\.set\(\{[^}]*password/i);
});

test('panel follows the owner design: goal + tone chips, Suggest Reply, step guide',()=>{
  const html=readFileSync(root+'panel.html','utf8');
  for(const g of ['reply','pitch','close']) assert.match(html,new RegExp(`data-goal="${g}"`));
  for(const t of ['match','friendly','professional']) assert.match(html,new RegExp(`data-tone="${t}"`));
  assert.match(html,/Suggest Reply/);
  assert.match(html,/id="steps"/);
  for(const s of ['Sign in','Add staff names','Open a chat']) assert.match(html,new RegExp(s));
  assert.doesNotMatch(html,/fonts\.googleapis|<link[^>]+https?:/);   // no third-party requests from the panel
});
