// Copies only the files Chrome needs into dist/, so "Load unpacked" never picks up node_modules or tests.
import {cpSync,mkdirSync,rmSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';

export const EXTENSION_FILES=['manifest.json','background.js','panel.html','panel.js','readers/discord.js','readers/selection.js','readers/twitch.js','readers/x.js',
  'lib/auth.js','lib/client.js','lib/conversation.js','lib/draft.js','lib/guard.js','lib/labels.js','lib/quixotic.js','lib/read.js','lib/sites.js',
  'icons/icon16.png','icons/icon32.png','icons/icon48.png','icons/icon128.png'];

export function pack(root,out){
  rmSync(out,{recursive:true,force:true});
  for(const f of EXTENSION_FILES){mkdirSync(dirname(join(out,f)),{recursive:true});cpSync(join(root,f),join(out,f));}
}

if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1]){
  const root=fileURLToPath(new URL('../',import.meta.url));
  pack(root,join(root,'dist'));
  console.log(`Packed ${EXTENSION_FILES.length} files into ${join(root,'dist')}`);
}
