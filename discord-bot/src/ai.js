import {validateDraft} from './core.js';
export async function generateDraft(config, prompt){
  const url=`${config.aiBaseUrl.replace(/\/$/,'')}/chat/completions`;
  const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${config.aiKey}`},
    body:JSON.stringify({model:config.aiModel,temperature:0.45,max_tokens:config.maxOutputTokens,
      messages:[{role:'system',content:prompt.system},{role:'user',content:prompt.user}]})});
  if(!response.ok) throw new Error(`AI provider HTTP ${response.status}`);
  const data=await response.json();
  let text=data.choices?.[0]?.message?.content;
  if(Array.isArray(text)) text=text.filter(x=>x.type==='text').map(x=>x.text).join('');
  if(typeof text!=='string'||!text.trim()) throw new Error('AI provider returned no draft');
  let obj;
  try{obj=JSON.parse(text.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));}
  catch{throw new Error('AI returned invalid structured output; draft blocked');}
  if(typeof obj?.draft!=='string'||typeof obj?.why!=='string') throw new Error('AI output missing required draft/why fields');
  const draft=obj.draft.replace(/@everyone|@here/g,'[mention removed]');
  const check=validateDraft(draft);
  return {draft,why:obj.why.slice(0,180),check};
}
