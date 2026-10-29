// Unit test for the install guide content (run: npm run test:unit; Node 24 strips the types).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { INSTALL_STEPS, DOWNLOAD_URL, EXTENSION_FOLDER } from './install.ts';
import { ZIP_FOLDER } from '../../discord-extension/scripts/zip.js';

test('seven steps, each with a title and plain instructions', () => {
  assert.equal(INSTALL_STEPS.length, 7);
  for (const s of INSTALL_STEPS) { assert.ok(s.title.length > 3); assert.ok(s.text.length > 10); }
});

test('step 1 downloads the zip the portal build produces', () => {
  assert.deepEqual(INSTALL_STEPS[0].action, { kind: 'download', label: 'Download the helper', value: DOWNLOAD_URL });
  const prebuild = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).scripts.prebuild;
  assert.ok(prebuild.endsWith('public' + DOWNLOAD_URL), prebuild);
});

test('the folder name in the guide is the folder inside the zip', () => {
  assert.equal(EXTENSION_FOLDER, ZIP_FOLDER);
  assert.ok(INSTALL_STEPS.some(s => s.text.includes(EXTENSION_FOLDER)));
});

test('chrome://extensions is offered as a copy (websites cannot open it), Discord as a link', () => {
  assert.ok(INSTALL_STEPS.some(s => s.action?.kind === 'copy' && s.action.value === 'chrome://extensions'));
  assert.deepEqual(INSTALL_STEPS.at(-1)!.action, { kind: 'link', label: 'Open Discord in Chrome', value: 'https://discord.com/app' });
});
