import 'dotenv/config';
import {REST,Routes,SlashCommandBuilder,ContextMenuCommandBuilder,ApplicationCommandType} from 'discord.js';
for(const n of ['DISCORD_TOKEN','DISCORD_CLIENT_ID','DISCORD_GUILD_ID']) if(!process.env[n]) throw new Error(`Missing ${n}`);
const commands=[
  new SlashCommandBuilder().setName('link-client').setDescription('Link this approved sales thread to a customer')
    .addUserOption(x=>x.setName('customer').setDescription('Customer in this ticket').setRequired(true)),
  new SlashCommandBuilder().setName('consent').setDescription('Customer: allow storing this ticket to assist staff with replies'),
  new SlashCommandBuilder().setName('revoke').setDescription('Customer: delete the locally stored ticket and revoke consent'),
  new SlashCommandBuilder().setName('suggest').setDescription('Draft a contextual Discord reply from this linked customer conversation'),
  new SlashCommandBuilder().setName('forget-client').setDescription('Admin: delete locally stored conversation data and unlink this thread'),
  new ContextMenuCommandBuilder().setName('Draft Sales Reply').setType(ApplicationCommandType.Message)
].map(x=>x.toJSON());
const rest=new REST({version:'10'}).setToken(process.env.DISCORD_TOKEN);
await rest.put(Routes.applicationGuildCommands(process.env.DISCORD_CLIENT_ID,process.env.DISCORD_GUILD_ID),{body:commands});
console.log('Registered Discord guild commands.');
