import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync,existsSync,mkdtempSync,rmSync,writeFileSync,cpSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {devBuild} from '../scripts/dev.js';
import {pack} from '../scripts/pack.js';

const root=fileURLToPath(new URL('../',import.meta.url));
const tmp=()=>mkdtempSync(join(tmpdir(),'qdev-'));

// Owner 2026-10-30: the copy loaded in Chrome updates itself when files change, without clicking Reload.
test('dev build adds the auto-update script and a version stamp to the loaded folder',()=>{
  const out=tmp();
  try{
    devBuild(root,out);
    assert.ok(existsSync(join(out,'dev-reload.js')));
    assert.match(readFileSync(join(out,'panel.html'),'utf8'),/<script src="dev-reload\.js"><\/script>\s*<script type="module" src="panel\.js">/);
    const stamp=JSON.parse(readFileSync(join(out,'dev-stamp.json'),'utf8'));
    assert.match(stamp.panel,/^[0-9a-f]{16}$/);assert.match(stamp.core,/^[0-9a-f]{16}$/);
    assert.equal(readFileSync(join(out,'manifest.json'),'utf8'),readFileSync(join(root,'manifest.json'),'utf8'));
  }finally{rmSync(out,{recursive:true,force:true});}
});

test('stamp: panel-only edits change "panel"; manifest or content-script edits change "core"',()=>{
  const src=tmp(),a=tmp(),b=tmp(),c=tmp();
  try{
    pack(root,src);cpSync(join(root,'scripts'),join(src,'scripts'),{recursive:true});
    devBuild(src,a);
    writeFileSync(join(src,'panel.js'),readFileSync(join(src,'panel.js'),'utf8')+'\n// edit');devBuild(src,b);
    writeFileSync(join(src,'reader.js'),readFileSync(join(src,'reader.js'),'utf8')+'\n// edit');devBuild(src,c);
    const s=d=>JSON.parse(readFileSync(join(d,'dev-stamp.json'),'utf8'));
    assert.notEqual(s(a).panel,s(b).panel);assert.equal(s(a).core,s(b).core);
    assert.notEqual(s(b).core,s(c).core);
  }finally{for(const d of [src,a,b,c]) rmSync(d,{recursive:true,force:true});}
});

test('employee download never contains the dev auto-update script',()=>{
  const out=tmp();
  try{pack(root,out);assert.ok(!existsSync(join(out,'dev-reload.js')));assert.doesNotMatch(readFileSync(join(out,'panel.html'),'utf8'),/dev-reload/);}
  finally{rmSync(out,{recursive:true,force:true});}
});

test('auto-update script only polls its own stamp file and reloads the extension',()=>{
  const js=readFileSync(join(root,'scripts/dev-reload.js'),'utf8');
  assert.match(js,/chrome\.runtime\.getURL\('dev-stamp\.json'\)/);
  assert.match(js,/chrome\.runtime\.reload\(\)/);
  assert.doesNotMatch(js,/https?:\/\//);
});
