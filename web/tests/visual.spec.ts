import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';

/* PRD §13 AT-08 — UI parity. Signs in as an employee and as an administrator against the running local stack, compares
   the home screen with the two §4 reference screenshots, and checks role-based navigation (§4.2, §4.3) and the §4.4
   responsive rules (no horizontal scroll, 44 × 44 px touch targets).
   Credentials: QA_ADMIN_USER, QA_EMPLOYEE_USER, QA_PASSWORD (environment or the gitignored web/.env.visual). */

const REF_DIR = new URL('../../UI images/reference/', import.meta.url);
const ROLES = {
  admin: { user: 'QA_ADMIN_USER', ref: 'image(20261016-164021).png', viewport: { width: 1468, height: 901 } },
  employee: { user: 'QA_EMPLOYEE_USER', ref: 'image(20261016-164058).png', viewport: { width: 1478, height: 907 } },
} as const;
type Role = keyof typeof ROLES;

// PRD §4.3 — exact admin WORKSPACE groups and items, in order.
const ADMIN_NAV = [
  'Knowledge', ['Knowledge', 'Add information', 'Documents', 'Sales memory'],
  'Manage', ['Approvals', 'Access requests', 'Dashboard', 'Insights'],
  'Administration', ['Users', 'Departments', 'Vocabulary', 'API keys', 'System'],
] as const;

/* Tolerance (implementation choice, docs/PRD_GAPS.md §0.6). The measured M6 parity is within a few pixels and font
   rasterisation differs from the machine the screenshots were taken on, so a pixel only counts as different when
   pixelmatch flags it (THRESHOLD) AND no pixel of similar colour exists within SHIFT_PX in the other image, in either
   direction. Small offsets and anti-aliasing are absorbed; a block that moves further leaves unmatched pixels.
   Masked regions (chat history titles, the animated mascot, the Workspace scrollbar — the reference shows the Windows
   classic scrollbar, which is browser chrome) are blanked in both images before comparing. */
const PIXEL_THRESHOLD = 0.2;
const SHIFT_PX = 4;
const COLOR_TOLERANCE = 48;      // max per-channel difference for "similar colour" in the shift search
const MAX_DIFF_RATIO = 0.008;     // baselines measured 2026-10-17: employee ≈0.1 %, admin ≈0.5 %; a 10 px drift ≥1.3 %

function credentials(role: Role) {
  const user = process.env[ROLES[role].user], password = process.env.QA_PASSWORD;
  if (!user || !password) throw new Error(`Set ${ROLES[role].user} and QA_PASSWORD (environment or web/.env.visual) to run the AT-08 visual test.`);
  return { user, password };
}

async function signIn(page: Page, role: Role) {
  const { user, password } = credentials(role);
  await page.goto('/');
  await page.locator('#lid').fill(user);
  await page.locator('#lpw').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Ask Quixotic AI' })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

type Box = { x: number; y: number; width: number; height: number };

function blank(png: PNG, b: Box) {
  const x0 = Math.max(0, Math.floor(b.x)), y0 = Math.max(0, Math.floor(b.y));
  const x1 = Math.min(png.width, Math.ceil(b.x + b.width)), y1 = Math.min(png.height, Math.ceil(b.y + b.height));
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    const i = (y * png.width + x) * 4;
    png.data[i] = 255; png.data[i + 1] = 0; png.data[i + 2] = 255; png.data[i + 3] = 255;
  }
}

/* Pixels flagged by pixelmatch that have no similar-coloured pixel within SHIFT_PX in the other image. */
function unmatched(a: PNG, b: PNG, flagged: PNG, out: PNG) {
  const { width: w, height: h } = a;
  const near = (src: PNG, dst: PNG, x: number, y: number) => {
    const i = (y * w + x) * 4;
    for (let dy = -SHIFT_PX; dy <= SHIFT_PX; dy++) for (let dx = -SHIFT_PX; dx <= SHIFT_PX; dx++) {
      const xx = x + dx, yy = y + dy;
      if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue;
      const j = (yy * w + xx) * 4;
      if (Math.abs(src.data[i] - dst.data[j]) <= COLOR_TOLERANCE && Math.abs(src.data[i + 1] - dst.data[j + 1]) <= COLOR_TOLERANCE
        && Math.abs(src.data[i + 2] - dst.data[j + 2]) <= COLOR_TOLERANCE) return true;
    }
    return false;
  };
  let n = 0;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4;
    const isFlagged = flagged.data[i] === 255 && flagged.data[i + 1] === 0 && flagged.data[i + 2] === 0;
    const bad = isFlagged && (!near(a, b, x, y) || !near(b, a, x, y));
    out.data[i] = bad ? 255 : 245; out.data[i + 1] = bad ? 0 : 245; out.data[i + 2] = bad ? 0 : 245; out.data[i + 3] = 255;
    if (bad) n++;
  }
  return n;
}

const pad = (b: Box, p: number): Box => ({ x: b.x - p, y: b.y - p, width: b.width + 2 * p, height: b.height + 2 * p });

async function diffRatio(page: Page, role: Role, info: TestInfo, tag = '') {
  const nav = page.getByRole('navigation', { name: 'Main' });
  const history = await nav.locator(':scope > div.flex-1').boundingBox();
  const mascot = await page.getByRole('img', { name: 'Quixotic AI assistant' }).boundingBox();
  if (!history || !mascot) throw new Error('chat history or mascot not found on the home screen');
  // Chat history titles are personal data; the mascot is animated. Both are blanked in the actual and the reference.
  const masks = [history, pad(mascot, 8)];
  const groups = nav.locator('.ws-group');
  const workspace = (await groups.count()) ? await groups.first().locator('xpath=..').boundingBox() : null;
  if (workspace) masks.push({ x: workspace.x + workspace.width - 20, y: workspace.y - 8, width: 20, height: workspace.height + 16 });

  const actual = PNG.sync.read(await page.screenshot({ animations: 'disabled', caret: 'hide' }));
  const expected = PNG.sync.read(readFileSync(new URL(ROLES[role].ref, REF_DIR)));
  expect([actual.width, actual.height], 'screenshot size must equal the reference size').toEqual([expected.width, expected.height]);
  for (const m of masks) { blank(actual, m); blank(expected, m); }

  const flagged = new PNG({ width: actual.width, height: actual.height }), diff = new PNG({ width: actual.width, height: actual.height });
  pixelmatch(actual.data, expected.data, flagged.data, actual.width, actual.height, { threshold: PIXEL_THRESHOLD, diffMask: true });
  const changed = unmatched(actual, expected, flagged, diff);
  const ratio = changed / (actual.width * actual.height);
  for (const [name, png] of [['actual', actual], ['expected', expected], ['diff', diff]] as const) {
    const path = info.outputPath(`${role}${tag}-${name}.png`);
    writeFileSync(path, PNG.sync.write(png));
    await info.attach(`${role}${tag}-${name}.png`, { path, contentType: 'image/png' });
  }
  console.log(`[AT-08] ${role}${tag}: ${changed} differing pixels (${(ratio * 100).toFixed(2)}%, limit ${MAX_DIFF_RATIO * 100}%)`);
  return ratio;
}

async function showHome(page: Page, role: Role) {
  await page.setViewportSize(ROLES[role].viewport);
  await signIn(page, role);
  // The admin reference shows the first example card in its hover state (docs/PRD_GAPS.md §0.5).
  if (role === 'admin') await page.locator('.tcard').first().hover();
  else await page.mouse.move(ROLES[role].viewport.width - 5, ROLES[role].viewport.height - 5);
}

for (const role of ['employee', 'admin'] as const) {
  test(`AT-08 ${role} home screen matches the §4 reference`, async ({ page }, info) => {
    await showHome(page, role);
    expect(await diffRatio(page, role, info), `${role} home screen differs from ${ROLES[role].ref}; see the attached diff`)
      .toBeLessThanOrEqual(MAX_DIFF_RATIO);
  });

  // Guards the tolerance itself: moving the hero (headline, composer, example cards) by 10 px must fail the comparison.
  test(`AT-08 ${role} comparison catches a 10 px layout drift`, async ({ page }, info) => {
    await showHome(page, role);
    await page.addStyleTag({ content: '.hero-glow > div { transform: translate(10px, 10px) !important; }' });
    expect(await diffRatio(page, role, info, '-drift')).toBeGreaterThan(MAX_DIFF_RATIO);
  });
}

test('AT-08 employee sidebar shows no workspace or admin items (§4.2)', async ({ page }) => {
  await page.setViewportSize(ROLES.employee.viewport);
  await signIn(page, 'employee');
  const nav = page.getByRole('navigation', { name: 'Main' });
  await expect(nav.getByRole('button', { name: 'New chat' })).toBeVisible();
  for (const label of ['Workspace', 'Knowledge', 'Manage', 'Administration'])
    await expect(nav.getByText(label, { exact: true })).toHaveCount(0);
  await expect(nav.locator('.ws-item, .ws-label')).toHaveCount(0);
});

test('AT-08 admin sidebar follows the exact §4.3 order', async ({ page }) => {
  await page.setViewportSize(ROLES.admin.viewport);
  await signIn(page, 'admin');
  const nav = page.getByRole('navigation', { name: 'Main' });
  await expect(nav.getByRole('button', { name: 'Workspace' })).toHaveAttribute('aria-expanded', 'true');
  const seen = await nav.locator('.ws-label, .ws-item').evaluateAll(els =>
    els.map(e => (e.classList.contains('ws-label') ? `# ${e.textContent}` : e.textContent)!.trim().toLowerCase()));
  const want = ADMIN_NAV.flatMap(x => (typeof x === 'string' ? [`# ${x}`] : [...x])).map(s => s.toLowerCase());
  expect(seen).toEqual(want);

  // §4.3 items 1–9 top to bottom: brand, New chat, Search chats, WORKSPACE, groups, chat history, account card.
  const top = async (l: ReturnType<Page['locator']>) => (await l.boundingBox())!.y;
  const ys = [
    await top(nav.getByRole('button', { name: 'Close sidebar' })),
    await top(nav.getByRole('button', { name: 'New chat' })),
    await top(nav.getByLabel('Search chats')),
    await top(nav.getByRole('button', { name: 'Workspace' })),
    await top(nav.locator('.ws-label').first()),
    await top(nav.locator(':scope > div.flex-1')),
    await top(nav.getByRole('button', { name: 'Account menu' })),
  ];
  expect(ys).toEqual([...ys].sort((a, b) => a - b));
  await expect(nav.getByRole('button', { name: 'Account menu' })).toContainText('Administrator');
});

async function assertMobile(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, 'horizontal scroll at 375 px').toBeLessThanOrEqual(0);
  // §4.4 minimum 44 × 44 px touch targets for every visible control (an input inside a <label> counts as the label).
  const small = await page.evaluate(() => {
    const out: string[] = [];
    document.querySelectorAll<HTMLElement>('a[href], button, input, select, textarea, [role="button"]').forEach(el => {
      const target = (el.tagName === 'INPUT' && el.closest('label')) || el;
      const r = target.getBoundingClientRect(), s = getComputedStyle(target);
      if (!r.width || !r.height || s.visibility === 'hidden' || target.closest('[aria-hidden="true"]')) return;
      if (r.right <= 0 || r.left >= innerWidth || r.bottom <= 0 || r.top >= innerHeight) return;
      if (r.width < 44 || r.height < 44)
        out.push(`${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)}" ${Math.round(r.width)}×${Math.round(r.height)}`);
    });
    return out;
  });
  expect(small, 'touch targets smaller than 44 × 44 px').toEqual([]);
}

for (const role of ['employee', 'admin'] as const) {
  test(`AT-08 ${role} at 375 px: no horizontal scroll, 44 px touch targets (§4.4)`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await signIn(page, role);
    await assertMobile(page);
    await page.getByRole('button', { name: 'Open sidebar' }).click();
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeInViewport();
    await assertMobile(page);
  });
}
