<!-- PRODUCT.md section 4 -->
# 4. Reference UI — preserve the supplied screenshots

Reference A: Admin screenshot (`image(20261016-164021).png`; 1468 × 901). Reference B: Employee screenshot (`image(20261016-164058).png`; 1478 × 907). Implement the desktop interface to be visually faithful at approximately 1470 × 900 viewport. Keep the same layout, information hierarchy, spacing, typography feel, copy, mascot, icons, colors, and interaction placements. Reuse original graphic assets if available; otherwise recreate equivalent SVG assets and review against screenshots. Exact pixel parity cannot be guaranteed solely from raster screenshots, so verify with side-by-side visual regression screenshots.

### 4.1 Shared desktop screen

- Fixed left sidebar, approximately 282–284 px wide, full viewport height; warm off-white background (sample near #FBF6F1), extremely light separator.
- Main content warm cream (sample #FFFAF6); white cards; bright orange emphasis (approximate #FF6B1A, confirm against source). Dark charcoal headings. Clean rounded sans-serif type; match exact font by inspecting original app assets if available rather than guessing.
- Top-left rounded orange app icon with white sparkle, followed by Quixotic AI text, where AI is orange; small collapse-sidebar icon on right.
- Sidebar links New chat and Search chats, with the same compact icons and typography.
- Centered prominent headline Ask Quixotic AI, with 'Quixotic AI' in orange and a small orange sparkle icon above/right.
- Centered subtitle: Get instant answers from your call center knowledge base — scripts, objections, SOPs, policies and more.
- Behind content: subtle pale-orange curved wave lines (decorative; pointer-events disabled). Center illustration: friendly orange/black headset AI mascot. Floating labeled pills: Scripts, Objections, Policies, and SOPs.
- Large white rounded question composer, approximately 960 px wide on desktop, with slight shadow. Placeholder: Ask Quixotic AI about scripts, objections, SOPs, and company knowledge...
- Composer bottom-left controls, in this order: circular + button; Web Search pill (screenshot reads 'WebSearch', preserve displayed text if strict parity required); Company Knowledge dropdown. Bottom-right: circular microphone icon, then pale-orange circular paper-plane send button.
- Below composer: label Try asking about... and exactly four horizontal example cards: Customer says too expensive, Booking script, Refund policy, Lead qualification. Match cards' icons, light borders, 15–18 px radius, orange arrow, and orange hover/active outline.
- Bottom-left fixed account profile card with avatar, username/role, scope subtitle, and ellipsis menu. Sidebar scroll is independent of main content.
- Homepage is intentionally spacious and not text-heavy. On entering a conversation, replace the hero area with message history, sources, and the pinned chat composer, while retaining the same visual system.

### 4.2 Employee layout — EXACT navigation scope

Employee sidebar contains: Quixotic AI, New chat, Search chats, date-grouped chat history (e.g. Previous 30 days), and the Employee profile card at bottom. No Workspace, Knowledge, Manage, or Administration navigation is visible. Profile subtitle shows Employee · [Authorized Scope]. Display 'Company Wide' only if the employee truly has that access; do not assign company-wide access by default.

### 4.3 Admin layout — EXACT sidebar structure and order

1. Quixotic AI / collapse toggle
2. New chat
3. Search chats
4. WORKSPACE (collapsible)
5. KNOWLEDGE: Knowledge; Add information; Documents; Sales memory
6. MANAGE: Approvals; Access requests; Dashboard; Insights
7. ADMINISTRATION: Users; Departments; Vocabulary; API keys; System
8. Date-grouped personal chat history
9. Fixed Administrator account card; subtitle Administrator · Company Wide when applicable.

Admin gets the same central Ask Quixotic AI home screen as the employee. Administrative pages open in the main panel without changing the sidebar design. Active item styling must remain understated and orange-accented.

### 4.4 Responsive design

At tablet widths, allow sidebar collapse. On mobile, put sidebar inside an accessible navigation drawer; retain brand, chat input, question examples (horizontal-scroll or stacked), and account status. Reflow mascot and floating labels rather than overlapping the composer. Maintain minimum 44 × 44 px touch targets, keyboard navigation, readable contrast, and visible focus states. The supplied screenshots define desktop appearance; mobile layouts must be derived consistently rather than assumed to have their own reference images.
