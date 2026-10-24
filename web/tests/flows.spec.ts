import { expect, test, type Page } from '@playwright/test';

/* Critical UI flows (QA 2026-10-19), against a running stack with the AT-08 test accounts (web/.env.visual):
   - every admin Workspace page (§4.3) opens without a browser error or a failed API call (§7);
   - an employee asks a question in chat and gets an answer or the exact §6 FR-CHAT-04 refusal, never an error. */

const ADMIN_PAGES = ['Knowledge', 'Add information', 'Documents', 'Sales memory', 'Approvals', 'Access requests', 'Dashboard',
  'Insights', 'Users', 'Departments', 'Vocabulary', 'API keys', 'System'];
const NOT_FOUND = "I couldn't find an approved answer in the company knowledge base.";

function watch(page: Page) {
  const problems: string[] = [];
  page.on('pageerror', e => problems.push(`page error: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('response', r => { if (r.url().includes('/v1/') && r.status() >= 500) problems.push(`${r.status()} ${r.url()}`); });
  return problems;
}

async function signIn(page: Page, userVar: string) {
  const user = process.env[userVar], password = process.env.QA_PASSWORD;
  if (!user || !password) throw new Error(`Set ${userVar} and QA_PASSWORD (environment or web/.env.visual).`);
  await page.goto('/');
  await page.locator('#lid').fill(user);
  await page.locator('#lpw').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Ask Quixotic AI' })).toBeVisible();
}

test('admin: every Workspace page opens without errors', async ({ page }) => {
  await signIn(page, 'QA_ADMIN_USER');
  const problems = watch(page);         // after sign-in: the signed-out session probe answers 401 by design
  for (const name of ADMIN_PAGES) {
    await page.getByRole('navigation').getByRole('link', { name: new RegExp(`^${name}\\b`) }).first().click();
    await page.waitForLoadState('networkidle');
    expect(problems, `after opening ${name}`).toEqual([]);
  }
});

test('employee: chat question gets an answer (approved, general AI answer, or the exact refusal)', async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page, 'QA_EMPLOYEE_USER');
  const problems = watch(page);         // after sign-in: the signed-out session probe answers 401 by design
  const box = page.getByRole('textbox').last();
  await box.fill('What are the night shift timings?');
  await box.press('Enter');
  const reply = page.locator('text=/11:00 PM|General AI answer|' + NOT_FOUND.replace(/[.?]/g, '\\$&') + '/').first();
  await expect(reply).toBeVisible({ timeout: 90_000 });
  expect(problems).toEqual([]);
});

test('Translate mode: Roman Urdu into the selected language (English), can be cancelled', async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page, 'QA_EMPLOYEE_USER');            // the AT-08 employee is in Sales - Upseller / Fresh Seller
  const problems = watch(page);
  await page.getByRole('button', { name: 'Answer mode' }).click();
  await page.getByRole('button', { name: /^Translate/ }).click();
  const box = page.getByRole('textbox').last();
  await box.fill('Sir aap ka logo kal tak ready ho jayega, aap sirf 10 dollar upfront de dein.');
  await box.press('Enter');
  await expect(page.getByText('English translation')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/logo/i).last()).toContainText(/10/);
  await page.getByRole('button', { name: 'Cancel translation mode' }).click();      // QAI-12
  await expect(page.getByRole('button', { name: 'Cancel translation mode' })).toHaveCount(0);
  expect(problems).toEqual([]);
});
