/* Line icons (24 × 24, stroked), drawn to match the reference screenshots (PRD §4.1). */
const P: Record<string, string> = {
  book: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v18H6.5A1.5 1.5 0 0 1 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 1 6.5 18H19"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  doc: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  notes: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  cloud: '<path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 20 11a3.5 3.5 0 0 1-1 7z"/><path d="M12 12v7M9 14.5l3-3 3 3"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
  tick: '<path d="M5 12l5 5L20 7"/>',
  chart: '<path d="M6 20V11M12 20V5M18 20v-6"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5h.01"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5"/><circle cx="17" cy="9" r="2.5"/><path d="M17.5 14.5c2.6.2 4.5 1.8 4.5 4.5"/>',
  building: '<path d="M5 21V4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v17"/><path d="M15 9h3a1 1 0 0 1 1 1v11M3 21h18M8.5 7h3M8.5 11h3M8.5 15h3"/>',
  key: '<circle cx="7.5" cy="16.5" r="3.5"/><path d="M10 14l9-9M16 8l2.5 2.5"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  mic: '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  send: '<path d="M21 3L3 11l7 3 3 7z"/><path d="M10 14l11-11"/>',
  chevd: '<path d="M6 9l6 6 6-6"/>',
  chevr: '<path d="M9 6l6 6-6 6"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  up: '<path d="M7 11v9H4v-9zM7 11l4-8a2 2 0 0 1 3 2l-1 4h6a2 2 0 0 1 2 2l-2 7a2 2 0 0 1-2 1.5H7"/>',
  down: '<path d="M17 13V4h3v9zM17 13l-4 8a2 2 0 0 1-3-2l1-4H5a2 2 0 0 1-2-2l2-7a2 2 0 0 1 2-1.5H17"/>',
  spark: '<path d="M12 3l2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  pen: '<path d="M4 20l1-5L16 4a2.5 2.5 0 0 1 4 4L9 19z"/>',
  msg: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/><path d="M8.5 11h7M8.5 14h4"/>',
  dots: '<circle cx="5" cy="12" r="1.3" fill="currentColor"/><circle cx="12" cy="12" r="1.3" fill="currentColor"/><circle cx="19" cy="12" r="1.3" fill="currentColor"/>',
  pulse: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  newchat: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  sidebar: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9M13 4v6M7 14v6"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"/>',
};

export function Icon({ name, size, className = '' }: { name: string; size?: number; className?: string }) {
  return (
    <svg className={`i ${className}`} viewBox="0 0 24 24" aria-hidden="true"
      style={size ? { width: size, height: size } : undefined} dangerouslySetInnerHTML={{ __html: P[name] || '' }} />
  );
}

/* App mark: rounded orange square with a white sparkle (PRD §4.1). */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <span className="grid place-items-center rounded-[10px] bg-orange text-white flex-none" style={{ width: size, height: size }}>
      <svg viewBox="0 0 24 24" width={size * 0.56} height={size * 0.56} fill="#fff" aria-hidden="true">
        <path d="M12 3l2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2z" />
      </svg>
    </span>
  );
}

export function Brand({ size = 18 }: { size?: number }) {
  return (
    <span className="flex items-center gap-2.5 font-extrabold tracking-[-0.02em] whitespace-pre" style={{ fontSize: size }}>
      <BrandMark /> <span>Quixotic <span className="text-orange">AI</span></span>
    </span>
  );
}
