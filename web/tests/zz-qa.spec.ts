import { test, expect, type Page } from '@playwright/test';
// temporary QA checks against the HTTP trial server (QAI-11 copy, QAI-12 cancel mode); deleted after the run

async function signIn(page: Page) {
  await page.goto('/'); await page.locator('#lid').fill(process.env.QA_EMPLOYEE_USER!); await page.locator('#lpw').fill(process.env.QA_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click(); await expect(page.getByRole('heading', { name: 'Ask Quixotic AI' })).toBeVisible();
  // record what the page really copies (works for both the clipboard API and the execCommand fallback)
  await page.evaluate(() => {
    (window as any).__copied = [];
    document.addEventListener('copy', () => { (window as any).__copied.push(String(window.getSelection() || (document.activeElement as HTMLTextAreaElement)?.value || '')); });
  });
}

test('QAI-11 copy works on plain HTTP; QAI-12 translation mode can be cancelled', async ({ page }) => {
  test.setTimeout(300_000);
  await signIn(page);
  console.log('secure context:', await page.evaluate(() => window.isSecureContext));
  await page.getByRole('button', { name: 'Answer mode' }).click();
  await page.getByRole('button', { name: /^Translate/ }).click();
  await page.getByLabel('Translate to').selectOption('Spanish');
  const box = page.getByRole('textbox').last();
  await box.fill('Sir aap ka logo kal tak ready ho jayega.'); await box.press('Enter');
  await expect(page.getByText('Spanish translation')).toBeVisible({ timeout: 120_000 });
  await page.getByRole('button', { name: /^Copy$/ }).last().click();
  await expect(page.getByText('Copied', { exact: true })).toBeVisible();
  const copied = await page.evaluate(() => (window as any).__copied as string[]);
  console.log('copied (translation):', JSON.stringify(copied));
  expect(copied.join(' ')).toMatch(/logo/i);
  await page.getByRole('button', { name: 'Cancel translation mode' }).click();
  await expect(page.getByLabel('Translate to')).toHaveCount(0);
  console.log('cancel mode: chip removed');
  // a chat answer: copy one message bubble
  await box.fill("New client asked how long a Twitch logo takes. He is friendly. What should I reply?"); await box.press('Enter');
  await expect(page.getByText(/General AI answer|confidence/).first()).toBeVisible({ timeout: 200_000 });
  const bubbles = page.getByRole('button', { name: 'Copy message' });
  if (await bubbles.count()) {
    await bubbles.first().click();
    const c2 = await page.evaluate(() => (window as any).__copied as string[]);
    console.log('copied (bubble):', JSON.stringify(c2[c2.length - 1]));
    expect(c2.length).toBeGreaterThan(copied.length);
  }
  await page.screenshot({ path: process.env.SHOT!, fullPage: false });
});
