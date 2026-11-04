// Client Brain step 2 (owner 2026-10-30): suggests facts from the customer's own messages, each with the exact
// message it came from. Nothing is saved until the employee ticks it. Plain rules (no AI), so nothing is invented;
// to be replaced by the backend suggestion slice (Client Brain S3) when it lands. Categories: backend/client_memory/rules.py.
const GAMES=[['Valorant',/\bvalorant\b|\bval\b/],['Fortnite',/\bfortnite\b/],['Call of Duty',/\bcall of duty\b|\bcod\b|\bwarzone\b/],
  ['Apex Legends',/\bapex\b/],['Minecraft',/\bminecraft\b/],['League of Legends',/\bleague of legends\b/],['Counter-Strike',/\bcs2\b|\bcsgo\b|\bcounter[- ]?strike\b/],
  ['GTA',/\bgta\b/],['Roblox',/\broblox\b/],['Overwatch',/\boverwatch\b/],['Rocket League',/\brocket league\b/],['Dota 2',/\bdota\b/],
  ['Genshin Impact',/\bgenshin\b/],['Elden Ring',/\belden ring\b/],['PUBG',/\bpubg\b/],['Rainbow Six Siege',/\brainbow six\b|\br6\b/],['Marvel Rivals',/\bmarvel rivals\b/]];
const PLATFORMS=[['Twitch',/\btwitch\b/],['YouTube',/\byoutube\b|\byt\b/],['Kick',/\bon kick\b|\bkick stream/],['TikTok',/\btiktok\b/],
  ['Instagram',/\binstagram\b|\binsta\b/],['Twitter/X',/\btwitter\b/],['Facebook',/\bfacebook\b/]];
const ART=['emote','banner','overlay','logo','pfp','panel','thumbnail','chibi','anime','cartoon','pixel art','vtuber','mascot','sticker',
  'sub badge','alert','illustration','3d','realistic','cute'];
const COLOURS=['red','orange','yellow','green','blue','purple','pink','black','white','gold','silver','teal','neon','pastel'];
const COLOUR_CONTEXT=new RegExp(String.raw`\b(${ART.join('|')}|colou?rs?|vibe|theme)s?\b`);
const BUDGET=[/\$\s?(\d{1,5}(?:\.\d{1,2})?)/,/\b(\d{1,5})\s?(?:usd|dollars?|bucks)\b/,/\bbudget\s*(?:is|of|:|around|~)?\s*\$?(\d{1,5})\b/];
const DEADLINE=/\b(?:by|before|until)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|next week|the weekend|end of (?:the )?(?:week|month))\b|\basap\b/;
const CONCERNS=[['sales pitch',/\btrying to sell\b|\bselling me\b|\bsales ?pitch\b/],['not interested',/\bnot (?:interested|buying)\b/],
  ['price',/\btoo (?:expensive|much|pricey)\b|\bcan'?t afford\b|\bcheaper\b/],['trust',/\bscam\b|\bis this legit\b|\bcan i trust\b/]];

const isCustomer=m=>!m.isBot&&!m.isStaff&&String(m.content||'').trim();
const word=w=>new RegExp(String.raw`\b${w}s?\b`);

function factsIn(text){
  const t=text.toLowerCase(),out=[];
  for(const [name,re] of GAMES) if(re.test(t)) out.push(['game',name,`Mentioned ${name}`]);
  for(const [name,re] of PLATFORMS) if(re.test(t)) out.push(['platform',name,`Mentioned ${name}`]);
  for(const a of ART) if(word(a).test(t)) out.push(['art_preference',a,`Mentioned ${a}`]);
  if(COLOUR_CONTEXT.test(t)) for(const c of COLOURS) if(word(c).test(t)) out.push(['art_preference',c,`Mentioned ${c}`]);
  for(const re of BUDGET){const m=t.match(re);if(m){out.push(['budget',`$${m[1]}`,`Mentioned a budget of $${m[1]}`]);break;}}
  const d=t.match(DEADLINE);if(d) out.push(['deadline',d[0],`Mentioned a deadline: ${d[0]}`]);
  for(const [name,re] of CONCERNS) if(re.test(t)) out.push(['objection',name,`Concern: ${name}`]);
  return out;
}

// Client type from what they say about themselves (owner 2026-10-30: "what is the client type").
const TYPES=[['Streamer',/\bmy (?:stream|streams|twitch|kick)\b|\bi stream\b|\bwhen i(?:'m| am)? live\b|\bmy viewers\b/],
  ['Content creator',/\bmy (?:channel|youtube|tiktok|videos?|content)\b/],['Business',/\bmy (?:business|company|brand|shop|store)\b/]];
// How they write, from the words they actually use; never personality guesses (backend/client_memory/rules.py).
const SLANG=['yo','bro','ngl','fr','lol','lmao','rn','u','ur','tbh','bet','fam','lowkey','bruh','pls','imo'];
const EMOJI=/\p{Extended_Pictographic}/u;

function styleFacts(msgs){
  const out=[],texts=msgs.map(m=>String(m.content));
  const used=SLANG.filter(s=>texts.some(t=>new RegExp(String.raw`(^|[^\w'])${s}($|[^\w'])`,'i').test(t)));
  if(used.length>=2){const m=msgs.find(x=>used.some(s=>new RegExp(String.raw`(^|[^\w'])${s}($|[^\w'])`,'i').test(x.content)));
    out.push([m,'slang',`Writes casually with slang (${used.slice(0,5).join(', ')})`]);}
  const e=msgs.find(x=>EMOJI.test(x.content));if(e) out.push([e,'emoji','Uses emoji']);
  const words=texts.map(t=>t.trim().split(/\s+/).length);
  if(msgs.length>=3&&words.reduce((a,b)=>a+b,0)/words.length<=8) out.push([msgs.at(-1),'short messages','Writes short messages']);
  return out.map(([m,value,statement])=>['communication',value,statement,m]);
}

export function suggestFacts(messages,existing=[]){
  const seen=new Set(existing.map(f=>`${f.category}:${String(f.value||'').toLowerCase()}`));
  for(const f of existing){const t=String(f.statement).match(/^Client type:\s*(.+)$/);if(t) seen.add(`other:${t[1].toLowerCase()}`);}
  const out=[],msgs=messages.filter(isCustomer);
  const add=(category,value,statement,m)=>{
    const key=`${category}:${value.toLowerCase()}`;
    if(seen.has(key)) return;
    seen.add(key);
    out.push({category,value,statement,source_id:String(m.id),source_text:String(m.content).slice(0,2000)});
  };
  for(const [name,re] of TYPES){const m=msgs.find(x=>re.test(String(x.content).toLowerCase()));if(m){add('other',name,`Client type: ${name}`,m);break;}}
  for(const m of msgs) for(const [category,value,statement] of factsIn(String(m.content))) add(category,value,statement,m);
  for(const [category,value,statement,m] of styleFacts(msgs)) add(category,value,statement,m);
  return out;
}

// The employee ticked it, so it is confirmed. Only Discord gives a real message id; other apps keep the quoted text.
export function factPayload(f,app){
  const discord=app==='Discord';
  return {category:f.category,statement:f.statement,value:f.value,status:'confirmed',
    source_type:discord?'discord_message':'employee_note',source_id:discord?f.source_id:'',
    source_text:discord?f.source_text:`${app?`${app} chat`:'Chat'}: ${f.source_text}`.slice(0,2000)};
}

export async function saveFacts({clientId,facts,app,api}){
  let saved=0;const errors=[];
  for(const f of facts){
    try{await api(`/v1/clients/${clientId}/memories`,{method:'POST',body:factPayload(f,app)});saved++;}
    catch(e){errors.push(`${f.value}: ${e.message}`);}
  }
  return {saved,errors};
}
