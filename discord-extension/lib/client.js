// Client Brain step 1 (owner 2026-10-30): recognise the customer of the open chat and show their Mini Brain from
// /v1/clients (backend/api/v1/clients.py, department-scoped on the server). A client is created only when the
// employee clicks; facts are saved only after an employee confirms them (docs/PRD_GAPS.md).
import {parseStaffNames,labelMessages} from './labels.js';

export const FACT_LABELS={art_preference:'Art style',platform:'Platform',game:'Games',communication:'How they talk',
  budget:'Budget',deadline:'Deadline',commitment:'Promised',objection:'Concern',other:'Note'};

export function customerOf(messages,staffNames){
  const m=labelMessages(messages,parseStaffNames(staffNames))
    .filter(x=>!x.isBot&&!x.isStaff&&String(x.author||'').trim()&&String(x.content||'').trim()).at(-1);
  return m?{name:m.author.trim(),discordId:m.authorId||''}:null;
}

// Discord id is the strong match; an exact name only matches a client saved without an id (same name may be someone else).
export function matchClient(clients,customer){
  const byId=customer.discordId&&clients.find(c=>c.discord_handle===customer.discordId);
  if(byId) return byId;
  const name=customer.name.toLowerCase();
  return clients.find(c=>!c.discord_handle&&String(c.display_name).toLowerCase()===name)||null;
}

export function makeApi({apiUrl,csrf,fetchFn=fetch}){
  const base=String(apiUrl).replace(/\/+$/,'');
  return async(path,{method='GET',body}={})=>{
    const res=await fetchFn(base+path,{method,credentials:'include',
      headers:{'Content-Type':'application/json','X-CSRF-Token':csrf||''},body:body===undefined?undefined:JSON.stringify(body)});
    if(res.status===401) throw new Error('Please sign in to Quixotic AI again.');
    let data={};try{data=await res.json();}catch{/* 204 or empty */}
    if(!res.ok) throw new Error(typeof data?.detail==='string'?data.detail:`Quixotic AI HTTP ${res.status}`);
    return data;
  };
}

export async function lookupClient({customer,api}){
  const {clients=[]}=await api(`/v1/clients?q=${encodeURIComponent(customer.discordId||customer.name)}`);
  const found=matchClient(clients,customer);
  if(!found) return {client:null,facts:[]};
  const {client,facts=[]}=await api(`/v1/clients/${found.id}`);
  return {client,facts};
}

export async function createClient({customer,department,api}){
  const body={display_name:customer.name,discord_handle:customer.discordId||null};
  if(department) body.department=department;
  return {client:await api('/v1/clients',{method:'POST',body}),facts:[]};
}
