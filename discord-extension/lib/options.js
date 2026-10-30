// "More replies" and "Artwork ideas" ask for a numbered list; each line becomes its own card.
export function parseOptions(text){
  const items=String(text||'').split(/\r?\n/).map(l=>l.match(/^\s*\d+[.)]\s*(.+)$/)?.[1]?.trim()).filter(Boolean);
  return items.length?items:[String(text||'').trim()];
}
