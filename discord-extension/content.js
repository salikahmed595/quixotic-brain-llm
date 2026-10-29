// Answers the panel's read request with the chat currently on screen. Reads only; never types, clicks or sends.
chrome.runtime.onMessage.addListener((msg,_sender,sendResponse)=>{
  if(msg?.type==='quixotic-read-chat') sendResponse({messages:globalThis.quixoticReadChat(document)});
});
