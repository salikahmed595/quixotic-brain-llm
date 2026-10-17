/* PRD §4.1 "friendly orange/black headset AI mascot". No original asset exists (owner, 2026-10-17), so this SVG is
   recreated from the reference screenshots: white rounded head with a dark visor and smiling orange eyes, orange
   headband and ear cups, a microphone boom from the right ear, and a white body with an orange dot. */
export function Mascot({ width = 150, className = '' }: { width?: number; className?: string }) {
  return (
    <svg className={className} width={width} viewBox="20 14 164 176" role="img" aria-label="Quixotic AI assistant">
      <defs>
        <linearGradient id="mq-orange" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff9147" /><stop offset="1" stopColor="#ff5c05" />
        </linearGradient>
        <linearGradient id="mq-white" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#f4eee8" />
        </linearGradient>
      </defs>
      {/* headband */}
      <path d="M41 92C41 46 72 21 104 21s63 25 63 71" fill="none" stroke="url(#mq-orange)" strokeWidth="8" strokeLinecap="round" />
      {/* head + visor */}
      <rect x="46" y="41" width="118" height="89" rx="40" fill="url(#mq-white)" stroke="#efe5dc" />
      <rect x="57" y="55" width="91" height="62" rx="28" fill="#1b1d2b" />
      {/* ear cups */}
      <rect x="28" y="68" width="24" height="50" rx="12" fill="url(#mq-orange)" />
      <rect x="155" y="68" width="23" height="50" rx="11.5" fill="url(#mq-orange)" />
      {/* smiling face */}
      <g fill="none" stroke="#ff8f45" strokeLinecap="round">
        <path d="M75 86q9.5-11 19 0" strokeWidth="5" />
        <path d="M109 86q9.5-11 19 0" strokeWidth="5" />
        <path d="M93 100q9.5 8 19 0" strokeWidth="4.5" />
      </g>
      {/* body */}
      <path d="M57 186v-21c0-19 21-30 45-30s45 11 45 30v21z" fill="url(#mq-white)" stroke="#efe5dc" />
      <circle cx="102" cy="160" r="7.5" fill="url(#mq-orange)" />
      {/* microphone boom */}
      <path d="M167 112c1 22-14 34-37 35" fill="none" stroke="url(#mq-orange)" strokeWidth="5" strokeLinecap="round" />
      <rect x="110" y="141" width="21" height="11.5" rx="5.75" fill="url(#mq-orange)" />
    </svg>
  );
}
