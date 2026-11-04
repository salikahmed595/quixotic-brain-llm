// Runs the site's reader; if an app reader finds no chat (a redesign, or a page it doesn't know such as Twitch
// whispers), falls back to the text the employee highlighted. run(file) injects a reader and returns its messages.
export const SELECTION_READER='readers/selection.js';

export async function readWith(site,run){
  const messages=await run(site.file);
  if(messages?.length||site.file===SELECTION_READER) return messages||[];
  return (await run(SELECTION_READER))||[];
}
