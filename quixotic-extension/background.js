// Toolbar button opens the side panel; nothing runs in the background otherwise.
chrome.sidePanel.setPanelBehavior({openPanelOnActionClick: true}).catch(console.error);
