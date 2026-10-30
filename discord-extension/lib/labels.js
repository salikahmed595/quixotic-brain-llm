// Who is staff: the employee lists staff names as the chat shows them in the panel; everyone else (not a bot) is the customer.
export function parseStaffNames(text){
  return new Set(String(text||'').split(/[,\n]/).map(s=>s.trim().toLowerCase()).filter(Boolean));
}

export function labelMessages(messages,staffNames){
  return messages.map(m=>({...m,isStaff:staffNames.has(String(m.author||'').trim().toLowerCase())}));
}
