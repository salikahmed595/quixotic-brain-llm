import Database from 'better-sqlite3';
import {mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {extractExplicitFacts} from './core.js';
export class Store {
  constructor(path) {
    mkdirSync(dirname(path),{recursive:true}); this.db=new Database(path);
    this.db.pragma('journal_mode = WAL');
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS channel_links(
        guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, customer_id TEXT NOT NULL,
        linked_by TEXT NOT NULL, linked_at TEXT NOT NULL, consent_at TEXT,
        PRIMARY KEY (guild_id,channel_id));
      CREATE TABLE IF NOT EXISTS messages(
        guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, id TEXT PRIMARY KEY,
        author_id TEXT NOT NULL, author_name TEXT NOT NULL, content TEXT NOT NULL,
        created_at TEXT NOT NULL, is_bot INTEGER NOT NULL DEFAULT 0);
      CREATE INDEX IF NOT EXISTS msg_channel_idx ON messages(guild_id,channel_id,created_at,id);
      CREATE TABLE IF NOT EXISTS facts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL, customer_id TEXT NOT NULL, key TEXT NOT NULL,
        value TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL,
        evidence TEXT NOT NULL, source_message_id TEXT NOT NULL,
        observed_at TEXT NOT NULL, UNIQUE(source_message_id,key,value));
      CREATE INDEX IF NOT EXISTS facts_idx ON facts(guild_id,channel_id,customer_id,key,observed_at);
      CREATE TABLE IF NOT EXISTS channel_state(
        guild_id TEXT NOT NULL,channel_id TEXT NOT NULL, backfill_complete INTEGER DEFAULT 0,
        PRIMARY KEY(guild_id,channel_id));
      CREATE TABLE IF NOT EXISTS draft_audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id TEXT NOT NULL,channel_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,employee_id TEXT NOT NULL,source_message_id TEXT,
        state TEXT NOT NULL,created_at TEXT NOT NULL,model TEXT NOT NULL,
        risk_reason TEXT NOT NULL DEFAULT '');
    `);
  }
  link(guildId,channelId,customerId,actorId) {
    this.db.prepare(`INSERT INTO channel_links(guild_id,channel_id,customer_id,linked_by,linked_at,consent_at) VALUES (?,?,?,?,?,NULL) ON CONFLICT(guild_id,channel_id)
      DO UPDATE SET customer_id=excluded.customer_id,linked_by=excluded.linked_by,linked_at=excluded.linked_at,consent_at=NULL`)
      .run(guildId,channelId,customerId,actorId,new Date().toISOString());
  }
  grantConsent(guildId,channelId,customerId) {
    return this.db.prepare('UPDATE channel_links SET consent_at=? WHERE guild_id=? AND channel_id=? AND customer_id=? AND consent_at IS NULL').run(new Date().toISOString(),guildId,channelId,customerId).changes>0;
  }
  getLink(guildId,channelId){return this.db.prepare('SELECT * FROM channel_links WHERE guild_id=? AND channel_id=?').get(guildId,channelId);}
  saveMessage(m) {
    if(!m.content?.trim() || m.isBot) return;
    const info=this.db.prepare('INSERT OR IGNORE INTO messages VALUES (?,?,?,?,?,?,?,?)').run(m.guildId,m.channelId,m.id,m.authorId,m.authorName||'User',m.content.slice(0,12000),m.createdAt,0);
    const link=this.getLink(m.guildId,m.channelId);
    if(info.changes && link?.customer_id===m.authorId){
      const insert=this.db.prepare(`INSERT OR IGNORE INTO facts(guild_id,channel_id,customer_id,key,value,status,scope,evidence,source_message_id,observed_at) VALUES (?,?,?,?,?,?,?,?,?,?)`);
      for(const f of extractExplicitFacts(m.content)) insert.run(m.guildId,m.channelId,m.authorId,f.key,f.value,f.status,f.scope,f.evidence,m.id,m.createdAt);
    }
  }
  recalculateFacts(guildId,channelId){
    const link=this.getLink(guildId,channelId);if(!link) return;
    this.db.prepare('DELETE FROM facts WHERE guild_id=? AND channel_id=?').run(guildId,channelId);
    const insert=this.db.prepare(`INSERT OR IGNORE INTO facts(guild_id,channel_id,customer_id,key,value,status,scope,evidence,source_message_id,observed_at) VALUES (?,?,?,?,?,?,?,?,?,?)`);
    for(const m of this.getMessages(guildId,channelId)) if(m.authorId===link.customer_id)
      for(const f of extractExplicitFacts(m.content)) insert.run(guildId,channelId,link.customer_id,f.key,f.value,f.status,f.scope,f.evidence,m.id,m.createdAt);
  }
  getMessages(guildId,channelId){
    return this.db.prepare('SELECT id,author_id AS authorId,author_name AS authorName,content,created_at AS createdAt,is_bot AS isBot FROM messages WHERE guild_id=? AND channel_id=? ORDER BY created_at ASC,id ASC').all(guildId,channelId);
  }
  getBounds(guildId,channelId){
    const newest=this.db.prepare('SELECT id FROM messages WHERE guild_id=? AND channel_id=? ORDER BY created_at DESC,id DESC LIMIT 1').get(guildId,channelId)?.id;
    const oldest=this.db.prepare('SELECT id FROM messages WHERE guild_id=? AND channel_id=? ORDER BY created_at ASC,id ASC LIMIT 1').get(guildId,channelId)?.id;
    const complete=!!this.db.prepare('SELECT backfill_complete FROM channel_state WHERE guild_id=? AND channel_id=?').get(guildId,channelId)?.backfill_complete;
    return {newest,oldest,complete};
  }
  markComplete(guildId,channelId){this.db.prepare('INSERT INTO channel_state VALUES (?,?,1) ON CONFLICT(guild_id,channel_id) DO UPDATE SET backfill_complete=1').run(guildId,channelId);}
  currentFacts(guildId,channelId,customerId){
    const rows=this.db.prepare('SELECT key,value,status,scope,evidence,source_message_id AS sourceMessageId,observed_at AS observedAt FROM facts WHERE guild_id=? AND channel_id=? AND customer_id=? ORDER BY observed_at DESC,id DESC').all(guildId,channelId,customerId);
    return rows.filter((r,i)=>rows.findIndex(x=>x.key===r.key)===i).slice(0,40);
  }
  audit(x){this.db.prepare('INSERT INTO draft_audit(guild_id,channel_id,customer_id,employee_id,source_message_id,state,created_at,model,risk_reason) VALUES (?,?,?,?,?,?,?,?,?)').run(x.guildId,x.channelId,x.customerId,x.employeeId,x.sourceMessageId||null,x.state,new Date().toISOString(),x.model,x.riskReason||'');}
  forget(guildId,channelId){
    const del=this.db.transaction(()=>{
      for(const table of ['facts','messages','draft_audit','channel_state','channel_links']) this.db.prepare(`DELETE FROM ${table} WHERE guild_id=? AND channel_id=?`).run(guildId,channelId);
    });del();
  }
}
