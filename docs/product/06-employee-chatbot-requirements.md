<!-- PRODUCT.md section 6 -->
# 6. Employee chatbot requirements

**FR-CHAT-01:** New chat, send/edit input before sending, conversation persistence, rename/delete own conversations, recent history grouping, and search own conversation titles/messages.

**FR-CHAT-02:** Send typed questions and optional microphone voice questions (speech-to-text with consent, recording state, cancellation, and error handling). A generated answer is text by default.

**FR-CHAT-03:** Four suggestion cards populate/submit example questions according to product decision, without making them hardcoded answers.

**FR-CHAT-04:** Company Knowledge is the default retrieval mode; answers must use only currently approved, permitted, indexed company sources. Display cited document title, relevant section and effective/updated date where available. If no verified answer is found: “I couldn't find an approved answer in the company knowledge base.” Offer Report missing information.

**FR-CHAT-05:** Web Search, if enabled, is explicitly separate from company answers: clearly label external information, cite URLs, avoid presenting web pages as company policy, and do not send confidential company text to an external search provider without authorization. Admin can disable the feature globally or per role. Do not silently mix untrusted web results into official policy responses.

**FR-CHAT-06:** Company Knowledge dropdown shows only permitted scopes (e.g. My Department, Company General, other assigned departments). Never expose unauthorized departments in the selector or backend retrieval.

**FR-CHAT-07:** Answers may use bullets, tables, and short actionable steps but should be clear and simple for new call-center staff. Show response loading, retry, unavailable service, feedback thumbs up/down, and cited-source drawer.

**FR-CHAT-08:** The assistant detects question language and answers in that language where possible while preserving the meaning of approved source text. Do not fabricate a translated policy absent supporting evidence.

**FR-CHAT-09:** Users see only their own chat history. Default admin analytics are aggregate; accessing individual conversation content requires a documented legal/operational policy and separate authorization.
