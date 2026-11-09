// Single source of truth for keyboard shortcuts: shown in the hold-Tab overlay and the settings footer.
// Handlers live in App.svelte `onKey`. Keep this list in sync when adding a shortcut.
export const HOTKEYS = [
  ['View', [
    ['Tab (hold)', 'Show this cheat sheet'],
    ['S', 'Open / close settings'],
    ['F', 'Fullscreen'],
    ['G', 'Cycle grouping (flat → asset class → broker → sector)'],
    ['M', 'Merge the same holding across accounts'],
  ]],
  ['Filter', [
    ['1', 'Toggle Indian stocks'],
    ['2', 'Toggle US stocks'],
    ['3', 'Toggle mutual funds'],
    ['4', 'Toggle other assets'],
    ['0', 'Show everything'],
    ['Shift + click chip', 'Show only that type or account'],
  ]],
  ['Privacy', [
    ['H', 'Hide / show all amounts'],
  ]],
  ['General', [
    ['Esc', 'Close settings / dialogs'],
  ]],
];
