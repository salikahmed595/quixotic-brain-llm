import { useState } from 'react';
import { storage } from '../api';
import { go } from '../state';
import { copyWithToast } from '../ui';
import { INSTALL_STEPS, type StepAction } from '../install';

/* Owner 2026-10-29: one step at a time, so employees always know what to do next (install guide for the
   Discord reply helper). Remembers the step they reached on this device. */
export function Install() {
  const last = INSTALL_STEPS.length - 1;
  const [i, setI] = useState(() => Math.min(Math.max(Number(storage.get('qb_install_step')) || 0, 0), last));
  const to = (n: number) => { setI(n); storage.set('qb_install_step', String(n)); };
  const step = INSTALL_STEPS[i];

  return (
    <div className="max-w-[720px] w-full mx-auto px-4 pb-16">
      <p className="text-[11px] font-extrabold tracking-[.14em] uppercase text-orange">Discord reply helper</p>
      <h1 className="text-[28px] font-extrabold tracking-tight text-ink mt-1">Install it in 7 easy steps</h1>
      <p className="text-ink-2 mt-1.5">Then get a suggested reply for any Discord customer chat with one click. Takes about 2 minutes.</p>

      <div className="mt-6" aria-label={`Step ${i + 1} of ${INSTALL_STEPS.length}`}>
        <div className="flex justify-between text-[13px] font-bold text-ink-2 mb-2">
          <span>Step {i + 1} of {INSTALL_STEPS.length}</span><span>{Math.round(((i + 1) / INSTALL_STEPS.length) * 100)}%</span>
        </div>
        <div className="h-2 rounded-full bg-line overflow-hidden"><div className="h-full bg-orange transition-[width] duration-300" style={{ width: `${((i + 1) / INSTALL_STEPS.length) * 100}%` }} /></div>
        <ol className="flex gap-1.5 mt-3 flex-wrap" aria-label="All steps">
          {INSTALL_STEPS.map((s, n) => (
            <li key={s.title}>
              <button onClick={() => to(n)} aria-current={n === i ? 'step' : undefined} title={s.title}
                className={`w-9 h-9 rounded-full text-[13px] font-extrabold grid place-items-center border ${n === i ? 'bg-orange text-white border-orange' : n < i ? 'bg-green-50 text-green-700 border-green-200' : 'bg-white text-muted border-line'}`}>
                {n < i ? '✓' : n + 1}
              </button>
            </li>
          ))}
        </ol>
      </div>

      <section className="mt-5 rounded-2xl border border-orange-200 bg-white shadow-sm p-6" aria-live="polite">
        <p className="text-[11px] font-extrabold tracking-[.12em] uppercase text-orange">Do this now</p>
        <h2 className="text-[22px] font-extrabold text-ink mt-1">{i + 1}. {step.title}</h2>
        <p className="text-[15px] leading-relaxed text-ink-2 mt-2">{step.text}</p>
        {step.action && <ActionButton action={step.action} onDone={() => i < last && to(i + 1)} />}
        {step.tip && <p className="mt-4 rounded-xl bg-orange-50 border border-orange-100 px-4 py-3 text-[13.5px] text-ink-2">💡 {step.tip}</p>}
      </section>

      <div className="flex justify-between gap-3 mt-5">
        <button className="btn" disabled={i === 0} onClick={() => to(i - 1)}>← Back</button>
        {i < last
          ? <button className="btn primary" onClick={() => to(i + 1)}>I did this, next step →</button>
          : <button className="btn primary" onClick={() => { to(0); go('ask'); }}>All done ✓</button>}
      </div>
    </div>
  );
}

function ActionButton({ action, onDone }: { action: StepAction; onDone: () => void }) {
  const cls = 'btn primary mt-5 h-12 px-6 text-[15px] inline-flex items-center no-underline';
  if (action.kind === 'copy') return <button className={cls} onClick={() => copyWithToast(action.value)}>📋 {action.label}</button>;
  if (action.kind === 'download') return <a className={cls} href={action.value} download onClick={() => setTimeout(onDone, 800)}>⬇ {action.label}</a>;
  return <a className={cls} href={action.value} target="_blank" rel="noreferrer">↗ {action.label}</a>;
}
