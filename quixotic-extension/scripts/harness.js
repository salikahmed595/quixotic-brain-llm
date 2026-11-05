// Local test page: serves the real panel with a fake chrome API and a fake Quixotic AI, so its screens can be clicked
// through in a normal browser without Chrome's extension system or a server. Test tool only; never packed or deployed.
// Run: node scripts/harness.js   Then set window.__chat and window.__answers from the page before clicking Suggest Reply.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {join,extname,normalize} from 'node:path';
import {fileURLToPath} from 'node:url';

const ROOT=fileURLToPath(new URL('..',import.meta.url));
const PORT=Number(process.env.PORT||8765);
const TYPES={'.html':'text/html','.js':'text/javascript','.png':'image/png','.json':'application/json'};

const FAKES=`<script>
window.__chat=[{id:'1',author:'fox',content:"my overlays don't match the fox theme"}];
window.__answers=['1. Makes sense, cute and cozy or more dark fantasy?\\n2. Cute or dark fantasy?\\n3. That makes sense, what vibe are you going for?'];
window.__asks=[];
const store={csrf:'test',staffNames:'Sara'};
window.chrome={
  storage:{local:{get:async k=>Object.fromEntries([k].flat().map(x=>[x,store[x]])),set:async o=>{Object.assign(store,o);},remove:async k=>{delete store[k];}}},
  tabs:{query:async()=>[{id:1,url:'https://discord.com/channels/@me/1'}]},
  permissions:{contains:async()=>true,request:async()=>true},
  scripting:{executeScript:async({func})=>func?[{result:window.__chat}]:[{}]},
  runtime:{reload(){},getURL:p=>p}
};
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
window.fetch=async(url,init={})=>{
  const u=String(url);
  if(u.includes('/v1/ask')){const q=JSON.parse(init.body).question;window.__asks.push(q);
    return json({answer:window.__answers[Math.min(window.__asks.length,window.__answers.length)-1],confidence:'high'});}
  if(u.includes('/v1/auth/me')) return json({departments:[{id:'d1',name:'Sales'}]});
  if(u.includes('/v1/clients')) return json({clients:[],items:[]});
  return json({});
};
</script>`;

createServer(async(req,res)=>{
  const path=normalize(decodeURIComponent(new URL(req.url,'http://x').pathname)).replace(/^[\\/]+/,'')||'panel.html';
  if(path.includes('..')||path.startsWith('node_modules')){res.writeHead(403).end();return;}
  try{
    let body=await readFile(join(ROOT,path));
    if(path==='panel.html') body=String(body).replace('<head>','<head>'+FAKES);
    res.writeHead(200,{'Content-Type':TYPES[extname(path)]||'text/plain'}).end(body);
  }catch{res.writeHead(404).end();}
}).listen(PORT,'127.0.0.1',()=>console.log(`Panel test page: http://localhost:${PORT}/panel.html`));
