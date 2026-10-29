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

test('least privilege: side panel + storage only, no broad access',()=>{
  assert.deepEqual(manifest.permissions,['sidePanel','storage']);
  for(const risky of ['tabs','cookies','history','webRequest','scripting','<all_urls>','debugger'])
    assert.ok(!JSON.stringify(manifest).includes(`"${risky}"`),risky);
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

test('chat reader runs only on Discord web, reader before the message listener',()=>{
  assert.deepEqual(manifest.content_scripts,[{matches:['https://discord.com/*'],js:['reader.js','content.js']}]);
  assert.ok(existsSync(root+'content.js'));
});

test('content script only answers the read request and never touches the message box',()=>{
  const js=readFileSync(root+'content.js','utf8');
  assert.match(js,/quixotic-read-chat/);
  assert.doesNotMatch(js,/textbox|contenteditable|dispatchEvent|\.click\(|fetch\(/i);
});

test('panel never writes into Discord: it only copies to the clipboard',()=>{
  const js=readFileSync(root+'panel.js','utf8');
  assert.match(js,/navigator\.clipboard\.writeText/);
  assert.doesNotMatch(js,/executeScript|dispatchEvent|textbox/);
});

test('network access only to the Quixotic AI site; no Discord API access',()=>{
  assert.deepEqual(manifest.host_permissions,['https://maqsad.quixoticcreatives.com/*']);
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
  for(const s of ['Sign in','Add staff names','Open a Discord chat']) assert.match(html,new RegExp(s));
  assert.doesNotMatch(html,/fonts\.googleapis|<link[^>]+https?:/);   // no third-party requests from the panel
});
