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
- The run page (`run.html`) takes a visitor's own model API key. It is held in one variable in the page
  for one run, sent with the run message to the worker, put only into the `x-api-key` header of
  requests made from the worker straight to the provider (`connect-src` names `'self'` and
  `https://api.anthropic.com` only), and cleared, with the field, when the run ends in any way or the
  page is left. It is never written to storage, never in a URL, never in the log, the result or the
  share link, and scrubbed from any error text. The panel and the class are read in the worker by the
  package's loaders (`np.load(..., allow_pickle=False)`) with size limits (512 MB, 4 MB) and checked
  before the key is used. The browser check (`--run-page`) verifies the key appears nowhere in the
  page, the URL or storage, and that every request goes to the site or the provider.

## Headers (app/web/vercel.json)

- `Content-Security-Policy: default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self';
  connect-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; object-src 'none';
  base-uri 'none'; frame-ancestors 'none'; form-action 'none'; upgrade-insecure-requests`.
  Everything not named is refused. No `unsafe-inline` and no `unsafe-eval`: `scripts/check_dist.mjs` fails the build on any inline
  script, inline handler, inline style or `<style>` block, and `scripts/browser_check.mjs` runs the
  demo in Chrome under these headers and fails on any CSP violation. `'wasm-unsafe-eval'` is what
  WebAssembly compilation needs; Pyodide needs nothing more.
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`, `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: no-referrer`, a `Permissions-Policy` denying camera, microphone,
  geolocation, the motion sensors, payment and USB, `Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy:
  same-origin`, `X-Frame-Options: DENY`. Errors get a generic `404.html`.

## Supply chain

- Every script, WebAssembly module, wheel and font is served from the site itself. Pyodide 314.0.7
  and the five package wheels the audit needs are fetched at build time and checked against
  `public/pyodide/MANIFEST.json` (sha256); the observable-garden wheel is built from the repository's
  own source at a commit and checked against `public/py/MANIFEST.json`; fonts come from npm packages
  pinned in `package-lock.json`. `ASSETS.lock.json` holds the sha256 of every pinned file in the
  built site, and the build fails if any differs.
- Pinned files are cached as immutable for a year: Vite's hashed assets (scripts, styles, fonts), the
  observable-garden wheel (its name carries the commit), and Pyodide under `/pyodide/314.0.7/` (the
  version in the path; the build fails if `vercel.json` does not name the pinned version).
- npm dependencies are pinned exactly, with a lockfile. CI runs `npm audit --audit-level=high` and
  `pip-audit` (which has no severity threshold: it fails on any known vulnerability, stricter than
  high), and Dependabot watches npm, pip and the workflow actions.

## Not in the repository

Per-IP rate limits, the firewall and DDoS protection are the host's (Vercel's) and are configured in
its dashboard, not in code. A static site has no queue or daily run cap to set: each run uses the
visitor's own machine.
