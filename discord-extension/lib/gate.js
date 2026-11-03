// Boundary gate (owner prompt pack 2026-11-03, §7 Prompt B, §17 Prompt L, §24 "enforced in code"): decided in code
// from the visible chat before any AI call, so an opt-out or a payment request never depends on the model noticing.
const OPT_OUT=/\bdon'?t (?:add|dm|message|text|msg) me\b|\bif (?:you'?re|ur|u r|you are) selling\b|\bnot interested\b|\bno (?:sales|selling)\b|\b(?:stop|quit) (?:dm'?ing|dming|messaging|selling|asking|spamming|pitching)\b|\b(?:pls|please|plz) stop\b|\bdon'?t (?:try to )?sell me\b|\bleave me alone\b|\bdon'?t want (?:any )?(?:art|commissions?|your art)\b/i;
// A later message that asks about art again re-opens the conversation (§4: the latest explicit boundary wins).
const INVITE=/\b(?:how much|price|cost|commissions?|emotes?|banners?|overlays?|artwork|can (?:you|u) (?:make|draw|do)|show me|wanna see|want to see)\b/i;
// Readiness only from explicit wording (§8); "maybe later" is not readiness.
const PAY=/\b(?:where|how) (?:do|can|should) i pay\b|\bpay(?:ment)? (?:link|details|info)\b|\bpaypal link\b|\bsend (?:me )?(?:the |an )?invoice\b|\bready to (?:order|pay|buy)\b|\bi want to (?:order|buy|pay)\b|\btake my money\b/i;

// §17: the only customer-facing text for a payment handoff; the team sends the official instructions, never the AI.
export const HANDOFF_REPLY="Perfect, I'll have the team confirm the final details and send you the official payment instructions.";

// Scenario 14: the only customer-facing text for a privacy or deletion request.
export const DATA_REPLY="Got it, I'll pass this to the team so they can handle your data request properly.";
const DATA=/\b(?:delete|remove|erase|wipe)\b[^.?!]{0,25}\b(?:my|our) (?:data|info|information|details|messages|records|account)\b|\bprivacy\b|\bgdpr\b|\bwhat data do you (?:have|keep|store)\b/i;

const text=m=>String(m?.content||'');
const isCustomer=m=>!m.isBot&&!m.isStaff&&text(m).trim();

export function gateFor(chat){
  const customer=chat.filter(isCustomer);
  const optIdx=customer.findLastIndex(m=>OPT_OUT.test(text(m)));
  if(optIdx>=0&&!customer.slice(optIdx+1).some(m=>INVITE.test(text(m))))
    return {status:'NO_REPLY',evidence:[customer[optIdx].id],
      reason:'The customer opted out of sales or contact. Respect it: no pitch and no follow-up.'};
  const latest=customer.at(-1);
  // Scenario 14: privacy or deletion requests are handled by authorised staff, never answered by the AI.
  if(latest&&DATA.test(text(latest)))
    return {status:'HUMAN_HANDOFF',kind:'privacy',evidence:[latest.id],reply:DATA_REPLY,
      reason:'The customer asked about their data or privacy. Pass it to the team member who handles data requests.'};
  if(latest&&PAY.test(text(latest)))
    return {status:'HUMAN_HANDOFF',kind:'payment',evidence:[latest.id],reply:HANDOFF_REPLY,
      reason:'The customer wants to pay. The team must confirm the details and send the official payment instructions; never paste a link the AI wrote.'};
  return {status:'SUGGEST',evidence:[]};
}
