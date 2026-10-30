// Owner 2026-10-30 design: the profile card (client type, interest chips, sales stage) is built from the client's saved
// Mini Brain facts. Client type and stage are stored as "other" facts until the backend has its own fields
// (Client Brain S9 sales marks); docs/PRD_GAPS.md.
export const STAGES=['New','Exploring','Interested','Quote sent','Paid'];
const TAG_CATEGORIES=['game','art_preference','platform'];

const after=(f,prefix)=>f.category==='other'&&String(f.statement).startsWith(prefix)?String(f.statement).slice(prefix.length).trim():null;

export function profileOf(facts){
  let type=null,stage=null,stageFactId=null;const tags=[];
  for(const f of facts){
    type=after(f,'Client type:')??type;
    const s=after(f,'Sales stage:');if(s){stage=s;stageFactId=f.id||null;}
    if(TAG_CATEGORIES.includes(f.category)){
      const tag=f.value||String(f.statement).replace(/^Mentioned\s+/,'');
      if(tag&&!tags.some(t=>t.toLowerCase()===tag.toLowerCase())) tags.push(tag);
    }
  }
  return {type,tags,stage,stageFactId};
}

const note=text=>({status:'confirmed',source_type:'employee_note',source_id:'',source_text:text});

export function stagePayload(stage,previousFactId){
  if(!STAGES.includes(stage)) throw new Error(`Unknown stage: ${stage}`);
  const out={category:'other',value:stage,statement:`Sales stage: ${stage}`,...note('Set by an employee in the reply assistant')};
  if(previousFactId) out.supersedes_memory_id=previousFactId;
  return out;
}

export function noteFact({category,text}){
  const t=String(text||'').replace(/\s+/g,' ').trim();
  if(!t) throw new Error('Type what you know about the client first.');
  return {category,value:'',statement:t.slice(0,500),...note(t.slice(0,2000))};
}
