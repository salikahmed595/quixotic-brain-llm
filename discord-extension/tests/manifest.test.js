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
