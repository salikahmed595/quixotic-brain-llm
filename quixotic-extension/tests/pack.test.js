import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync,existsSync,rmSync,readdirSync,statSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {EXTENSION_FILES,pack} from '../scripts/pack.js';

const root=fileURLToPath(new URL('../',import.meta.url));
const manifest=JSON.parse(readFileSync(root+'manifest.json','utf8'));

test('pack list covers every file the extension loads',()=>{
  const needed=new Set(['manifest.json',manifest.background.service_worker,manifest.side_panel.default_path,'panel.js']);
  for(const f of readdirSync(root+'readers')) needed.add('readers/'+f);   // injected by panel.js on click
  for(const f of readdirSync(root+'lib')) needed.add('lib/'+f);   // panel.js imports from lib/
  for(const f of Object.values(manifest.icons)) needed.add(f);
  for(const f of needed) assert.ok(EXTENSION_FILES.includes(f),`missing ${f}`);
});

test('pack copies only extension files into dist/ (no node_modules, tests or package files)',()=>{
  const out=join(root,'dist');
  rmSync(out,{recursive:true,force:true});
  pack(root,out);
  const walk=d=>readdirSync(d).flatMap(n=>statSync(join(d,n)).isDirectory()?walk(join(d,n)).map(x=>n+'/'+x):[n]);
  assert.deepEqual(walk(out).sort(),[...EXTENSION_FILES].sort());
  assert.equal(readFileSync(join(out,'manifest.json'),'utf8'),readFileSync(root+'manifest.json','utf8'));
  rmSync(out,{recursive:true,force:true});
  assert.ok(!existsSync(out));
});
