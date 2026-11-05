import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {ICON_SIZES,drawIcon,encodePng} from '../scripts/icons.js';

const root=fileURLToPath(new URL('../',import.meta.url));
const manifest=JSON.parse(readFileSync(root+'manifest.json','utf8'));
const pngSize=buf=>({sig:buf.subarray(0,8).toString('hex'),w:buf.readUInt32BE(16),h:buf.readUInt32BE(20)});

// Without icons Chrome shows a grey letter on the toolbar; the orange Q makes the helper easy to find.
test('manifest gives Chrome an orange icon for the toolbar and the extensions page',()=>{
  for(const s of ICON_SIZES){
    const f=`icons/icon${s}.png`;
    assert.equal(manifest.icons[s],f);assert.equal(manifest.action.default_icon[s],f);
    assert.ok(existsSync(root+f),f);
    assert.deepEqual(pngSize(readFileSync(root+f)),{sig:'89504e470d0a1a0a',w:s,h:s});
  }
});

test('committed icons match the generator (run node scripts/icons.js after changing it)',()=>{
  for(const s of ICON_SIZES) assert.ok(readFileSync(root+`icons/icon${s}.png`).equals(encodePng(s,drawIcon(s))),String(s));
});

test('icon is orange in the middle of the badge and transparent in the corner',()=>{
  const s=128,px=drawIcon(s),at=(x,y)=>[...px.subarray((y*s+x)*4,(y*s+x)*4+4)];
  assert.equal(at(0,0)[3],0);
  const [r,g,b,a]=at(20,64);assert.equal(a,255);assert.ok(r>200&&g<160&&b<90,`orange, got ${r},${g},${b}`);
  assert.deepEqual(at(64,64-Math.round(s*0.27)+4).slice(0,3),[255,255,255]);   // white ring of the Q
});
