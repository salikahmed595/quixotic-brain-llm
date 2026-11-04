// Splits the suggested reply so the client's known interests can be shown in orange (owner design 2026-10-30).
const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');

export function highlightParts(text,terms){
  const list=[...new Set(terms.map(t=>String(t).trim()).filter(t=>t.length>1))].sort((a,b)=>b.length-a.length);
  if(!list.length) return [{text,hit:false}];
  const re=new RegExp(`(${list.map(escape).join('|')})`,'gi');
  return text.split(re).filter(Boolean).map(part=>({text:part,hit:list.some(t=>t.toLowerCase()===part.toLowerCase())}));
}
