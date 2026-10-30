// Any website: reads only the text the employee highlighted. "Name: message" lines keep their author; text without
// names is treated as the customer's message. Injected on click; exposes globalThis.quixoticReadChat like the app readers.
(function(){
  const NAMED=/^(?:\[[^\]]{1,20}\]\s*)?([^:\n]{1,40}):\s*(.*)$/;
  globalThis.quixoticReadChat=function(doc){
    const text=String(doc.defaultView.getSelection()||'');
    const out=[];
    for(const raw of text.split(/\r?\n/)){
      const lineText=raw.trim();if(!lineText) continue;
      const m=lineText.match(NAMED);
      if(m) out.push({author:m[1].trim(),content:m[2].trim()});
      else if(out.length) out.at(-1).content=(out.at(-1).content+' '+lineText).trim();
      else out.push({author:'',content:lineText});
    }
    return out.map((m,i)=>({id:String(i+1),author:m.author,isBot:false,content:m.content}));
  };
})();
