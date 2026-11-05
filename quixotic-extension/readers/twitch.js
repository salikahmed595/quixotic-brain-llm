// Reads the Twitch chat already on screen (channel page, popout chat, creator dashboard). Every Twitch page-layout
// assumption lives here. Injected on click; exposes globalThis.quixoticReadChat like the other readers.
(function(){
  const LINE='.chat-line__message';
  const BOTS=new Set(['nightbot','streamelements','streamlabs','moobot','fossabot','wizebot','sery_bot','soundalerts']);

  function textOf(el){
    if(!el) return '';
    const copy=el.cloneNode(true);
    copy.querySelectorAll('img[alt]').forEach(img=>img.replaceWith(img.ownerDocument.createTextNode(' '+img.alt)));
    return copy.textContent.replace(/\s+/g,' ').trim();
  }

  globalThis.quixoticReadChat=function(doc){
    return [...doc.querySelectorAll(LINE)].map((li,i)=>{
      const nameEl=li.querySelector('.chat-author__display-name');
      const login=(li.getAttribute('data-a-user')||nameEl?.getAttribute('data-a-user')||'').toLowerCase();
      return {id:String(i+1),author:(nameEl?.textContent||login).trim(),isBot:BOTS.has(login),
        content:textOf(li.querySelector('[data-a-target="chat-line-message-body"]'))};
    }).filter(m=>m.author||m.content);
  };
})();
