// Reads the X (Twitter) DM conversation already on screen. X shows no name on each bubble, so own messages are the
// ones drawn on the right (fromMe). Every X page-layout assumption lives here. Injected on click; exposes
// globalThis.quixoticReadChat like the other readers.
(function(){
  const ENTRY='[data-testid="messageEntry"]';
  const VIEW='[data-testid="DmActivityViewport"]';

  function textOf(el){
    const copy=el.cloneNode(true);
    copy.querySelectorAll('time').forEach(n=>n.remove());
    copy.querySelectorAll('img[alt]').forEach(img=>img.replaceWith(img.ownerDocument.createTextNode(img.alt==='Image'?'':' '+img.alt)));
    return copy.textContent.replace(/\s+/g,' ').trim();
  }
  function onRight(entry){
    const box=(entry.closest(VIEW)||entry.parentElement).getBoundingClientRect();
    const b=(entry.querySelector('[data-testid="tweetText"]')||entry).getBoundingClientRect();
    return b.left-box.left>box.right-b.right;
  }

  globalThis.quixoticReadChat=function(doc){
    return [...doc.querySelectorAll(ENTRY)].map(entry=>{
      const fromMe=onRight(entry);
      return {author:fromMe?'You':'',fromMe,isBot:false,content:textOf(entry)};
    }).filter(m=>m.content).map((m,i)=>({id:String(i+1),...m}));
  };
})();
