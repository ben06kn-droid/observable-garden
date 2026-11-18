// The loading screen's drawing (src/loader.ts, src/styles/loader.css), as markup: written into the one-page site's
// HTML at build time (vite.config.ts), so it is on screen from the first frame, and made by the preview page.
export const MARK = `<svg class="mark" viewBox="0 0 160 160" aria-hidden="true"><g class="all">
  <circle class="ring" cx="80" cy="80" r="52" pathLength="1"/>
  <g class="half ld-top"><path d="M 28 80 A 52 52 0 0 1 132 80"/></g>
  <g class="half ld-bottom"><path d="M 132 80 A 52 52 0 0 1 28 80"/></g>
  <line class="cut" x1="20" y1="80" x2="140" y2="80" pathLength="1"/>
</g></svg>
<svg class="tank" viewBox="-1 -15 78 400" aria-hidden="true">
  <defs><clipPath id="ld-box"><polygon points="0,0 20,-14 76,-14 76,370 56,384 0,384"/></clipPath></defs>
  <g clip-path="url(#ld-box)"><polygon class="level" points="0,0 20,-14 76,-14 76,520 0,520"/></g>
  <path class="edge" d="M 0 0 H 56 V 384 H 0 Z M 0 0 L 20 -14 H 76 L 56 0 M 76 -14 V 370 L 56 384"/>
</svg>`;

// The percent counter beside the box: numerals built from square blocks on a 5 x 7 grid, like a pixel display,
// drawn as one SVG path of 4 px squares (28 px tall), so no font is needed. Three fixed-width digit cells, right
// aligned (nothing moves sideways as the number grows), then a "%" in the same blocks. src/loader.ts redraws the
// digits as the number changes.
const GLYPHS: Record<string, string[]> = {
  "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
  "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
  "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
  "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
  "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
  "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
  "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
  "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
  "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
  "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
  "%": ["11000", "11001", "00010", "00100", "01000", "10011", "00011"],
};
const BLOCK = 4, CELL = 5 * BLOCK + BLOCK;   // a block; a cell is five blocks wide and one block of space
const glyph = (ch: string, x0: number) => (GLYPHS[ch] ?? []).flatMap((row, r) => [...row].map((b, c) => b === "1" ? `M${x0 + c * BLOCK} ${r * BLOCK}h${BLOCK}v${BLOCK}h-${BLOCK}z` : "")).join("");
/** the three digit cells' path for a whole number 0-100, right aligned */
export const counterDigits = (n: number) => [...String(Math.max(0, Math.min(100, Math.floor(n)))).padStart(3, " ")].map((ch, i) => ch === " " ? "" : glyph(ch, i * CELL)).join("");
const COUNTER_W = 4 * CELL - BLOCK, COUNTER_H = 7 * BLOCK;
export const COUNTER = `<svg class="count" viewBox="0 0 ${COUNTER_W} ${COUNTER_H}" aria-hidden="true"><path class="digits" d="${counterDigits(0)}"/><path d="${glyph("%", 3 * CELL)}"/></svg>`;
export const LOADER = `<div class="loader" role="progressbar" aria-label="Loading the site" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" aria-valuetext="0%">${MARK}${COUNTER}</div>`;
