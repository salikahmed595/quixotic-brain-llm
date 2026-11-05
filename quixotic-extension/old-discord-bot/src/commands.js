// Discord command definitions (plain API JSON: type 1 = slash command, type 3 = message context menu) and
// message selection. The bot stores nothing; it reads the channel live when an employee asks (owner 2026-10-29).
export const COMMANDS=[
  {name:'suggest',type:1,description:'Private reply draft for the latest customer message in this channel'},
  {name:'Draft Sales Reply',type:3}
];

export const isCustomerMessage=m=>!m.isBot&&!m.isStaff&&Boolean(String(m.content||'').trim());

export function pickLatestCustomerMessage(messages){
  let latest=null;
  for(const m of messages) if(isCustomerMessage(m)&&(!latest||BigInt(m.id)>BigInt(latest.id))) latest=m;
  return latest;
}
