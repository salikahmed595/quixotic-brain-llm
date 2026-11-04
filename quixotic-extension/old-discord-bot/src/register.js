import 'dotenv/config';
import {REST,Routes} from 'discord.js';
import {COMMANDS} from './commands.js';
for(const n of ['DISCORD_TOKEN','DISCORD_CLIENT_ID','DISCORD_GUILD_ID']) if(!process.env[n]) throw new Error(`Missing ${n}`);
const rest=new REST({version:'10'}).setToken(process.env.DISCORD_TOKEN);
await rest.put(Routes.applicationGuildCommands(process.env.DISCORD_CLIENT_ID,process.env.DISCORD_GUILD_ID),{body:COMMANDS});
console.log('Registered Discord guild commands.');
