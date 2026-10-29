/** Fetch by Discord's 100-message pages. Preserves a cursor to resume large backfills. */
export async function syncHistory(channel,store,limitPages=100,authorAllowed=async()=>true){
  const g=channel.guildId,c=channel.id; if(!g) throw new Error('Only configured server channels supported');
  const initial=store.getBounds(g,c);
  let pages=0,added=0,catchupComplete=true;
  let cursor;
  // Catch up missed messages since last stored message (when bot was offline).
  while(pages<limitPages){
    const params={limit:100};if(cursor) params.before=cursor;
    const batch=await channel.messages.fetch(params);pages++;
    if(!batch.size) break;
    const arr=[...batch.values()];
    for(const m of arr){if(!initial.newest||BigInt(m.id)>BigInt(initial.newest)) {if(await save(store,m,authorAllowed)) added++;}}
    const oldest=arr.reduce((a,b)=>BigInt(a.id)<BigInt(b.id)?a:b);
    cursor=oldest.id;
    if((initial.newest && BigInt(cursor)<=BigInt(initial.newest)) || batch.size<100) break;
  }
  if(pages===limitPages && initial.newest && cursor && BigInt(cursor)>BigInt(initial.newest)) catchupComplete=false;
  // On initial indexing, the previous loop may have reached oldest. For later calls,
  // continue historical backfill from previously stored oldest, not newest again.
  const bounds=store.getBounds(g,c);
  let backfillCursor=initial.oldest || bounds.oldest;
  if(!initial.oldest && bounds.oldest && pages<limitPages){
    // Initial fetch may have had to stop at page limit. Continue in next command.
    if(cursor && BigInt(cursor)<=BigInt(bounds.oldest)) backfillCursor=cursor;
  }
  if(!initial.complete && backfillCursor){
    while(pages<limitPages){
      const batch=await channel.messages.fetch({limit:100,before:backfillCursor});pages++;
      if(!batch.size){store.markComplete(g,c);break;}
      const arr=[...batch.values()];
      for(const m of arr){if(await save(store,m,authorAllowed)) added++;}
      backfillCursor=arr.reduce((a,b)=>BigInt(a.id)<BigInt(b.id)?a:b).id;
      if(batch.size<100){store.markComplete(g,c);break;}
    }
  }else if(!initial.complete && !backfillCursor){store.markComplete(g,c);}
  return {pages,added,complete:store.getBounds(g,c).complete&&catchupComplete,catchupComplete};
}
async function save(store,m,authorAllowed){
  if(m.author?.bot || !(await authorAllowed(m))) return false;
  store.saveMessage({guildId:m.guildId,channelId:m.channelId,id:m.id,authorId:m.author.id,
    authorName:m.author.username||m.author.globalName||'User',content:m.content||'',
    createdAt:(m.createdAt||new Date()).toISOString(),isBot:false});
  return true;
}
