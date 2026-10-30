// Reads the chat Discord already shows in this tab: no Discord token, no Discord API, nothing stored or sent.
// Every Discord page-layout assumption lives here, so a Discord redesign is fixed in this one file.
// Classic script (content scripts can't be ES modules); exposes globalThis.quixoticReadChat.
(function(){
  const LIST='ol[data-list-id="chat-messages"]';
  const ITEM='li[id^="chat-messages-"]';

  function textOf(el){
    if(!el) return '';
    const copy=el.cloneNode(true);
    copy.querySelectorAll('time,[class*="edited"],[class*="timestamp"]').forEach(n=>n.remove());
    copy.querySelectorAll('img[alt]').forEach(img=>img.replaceWith(img.ownerDocument.createTextNode(img.alt)));
    return copy.textContent.replace(/\s+/g,' ').trim();
  }

  globalThis.quixoticReadChat=function(doc){
    const list=doc.querySelector(LIST);
    if(!list) return [];
    let author='',isBot=false;
    return [...list.querySelectorAll(ITEM)].map(li=>{
      const id=li.id.split('-').pop();
      const name=li.querySelector(`#message-username-${id} [class*="username"]`);
      if(name){   // a header starts a new group; follow-up messages in the group have none
        author=name.textContent.trim();
        isBot=Boolean(li.querySelector('h3 [class*="botTag"]'));
      }
      // Match the content by this message's own id, so a reply's quoted preview is never read as its text.
      return {id,author,isBot,content:textOf(li.querySelector(`#message-content-${id}:not([class*="replied"])`))};
    });
  };
})();
