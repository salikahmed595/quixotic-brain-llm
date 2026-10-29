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

test('least privilege: only the side panel permission, no broad access',()=>{
  assert.deepEqual(manifest.permissions,['sidePanel']);
  for(const risky of ['tabs','cookies','history','webRequest','scripting','<all_urls>','debugger'])
    assert.ok(!JSON.stringify(manifest).includes(`"${risky}"`),risky);
});

test('panel has no inline script (MV3 CSP) and loads panel.js',()=>{
  const html=readFileSync(root+'panel.html','utf8');
  assert.match(html,/<script src="panel\.js"><\/script>/);
  assert.doesNotMatch(html,/<script>(?!<\/script>)/);
  assert.doesNotMatch(html,/\son\w+=/i);
});

test('background opens the panel when the toolbar button is clicked',()=>{
  assert.match(readFileSync(root+'background.js','utf8'),/setPanelBehavior\(\{\s*openPanelOnActionClick:\s*true\s*\}\)/);
});
