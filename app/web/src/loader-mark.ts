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
export const LOADER = `<div class="loader" role="progressbar" aria-label="Loading the site" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">${MARK}</div>`;
