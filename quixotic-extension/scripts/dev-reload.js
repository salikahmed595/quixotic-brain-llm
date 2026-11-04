// Dev only: scripts/dev.js adds this to the panel of the folder loaded in Chrome; the employee download never has it.
// Polls dev-stamp.json in the extension's own folder: panel edits reload the panel, other edits reload the extension.
(async()=>{
  const url=chrome.runtime.getURL('dev-stamp.json');
  const read=async()=>{try{return await (await fetch(url,{cache:'no-store'})).json();}catch{return null;}};
  const first=await read();if(!first) return;
  // Manifest, background and content-script edits that happened while the panel was closed.
  const {devCore}=await chrome.storage.local.get('devCore');
  if(devCore!==first.core){await chrome.storage.local.set({devCore:first.core});if(devCore){chrome.runtime.reload();return;}}
  setInterval(async()=>{
    const s=await read();if(!s) return;   // mid-copy: try again next tick
    if(s.core!==first.core){await chrome.storage.local.set({devCore:s.core});chrome.runtime.reload();}
    else if(s.panel!==first.panel) location.reload();
  },1500);
})();
