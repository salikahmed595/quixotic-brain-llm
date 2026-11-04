// Builds quixotic-reply-assistant.zip (stored, no compression; ~50 KB) for the portal's install page.
// No dependencies: the portal's Docker build runs this with plain Node. Usage: node scripts/zip.js <out.zip>
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {crc32} from 'node:zlib';
import {EXTENSION_FILES} from './pack.js';

export const ZIP_FOLDER='quixotic-reply-assistant';   // the folder Windows "Extract All" makes; employees pick it in Chrome
export const ZIP_NAME=`${ZIP_FOLDER}.zip`;
const DOS_TIME=0, DOS_DATE=(2026-1980)<<9|1<<5|1;      // fixed timestamp: the same files give the same zip

export function buildZip(root){
  const locals=[],centrals=[];let offset=0;
  for(const f of EXTENSION_FILES){
    // Entries at the zip root, so Extract All gives one folder with manifest.json directly inside.
    const data=readFileSync(join(root,f)),name=Buffer.from(f,'utf8'),crc=crc32(data)>>>0;
    const head=Buffer.alloc(30);
    head.writeUInt32LE(0x04034b50,0);head.writeUInt16LE(20,4);head.writeUInt16LE(0x0800,6);head.writeUInt16LE(0,8);
    head.writeUInt16LE(DOS_TIME,10);head.writeUInt16LE(DOS_DATE,12);head.writeUInt32LE(crc,14);
    head.writeUInt32LE(data.length,18);head.writeUInt32LE(data.length,22);head.writeUInt16LE(name.length,26);head.writeUInt16LE(0,28);
    const cen=Buffer.alloc(46);
    cen.writeUInt32LE(0x02014b50,0);cen.writeUInt16LE(20,4);cen.writeUInt16LE(20,6);cen.writeUInt16LE(0x0800,8);cen.writeUInt16LE(0,10);
    cen.writeUInt16LE(DOS_TIME,12);cen.writeUInt16LE(DOS_DATE,14);cen.writeUInt32LE(crc,16);
    cen.writeUInt32LE(data.length,20);cen.writeUInt32LE(data.length,24);cen.writeUInt16LE(name.length,28);
    cen.writeUInt32LE(offset,42);
    locals.push(head,name,data);centrals.push(cen,name);offset+=30+name.length+data.length;
  }
  const dir=Buffer.concat(centrals),end=Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50,0);end.writeUInt16LE(EXTENSION_FILES.length,8);end.writeUInt16LE(EXTENSION_FILES.length,10);
  end.writeUInt32LE(dir.length,12);end.writeUInt32LE(offset,16);
  return Buffer.concat([...locals,dir,end]);
}

export function writeZip(root,out){
  mkdirSync(dirname(out),{recursive:true});
  writeFileSync(out,buildZip(root));
}

if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])){
  const out=process.argv[2];
  if(!out) throw new Error('Usage: node scripts/zip.js <out.zip>');
  writeZip(fileURLToPath(new URL('../',import.meta.url)),resolve(out));
  console.log(`Wrote ${resolve(out)}`);
}
