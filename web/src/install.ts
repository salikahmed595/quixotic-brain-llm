/* Owner 2026-10-29: guided install of the Discord reply helper (Chrome extension in quixotic-extension/).
   The zip is built into public/downloads by web's prebuild; not a PRD feature (docs/PRD_GAPS.md). */
export const DOWNLOAD_URL = '/downloads/quixotic-reply-assistant.zip';
export const EXTENSION_FOLDER = 'quixotic-reply-assistant';   // the folder inside the zip (quixotic-extension/scripts/zip.js)

export type StepAction = { kind: 'download' | 'copy' | 'link'; label: string; value: string };
export type InstallStep = { title: string; text: string; tip?: string; action?: StepAction };

export const INSTALL_STEPS: InstallStep[] = [
  { title: 'Download the helper', text: 'Click the button below. A small file named quixotic-reply-assistant.zip is saved to your Downloads folder.',
    tip: 'Use Google Chrome (or Microsoft Edge) on your computer for all the steps.',
    action: { kind: 'download', label: 'Download the helper', value: DOWNLOAD_URL } },
  { title: 'Unzip it', text: `Open your Downloads folder, right-click quixotic-reply-assistant.zip, choose "Extract All…" and click "Extract". You now have a folder named ${EXTENSION_FOLDER}.`,
    tip: 'Keep this folder. Chrome uses it, so do not delete or move it later.' },
  { title: "Open Chrome's extensions page", text: 'Click the button to copy the address, then click Chrome\'s address bar at the top, paste it (Ctrl+V) and press Enter.',
    tip: 'Websites are not allowed to open this page for you, so it has to be pasted.',
    action: { kind: 'copy', label: 'Copy chrome://extensions', value: 'chrome://extensions' } },
  { title: 'Turn on Developer mode', text: 'On the extensions page, find the "Developer mode" switch in the top-right corner and turn it on.',
    tip: 'New buttons appear at the top left. That is expected.' },
  { title: 'Load the helper', text: `Click "Load unpacked" (top left). Choose the ${EXTENSION_FOLDER} folder from step 2 and click "Select Folder".`,
    tip: 'A card named "Quixotic Reply Assistant" appears. That means it is installed.' },
  { title: 'Pin it to the toolbar', text: 'Click the puzzle-piece icon at the top right of Chrome, then click the pin next to "Quixotic Reply Assistant". An orange Q icon stays on your toolbar.' },
  { title: 'Use it on Discord', text: 'Open Discord in Chrome (not the Discord app), open a customer chat and click the orange Q icon. The panel then guides you: sign in, add staff names, click Suggest Reply, copy the reply.',
    tip: 'The helper never sends anything. You paste the reply into Discord, check it and send it yourself.',
    action: { kind: 'link', label: 'Open Discord in Chrome', value: 'https://discord.com/app' } },
];
