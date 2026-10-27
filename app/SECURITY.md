# Security of the Quixote site (app/web)

Report a vulnerability through GitHub's private advisory form:
https://github.com/ben06kn-droid/observable-garden/security/advisories/new
(also at `/.well-known/security.txt` on the site).

## What the site is

A static site. There is no server-side code, no database, no account and no API of ours: the host
serves files, and the gate runs in the visitor's browser, in a Web Worker, under Pyodide. Nothing a
visitor does is sent to us.

## What it does not do

- It executes no code supplied by a visitor. The demo audits bundled files; later phases that read a
  visitor's panel will parse it only with the repository's loader (`quixote.panel.read`, which calls
  `np.load(..., allow_pickle=False)`), inside the worker, with size limits.
- It stores nothing: no cookies, no local or session storage, no IndexedDB, no analytics, no
  third-party requests.
- It handles no secrets in this phase. When a later phase lets a visitor use their own model API key,
  the key will go from the browser straight to the provider (`connect-src` will then name
  `https://api.anthropic.com` and `https://api.openai.com` only), held in memory for one run.

## Headers (app/web/vercel.json)

- `Content-Security-Policy: default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self';
  connect-src 'self'; img-src 'self'; style-src 'self'; font-src 'self'; object-src 'none';
  base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests`.
  No `unsafe-inline` and no `unsafe-eval`: `scripts/check_dist.mjs` fails the build on any inline
  script, inline handler, inline style or `<style>` block, and `scripts/browser_check.mjs` runs the
  demo in Chrome under these headers and fails on any CSP violation. `'wasm-unsafe-eval'` is what
  WebAssembly compilation needs; Pyodide needs nothing more.
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`, `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: no-referrer`, a `Permissions-Policy` denying sensors, camera,
  microphone, payment and USB, `Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy:
  same-origin`, `X-Frame-Options: DENY`. Errors get a generic `404.html`.

## Supply chain

- Every script, WebAssembly module, wheel and font is served from the site itself. Pyodide 314.0.7
  and the five package wheels the audit needs are fetched at build time and checked against
  `public/pyodide/MANIFEST.json` (sha256); the observable-garden wheel is built from the repository's
  own source at a commit and checked against `public/py/MANIFEST.json`; fonts come from npm packages
  pinned in `package-lock.json`. `ASSETS.lock.json` holds the sha256 of every pinned file in the
  built site, and the build fails if any differs.
- npm dependencies are pinned exactly, with a lockfile; CI runs `npm audit` and `pip-audit`, and
  Dependabot watches npm, pip and the workflow actions.

## Not in the repository

Per-IP rate limits, the firewall and DDoS protection are the host's (Vercel's) and are configured in
its dashboard, not in code. A static site has no queue or daily run cap to set: each run uses the
visitor's own machine.
