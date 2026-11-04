import 'dotenv/config';
import {Client,GatewayIntentBits,MessageFlags,PermissionFlagsBits} from 'discord.js';
import {loadQuixoticConfig} from './quixotic.js';
import {draftReply} from './draft.js';
import {isCustomerMessage,pickLatestCustomerMessage} from './commands.js';
import {buildConversationQuestion} from './conversation.js';

// Thin client: nothing is stored here. Messages are read live only when staff ask for a draft (owner 2026-10-29).
const env=(k)=>String(process.env[k]||'').trim();
for(const k of ['DISCORD_TOKEN','DISCORD_GUILD_ID','ALLOWED_CHANNEL_IDS','STAFF_ROLE_IDS']) if(!env(k)) throw new Error(`Missing mandatory configuration: ${k}`);
const allowed=new Set(env('ALLOWED_CHANNEL_IDS').split(',').map(x=>x.trim()));
const staff=new Set(env('STAFF_ROLE_IDS').split(',').map(x=>x.trim()));
const config=loadQuixoticConfig();
const RECENT_MESSAGES=50;   // one Discord page of chat context; trimmed further to fit /v1/ask (conversation.js)
const bot=new Client({intents:[GatewayIntentBits.Guilds,GatewayIntentBits.GuildMessages,GatewayIntentBits.MessageContent]});
const permittedChannel=c=>c?.guildId===env('DISCORD_GUILD_ID') && (allowed.has(c.id)||(c.parentId&&allowed.has(c.parentId)));
const roleAllowed=member=>{
  const roleIds=member?.roles?.cache ? [...member.roles.cache.keys()] : (Array.isArray(member?.roles)?member.roles:[]);
  return roleIds.some(id=>staff.has(id));
};
const isStaffMember=member=>roleAllowed(member)||member?.permissions?.has?.(PermissionFlagsBits.ManageGuild)||false;
const toPlain=m=>({id:m.id,authorId:m.author?.id,isBot:Boolean(m.author?.bot),isStaff:isStaffMember(m.member),content:m.content||''});
const canUse=interaction=>interaction.inGuild()&&permittedChannel(interaction.channel)&&
  (roleAllowed(interaction.member)||interaction.memberPermissions?.has(PermissionFlagsBits.ManageGuild))&&
  interaction.memberPermissions?.has(PermissionFlagsBits.ViewChannel)&&
  interaction.memberPermissions?.has(PermissionFlagsBits.ReadMessageHistory);
const safeError=e=>{
  console.error('Sales copilot operation failed:',e);
  // Do not expose API keys, customer data, or internal exception strings in Discord.
  return 'Request could not be completed. Check bot permissions, Quixotic AI configuration, and server logs.';
};

bot.on('interactionCreate',async interaction=>{
  if(!interaction.isChatInputCommand()&&!interaction.isMessageContextMenuCommand()) return;
  try {
    if(!canUse(interaction)) {
      await interaction.reply({content:'Not authorized. Use this only within an approved sales ticket/channel with staff permission.',flags:MessageFlags.Ephemeral});return;
    }
    if(interaction.commandName!=='suggest'&&!interaction.isMessageContextMenuCommand()) return;
    let target;
    if(interaction.isMessageContextMenuCommand()){
      target=toPlain(interaction.targetMessage);
      if(!isCustomerMessage(target)){await interaction.reply({content:'Right-click a text message written by the customer, not by staff or a bot.',flags:MessageFlags.Ephemeral});return;}
    }
    await interaction.deferReply({flags:MessageFlags.Ephemeral});
    // The recent chat up to the chosen message goes along so the draft continues the conversation.
    const recent=await interaction.channel.messages.fetch(target?{limit:RECENT_MESSAGES,before:target.id}:{limit:RECENT_MESSAGES});
    const chat=[...recent.values()].map(toPlain);
    if(target) chat.push(target);
    else target=pickLatestCustomerMessage(chat);
    if(!target){await interaction.editReply('No recent customer message found in this channel.');return;}
    const question=buildConversationQuestion(chat,target.id);
    const draft=await draftReply({config,discordUserId:interaction.user.id,question});
    await interaction.editReply(draft.text);
  }catch(e){
    const msg=safeError(e);
    try{if(interaction.deferred||interaction.replied) await interaction.editReply(msg);else await interaction.reply({content:msg,flags:MessageFlags.Ephemeral});}catch(err){console.error('Could not report failed interaction',err);}
  }
});

bot.once('ready',()=>console.log(`Quixotic sales copilot online as ${bot.user.tag}; approved channels only.`));
await bot.login(env('DISCORD_TOKEN'));
