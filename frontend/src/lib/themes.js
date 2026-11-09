import { interpolateLab } from 'd3-interpolate';

// Theme = flat map of design tokens. Every key becomes a CSS var (--bg, --profit, ...).
// To add a preset: append to PRESET_THEMES. Custom themes live in the customThemes store.
export const THEME_KEYS = [
  ['bg', 'Background'],
  ['surface', 'Panel'],
  ['surface-2', 'Panel inputs'],
  ['text', 'Text'],
  ['muted', 'Muted text'],
  ['accent', 'Accent'],
  ['profit', 'Profit (max)'],
  ['loss', 'Loss (max)'],
  ['neutral', 'Flat / 0%'],
  ['gap', 'Tile gap'],
];

const MONO = "ui-monospace, 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace";
const SANS = "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

export const PRESET_THEMES = [
  {
    id: 'terminal', name: 'Terminal', preset: true, font: MONO, radius: '0px',
    bg: '#000000', surface: '#0a0a0a', 'surface-2': '#141414', text: '#d4d4d4', muted: '#7a7a7a',
    accent: '#33ff99', profit: '#00c853', loss: '#ff3b30', neutral: '#1c1c1c', gap: '#000000',
  },
  {
    id: 'dark', name: 'Dark', preset: true, font: SANS, radius: '4px',
    bg: '#0f1115', surface: '#161a20', 'surface-2': '#1e232b', text: '#eef0f3', muted: '#8a93a0',
    accent: '#7aa2ff', profit: '#22a861', loss: '#e5484d', neutral: '#2a2f38', gap: '#0f1115',
  },
  {
    id: 'light', name: 'Light', preset: true, font: SANS, radius: '4px',
    bg: '#f4f5f7', surface: '#ffffff', 'surface-2': '#f0f1f4', text: '#14161a', muted: '#636b76',
    accent: '#2457d6', profit: '#15924a', loss: '#d32f2f', neutral: '#d8dbe0', gap: '#f4f5f7',
  },
  {
    id: 'colorblind', name: 'Colorblind (blue/orange)', preset: true, font: SANS, radius: '4px',
    bg: '#0e1116', surface: '#151a22', 'surface-2': '#1d2430', text: '#eef1f6', muted: '#8b95a5',
    accent: '#5aa9ff', profit: '#2f7fe0', loss: '#e8871e', neutral: '#2a303b', gap: '#0e1116',
  },
  {
    id: 'paper', name: 'Paper', preset: true, font: "Georgia, 'Iowan Old Style', serif", radius: '2px',
    bg: '#f3eee3', surface: '#fbf8f1', 'surface-2': '#efe8da', text: '#2b2620', muted: '#7d7364',
    accent: '#8a4b2a', profit: '#4c7a3a', loss: '#a8402f', neutral: '#ddd3c0', gap: '#f3eee3',
  },
];

export function allThemes(custom) {
  return [...PRESET_THEMES, ...(custom || [])];
}

export function findTheme(id, custom) {
  return allThemes(custom).find((t) => t.id === id) || PRESET_THEMES[0];
}

export function applyTheme(theme) {
  const root = document.documentElement.style;
  for (const [k] of THEME_KEYS) if (theme[k]) root.setProperty(`--${k}`, theme[k]);
  root.setProperty('--font', theme.font || SANS);
  root.setProperty('--radius', theme.radius || '4px');
  const meta = document.querySelector('meta[name="color-scheme"]');
  if (meta) meta.content = luminance(theme.bg) > 0.5 ? 'light' : 'dark';
}

/** Map a % change onto neutral→profit / neutral→loss. `full` = % at which colour saturates. */
export function makeColorScale(theme, full) {
  const up = interpolateLab(theme.neutral, theme.profit);
  const down = interpolateLab(theme.neutral, theme.loss);
  return (pct) => {
    if (pct == null || !Number.isFinite(pct)) return theme.neutral;
    // sqrt easing: small moves still visibly tint the tile
    const t = Math.min(1, Math.sqrt(Math.abs(pct) / full));
    return pct >= 0 ? up(t) : down(t);
  };
}

/** WCAG relative luminance of a hex / rgb() colour (0..1). */
export function luminance(color) {
  const rgb = parseColor(color);
  if (!rgb) return 0;
  const [r, g, b] = rgb.map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function textOn(color) {
  return luminance(color) > 0.33 ? '#111111' : '#ffffff';
}

function parseColor(c) {
  if (!c) return null;
  if (c.startsWith('#')) {
    let h = c.slice(1);
    if (h.length === 3) h = h.split('').map((x) => x + x).join('');
    const n = parseInt(h.slice(0, 6), 16);
    return Number.isNaN(n) ? null : [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const m = c.match(/rgba?\(([^)]+)\)/);
  return m ? m[1].split(',').slice(0, 3).map((x) => parseFloat(x)) : null;
}

export function newThemeFrom(base, name) {
  const id = 'custom-' + Math.random().toString(36).slice(2, 8);
  const { preset, ...rest } = base;
  return { ...rest, id, name: name || `${base.name} (custom)`, preset: false };
}

/** Validate an imported theme JSON (only known keys, colour-ish strings). */
export function sanitizeTheme(obj) {
  if (!obj || typeof obj !== 'object') throw new Error('Not a theme object');
  const out = newThemeFrom(PRESET_THEMES[1], String(obj.name || 'Imported theme').slice(0, 40));
  for (const [k] of THEME_KEYS) {
    if (typeof obj[k] === 'string' && /^#[0-9a-f]{3,8}$/i.test(obj[k])) out[k] = obj[k];
  }
  if (typeof obj.font === 'string' && obj.font.length < 200 && !/[;{}<>]/.test(obj.font)) out.font = obj.font;
  if (typeof obj.radius === 'string' && /^\d{1,2}px$/.test(obj.radius)) out.radius = obj.radius;
  return out;
}
