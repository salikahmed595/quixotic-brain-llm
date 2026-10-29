// Copied from discord-bot/src/guard.js (same behaviour; keep both in sync until the bot is retired).
// Rule-based guard against obvious invented delivery/payment commitments in a draft (from the starter).
const promise=/(\b(?:guarantee|guaranteed|promise|definitely|100%)\b.{0,65}\b(?:deliver|delivery|ready|finish|refund|discount|ship|complete)\b|\b(?:deliver|delivery|ready|finish|completed|refund)\b.{0,50}\b(?:tomorrow|tonight|today|within\s+\d+\s+(?:hours|days)|by\s+\w+day)\b)/i;
const negative=/\b(?:cannot|can't|won't|not|need to check|before i promise|confirm first|let me check|can't guarantee)\b/i;
export function validateDraft(draft) {
  if(typeof draft!=='string'||!draft.trim()) return {ok:false,reason:'Draft empty'};
  if(draft.length>1800) return {ok:false,reason:'Draft too long for review'};
  if(promise.test(draft) && !negative.test(draft)) return {ok:false,reason:'Possible unsupported guarantee or deadline; requires verified CRM approval'};
  if(/\b(?:payment (?:is|was) (?:confirmed|received)|your payment went through|already paid)\b/i.test(draft) && !negative.test(draft)) return {ok:false,reason:'Unverified payment-status claim'};
  return {ok:true,reason:''};
}
