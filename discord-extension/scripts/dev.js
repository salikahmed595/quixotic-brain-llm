// Dev copy for the folder loaded in Chrome: the extension files plus dev-reload.js, so it updates itself when they change.
// Usage: node scripts/dev.js <folder loaded in Chrome> [--watch]
import {cpSync,mkdirSync,readFileSync,writeFileSync,watch} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {EXTENSION_FILES} from './pack.js';

const isPanel=f=>f==='panel.html'||f==='panel.js'||f.startsWith('lib/')||f.startsWith('readers/');   // read fresh on panel reload or click
const hash=(root,files)=>{const h=createHash('sha256');for(const f of files) h.update(f+'\0').update(readFileSync(join(root,f)));return h.digest('hex').slice(0,16);};

export function devBuild(root,out){
  // Overwrite in place (no delete): Chrome keeps the folder loaded the whole time.
  for(const f of EXTENSION_FILES){mkdirSync(dirname(join(out,f)),{recursive:true});cpSync(join(root,f),join(out,f));}
  cpSync(join(root,'scripts/dev-reload.js'),join(out,'dev-reload.js'));
  const html=readFileSync(join(root,'panel.html'),'utf8').replace('<script type="module" src="panel.js"></script>',
    '<script src="dev-reload.js"></script>\n  <script type="module" src="panel.js"></script>');
  writeFileSync(join(out,'panel.html'),html);
  const stamp={panel:hash(root,EXTENSION_FILES.filter(isPanel)),core:hash(root,EXTENSION_FILES.filter(f=>!isPanel(f)))};
  writeFileSync(join(out,'dev-stamp.json'),JSON.stringify(stamp)+'\n');   // written last, so a stamp change means the copy is complete
  return stamp;
}

if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])){
  const out=process.argv[2];
  if(!out) throw new Error('Usage: node scripts/dev.js <folder loaded in Chrome> [--watch]');
  const root=fileURLToPath(new URL('../',import.meta.url)),target=resolve(out);
  const build=()=>{try{devBuild(root,target);console.log(`Updated ${target} ${new Date().toLocaleTimeString()}`);}catch(e){console.error(e.message);}};
  build();
  if(process.argv.includes('--watch')){
    let t;watch(root,{recursive:true},(_,f)=>{
      if(!f||/node_modules|dist|tests|\.git/.test(f)) return;
      clearTimeout(t);t=setTimeout(build,300);
    });
    console.log('Watching for changes. Ctrl+C to stop.');
  }
}
