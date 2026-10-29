import test from 'node:test';import assert from 'node:assert/strict';
import {syncHistory} from '../src/discordHistory.js';
function fixture(count){
 const all=Array.from({length:count},(_,i)=>({id:String(i+1000),guildId:'g',channelId:'c',content:'a valid customer message',author:{id:'cust',username:'customer',bot:false},createdAt:new Date(1700000000000+i*1000)}));
 const index=new Map();let complete=false;
 const store={
  getBounds(){const arr=[...index.values()].sort((a,b)=>BigInt(a.id)<BigInt(b.id)?-1:1);return {newest:arr.at(-1)?.id,oldest:arr[0]?.id,complete};},
  saveMessage(m){index.set(m.id,m);},
  markComplete(){complete=true;}
 };
 const channel={guildId:'g',id:'c',messages:{async fetch({limit,before}){
   const values=all.filter(m=>!before||BigInt(m.id)<BigInt(before)).sort((a,b)=>BigInt(a.id)>BigInt(b.id)?-1:1).slice(0,limit);
   return new Map(values.map(m=>[m.id,m]));
 }}};
 return {store,channel,index};
}
test('multi-page backfill reads all accessible history and marks complete',async()=>{
 const {store,channel,index}=fixture(215);const r=await syncHistory(channel,store,10);
 assert.equal(index.size,215);assert.equal(r.complete,true);
});
test('large history resumes from stored oldest cursor rather than losing older messages',async()=>{
 const {store,channel,index}=fixture(315);
 const first=await syncHistory(channel,store,2);assert.equal(first.complete,false);assert.equal(index.size,200);
 const second=await syncHistory(channel,store,3);assert.equal(second.complete,true);assert.equal(index.size,315);
});
