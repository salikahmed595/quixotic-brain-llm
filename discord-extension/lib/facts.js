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

export function suggestFacts(messages,existing=[]){
  const seen=new Set(existing.map(f=>`${f.category}:${String(f.value||'').toLowerCase()}`));
  const out=[];
  for(const m of messages.filter(isCustomer)) for(const [category,value,statement] of factsIn(String(m.content))){
    const key=`${category}:${value.toLowerCase()}`;
    if(seen.has(key)) continue;
    seen.add(key);
    out.push({category,value,statement,source_id:String(m.id),source_text:String(m.content).slice(0,2000)});
  }
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
