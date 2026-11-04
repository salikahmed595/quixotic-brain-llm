// Thin client for Quixotic AI: the bot never calls an LLM itself, so permissions, department filters and the
// approved-evidence rule stay server-side (CLAUDE.md Rule 2). Contract: backend/api/v1/ask.py (PRD §38 shape).
const REQUIRED=['QUIXOTIC_API_URL','QUIXOTIC_API_KEY','STAFF_USER_MAP'];

export function loadQuixoticConfig(env=process.env){
  const missing=REQUIRED.filter(k=>!env[k]||!String(env[k]).trim());
  if(missing.length) throw new Error(`Missing required setting(s): ${missing.join(', ')}`);
  // PRD gap: the PRD does not say how a Discord staff account maps to a Quixotic employee; explicit map, no default.
  let map;
  try{map=JSON.parse(env.STAFF_USER_MAP);}catch{throw new Error('STAFF_USER_MAP must be a JSON object {"discordUserId":"quixoticUserId"}');}
  if(!map||typeof map!=='object'||Array.isArray(map)||Object.values(map).some(v=>typeof v!=='string'||!v.trim()))
    throw new Error('STAFF_USER_MAP must be a JSON object {"discordUserId":"quixoticUserId"}');
  return {apiUrl:env.QUIXOTIC_API_URL.replace(/\/+$/,''),apiKey:env.QUIXOTIC_API_KEY,staffUserMap:map};
}

export class NotLinkedError extends Error{
  constructor(){super('Your Discord account is not linked to a Quixotic AI employee. Ask an admin to add you.');}
}

export function resolveUserId(config,discordUserId){
  // Without user_id the API would act as the key's creator; refuse rather than borrow someone else's permissions.
  const id=config.staffUserMap[discordUserId];
  if(!id) throw new NotLinkedError();
  return id;
}

export async function askQuixotic(config,{question,discordUserId,mode='general'},fetchFn=fetch){
  const userId=resolveUserId(config,discordUserId);
  const response=await fetchFn(`${config.apiUrl}/v1/ask`,{method:'POST',
    headers:{'Content-Type':'application/json','X-API-Key':config.apiKey},
    body:JSON.stringify({question,user_id:userId,mode})});
  if(!response.ok) throw new Error(`Quixotic AI HTTP ${response.status}`);
  const data=await response.json();
  if(typeof data?.answer!=='string'||!data.answer.trim()) throw new Error('Quixotic AI returned no answer');
  return {queryId:data.query_id,answer:data.answer,confidence:data.confidence};
}
