import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {crc32} from 'node:zlib';
import {buildZip,ZIP_FOLDER} from '../scripts/zip.js';
import {EXTENSION_FILES} from '../scripts/pack.js';

const root=fileURLToPath(new URL('../',import.meta.url));

// Minimal reader: walk the central directory and check each stored entry against its local copy.
function readZip(buf){
  const eocd=buf.lastIndexOf(Buffer.from([0x50,0x4b,0x05,0x06]));
  assert.ok(eocd>=0,'end of central directory');
  const count=buf.readUInt16LE(eocd+10);let p=buf.readUInt32LE(eocd+16);const out={};
  for(let i=0;i<count;i++){
    assert.equal(buf.readUInt32LE(p),0x02014b50);
    const method=buf.readUInt16LE(p+10),crc=buf.readUInt32LE(p+16),size=buf.readUInt32LE(p+24);
    const nameLen=buf.readUInt16LE(p+28),extra=buf.readUInt16LE(p+30),comment=buf.readUInt16LE(p+32),local=buf.readUInt32LE(p+42);
    const name=buf.toString('utf8',p+46,p+46+nameLen);
    assert.equal(buf.readUInt32LE(local),0x04034b50);
    const start=local+30+buf.readUInt16LE(local+26)+buf.readUInt16LE(local+28);
    const data=buf.subarray(start,start+size);
    out[name]={method,crc,data};p+=46+nameLen+extra+comment;
  }
  return out;
}

test('zip holds every extension file inside one folder, byte-for-byte with valid CRCs',()=>{
  const entries=readZip(buildZip(root));
  assert.deepEqual(Object.keys(entries).sort(),EXTENSION_FILES.map(f=>`${ZIP_FOLDER}/${f}`).sort());
  for(const f of EXTENSION_FILES){
    const e=entries[`${ZIP_FOLDER}/${f}`],src=readFileSync(join(root,f));
    assert.equal(e.method,0);assert.ok(e.data.equals(src),f);assert.equal(e.crc,crc32(src)>>>0,f);
  }
});

test('zip is written to the given path (the portal build puts it in web/public/downloads)',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'qzip-'));
  try{
    const {writeZip}=await import('../scripts/zip.js');
    const out=join(dir,'nested','quixotic-reply-assistant.zip');
    writeZip(root,out);
    assert.ok(readFileSync(out).equals(buildZip(root)));
  }finally{rmSync(dir,{recursive:true,force:true});}
});
