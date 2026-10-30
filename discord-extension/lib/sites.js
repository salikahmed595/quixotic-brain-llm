// Which reader to use for the tab (owner 2026-10-30: any messaging site). Apps listed here have their own reader
// and are allowed in manifest.json; any other website reads the text the employee highlights, after they allow it.
const APPS=[
  {app:'Discord',hosts:['discord.com'],file:'readers/discord.js'},
  {app:'Twitch',hosts:['www.twitch.tv','dashboard.twitch.tv'],file:'readers/twitch.js'},
];
const BLOCKED=['chromewebstore.google.com','chrome.google.com'];   // Chrome never lets extensions read these

export function siteFor(url){
  let u;try{u=new URL(url);}catch{return null;}
  if(!['http:','https:'].includes(u.protocol)||BLOCKED.includes(u.hostname)) return null;
  const origin=`${u.protocol}//${u.host}/*`;
  const known=APPS.find(a=>a.hosts.includes(u.hostname));
  return known?{app:known.app,file:known.file,origin,builtIn:true}:{app:null,file:'readers/selection.js',origin,builtIn:false};
}
