import 'dotenv/config';
import {Client,GatewayIntentBits,MessageFlags,PermissionFlagsBits,ButtonBuilder,ButtonStyle,ActionRowBuilder} from 'discord.js';
import {resolve} from 'node:path';
import {Store} from './store.js';
import {syncHistory} from './discordHistory.js';
import {loadQuixoticConfig} from './quixotic.js';
import {draftReply} from './draft.js';

const env=(k)=>String(process.env[k]||'').trim();
for(const k of ['DISCORD_TOKEN','DISCORD_GUILD_ID','ALLOWED_CHANNEL_IDS','STAFF_ROLE_IDS']) if(!env(k)) throw new Error(`Missing mandatory configuration: ${k}`);
const allowed=new Set(env('ALLOWED_CHANNEL_IDS').split(',').map(x=>x.trim()));
const staff=new Set(env('STAFF_ROLE_IDS').split(',').map(x=>x.trim()));
const config=loadQuixoticConfig();
const store=new Store(resolve(env('DB_PATH')||'./data/copilot.sqlite'));
const bot=new Client({intents:[GatewayIntentBits.Guilds,GatewayIntentBits.GuildMessages,GatewayIntentBits.MessageContent]});
const permittedChannel=c=>c?.guildId===env('DISCORD_GUILD_ID') && (allowed.has(c.id)||(c.parentId&&allowed.has(c.parentId)));
const roleAllowed=member=>{
  const roleIds=member?.roles?.cache ? [...member.roles.cache.keys()] : (Array.isArray(member?.roles)?member.roles:[]);
  return roleIds.some(id=>staff.has(id));
};
const staffMemberCache=new Map();
async function isTicketParticipant(message,customerId){
  if(message.author?.id===customerId) return true;
  const uid=message.author?.id; if(!uid) return false;
  if(staffMemberCache.has(uid)) return staffMemberCache.get(uid);
  let member=message.member;
  if(!member) try{member=await message.guild.members.fetch(uid);}catch{return false;}
  const allowed=roleAllowed(member)||member?.permissions?.has(PermissionFlagsBits.ManageGuild)||false;
  staffMemberCache.set(uid,allowed);return allowed;
}
const canUse=interaction=>interaction.inGuild()&&permittedChannel(interaction.channel)&&
  (roleAllowed(interaction.member)||interaction.memberPermissions?.has(PermissionFlagsBits.ManageGuild))&&
  interaction.memberPermissions?.has(PermissionFlagsBits.ViewChannel)&&
  interaction.memberPermissions?.has(PermissionFlagsBits.ReadMessageHistory);
const safeError=e=>{
  console.error('Sales copilot operation failed:',e);
  // Do not expose model API tokens, customer data, or internal exception strings in Discord.
  return 'Request could not be completed. Check bot permissions, AI provider configuration, and server logs.';
};

bot.on('messageCreate',m=>{
  if(!m.inGuild()||m.author.bot||!permittedChannel(m.channel)) return;
  const link=store.getLink(m.guildId,m.channelId);
  if(!link?.consent_at || (m.author.id!==link.customer_id && !roleAllowed(m.member))) return;
  store.saveMessage({guildId:m.guildId,channelId:m.channelId,id:m.id,authorId:m.author.id,
    authorName:m.author.username,content:m.content||'',createdAt:m.createdAt.toISOString(),isBot:false});
});

bot.on('interactionCreate',async interaction=>{
  if(!interaction.isChatInputCommand()&&!interaction.isMessageContextMenuCommand()&&!interaction.isButton()) return;
  try {
    if(interaction.isChatInputCommand() && ['consent','revoke'].includes(interaction.commandName)) {
      const link=interaction.inGuild()&&permittedChannel(interaction.channel) ? store.getLink(interaction.guildId,interaction.channelId) : null;
      if(!link || link.customer_id!==interaction.user.id) {
        await interaction.reply({content:'This command is only available to the linked customer in their ticket.',flags:MessageFlags.Ephemeral}); return;
      }
      if(interaction.commandName==='revoke') {
        store.forget(interaction.guildId,interaction.channelId);
        await interaction.reply({content:'Your consent has been revoked and the copilot’s local records for this ticket deleted. Original Discord messages remain on Discord.',flags:MessageFlags.Ephemeral});return;
      }
      await interaction.deferReply({flags:MessageFlags.Ephemeral});
      store.grantConsent(interaction.guildId,interaction.channelId,interaction.user.id);
      const result=await syncHistory(interaction.channel,store,Number(env('MAX_SYNC_PAGES')||100),m=>isTicketParticipant(m,link.customer_id));
      store.recalculateFacts(interaction.guildId,interaction.channelId);
      await interaction.editReply(`Thanks. This ticket can now be used for AI-assisted staff reply drafts; the bot does not send sales messages on its own. Archived coverage: ${result.complete?'complete':'partial, continuing on future requests'}. Use /revoke to remove stored records.`);return;
    }
    if(!canUse(interaction)) {
      await interaction.reply({content:'Not authorized. Use this only within an approved sales ticket/channel with staff permission.',flags:MessageFlags.Ephemeral});return;
    }
    const g=interaction.guildId,c=interaction.channelId;
    if(interaction.isButton()){
      if(interaction.customId!==`forget:${g}:${c}:${interaction.user.id}`) return;
      if(!interaction.memberPermissions.has(PermissionFlagsBits.ManageGuild)) return;
      store.forget(g,c);
      await interaction.update({content:'Stored messages, extracted facts and draft audit metadata for this ticket have been deleted; ticket unlinked.',components:[]});return;
    }
    if(interaction.commandName==='forget-client'){
      if(!interaction.memberPermissions.has(PermissionFlagsBits.ManageGuild)){
        await interaction.reply({content:'Only a server manager can delete a client ticket.',flags:MessageFlags.Ephemeral});return;
      }
      const button=new ButtonBuilder().setCustomId(`forget:${g}:${c}:${interaction.user.id}`).setLabel('Confirm permanent local deletion').setStyle(ButtonStyle.Danger);
      await interaction.reply({content:'Delete this ticket’s locally stored conversation and memory? This cannot be undone. Discord messages themselves are not deleted.',components:[new ActionRowBuilder().addComponents(button)],flags:MessageFlags.Ephemeral});return;
    }
    if(interaction.commandName==='link-client'){
      const customer=interaction.options.getUser('customer',true);
      if(customer.bot) {await interaction.reply({content:'Choose a real customer, not a bot.',flags:MessageFlags.Ephemeral});return;}
      const prior=store.getLink(g,c);
      if(prior && prior.customer_id!==customer.id){await interaction.reply({content:'This ticket is linked to a different customer. Export/review it and use /forget-client before relinking; do not mix customer memories.',flags:MessageFlags.Ephemeral});return;}
      if(prior?.customer_id===customer.id){
        await interaction.reply({content:`This ticket is already linked to <@${customer.id}>. Consent status: ${prior.consent_at?'granted':'pending /consent'}.`,flags:MessageFlags.Ephemeral});return;
      }
      if(!interaction.channel.permissionsFor(bot.user)?.has(PermissionFlagsBits.SendMessages)) {
        await interaction.reply({content:'Bot needs Send Messages permission here to disclose its data use before linking.',flags:MessageFlags.Ephemeral});return;
      }
      await interaction.deferReply({flags:MessageFlags.Ephemeral});
      store.link(g,c,customer.id,interaction.user.id);
      if (!prior) await interaction.channel.send(`ℹ️ <@${customer.id}>: This Quixotic ticket can use an AI-assisted drafting tool for staff. With your permission, the bot will store messages in **this ticket** to remember your artwork preferences and draft replies for human review. It does not automatically message you. Please use **/consent** here if you agree, or don't opt in. After opting in, use **/revoke** to delete the bot's locally stored data (not Discord's original messages).`);
      await interaction.editReply(`Linked this ticket to <@${customer.id}>. Waiting for the customer's **/consent** before reading or storing conversation history. Once consented, future messages are archived automatically.`);return;
    }
    if(interaction.commandName==='suggest'||interaction.isMessageContextMenuCommand()) {
      const link=store.getLink(g,c);
      if(!link){await interaction.reply({content:'Use /link-client first in this customer ticket.',flags:MessageFlags.Ephemeral});return;}
      if(!link.consent_at){await interaction.reply({content:'Waiting for the linked customer to opt in using /consent before any history is indexed.',flags:MessageFlags.Ephemeral});return;}
      let anchor=null;
      if(interaction.isMessageContextMenuCommand()){
        if(interaction.targetMessage.author.id!==link.customer_id){await interaction.reply({content:'Right-click a message written by the linked customer, not an employee.',flags:MessageFlags.Ephemeral});return;}
        anchor=interaction.targetMessage.id;
      }
      await interaction.deferReply({flags:MessageFlags.Ephemeral});
      await syncHistory(interaction.channel,store,Number(env('MAX_SYNC_PAGES')||100),m=>isTicketParticipant(m,link.customer_id));
      const messages=store.getMessages(g,c);
      const customerMessages=messages.filter(m=>m.authorId===link.customer_id && (!anchor||BigInt(m.id)<=BigInt(anchor)));
      if(!customerMessages.length){await interaction.editReply('No customer messages are available for this ticket. Ensure Message Content access and ticket history permissions.');return;}
      const chosen=anchor||customerMessages.at(-1).id;
      const customerText=customerMessages.find(m=>m.id===chosen)?.content;
      const audit=(state,riskReason)=>store.audit({guildId:g,channelId:c,customerId:link.customer_id,employeeId:interaction.user.id,sourceMessageId:chosen,state,model:'quixotic-ai',riskReason});
      let draft;
      try{draft=await draftReply({config,discordUserId:interaction.user.id,customerText});}
      catch(e){audit('MODEL_ERROR',e.message.slice(0,150));throw e;}
      audit(draft.ok?'DRAFT_PROPOSED':'BLOCKED',draft.reason||'');
      await interaction.editReply(draft.text);return;
    }
  }catch(e){
    const msg=safeError(e);
    try{if(interaction.deferred||interaction.replied) await interaction.editReply(msg);else await interaction.reply({content:msg,flags:MessageFlags.Ephemeral});}catch(err){console.error('Could not report failed interaction',err);}
  }
});

bot.once('ready',()=>console.log(`Quixotic sales copilot online as ${bot.user.tag}; approved channels only.`));
await bot.login(env('DISCORD_TOKEN'));
