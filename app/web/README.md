# app/web: the gate in the browser

A static site. The gate runs in the visitor's browser: a Web Worker loads Pyodide and the
observable-garden package, and calls `quixote.audit.audit_log`, the function behind `quixote audit`.
Nothing is computed on a server.

## Build

Node 22.12 or later (pinned in development: 24.21.0).

    npm ci
    npm run build          # fetch and check Pyodide, check examples and wheel, typecheck, vite build, check dist
    npm run preview        # serve dist/ with vercel.json's headers on 127.0.0.1:4173

| script | what it does |
|---|---|
| `scripts/fetch_pyodide.mjs` | puts the pinned Pyodide files in `public/pyodide/<version>/` and checks each against `MANIFEST.json` |
| `scripts/build_wheel.py` (`npm run build-wheel`) | builds the observable-garden wheel from `git archive HEAD`, the commit in its version |
| `scripts/check_wheel.mjs` | the wheel matches its manifest, and the package source has not changed since |
| `scripts/copy_examples.mjs`, `check_examples.mjs` | copies the demo's examples from `examples/`; the check fails if a copy differs |
| `scripts/make_overview_tree.py` (`--check`) | the trees behind the overview page, from the worker's own Python |
| `scripts/make_licenses.py` | `public/licenses.txt`, from the components themselves |
| `scripts/check_dist.mjs` (`--update`) | no inline script or style, nothing from another origin, every pinned file matches `ASSETS.lock.json` |
| `scripts/equivalence.mjs` | the browser build against the CLI on every example (below) |
| `scripts/browser_check.mjs` | the built site in headless Chrome under the production headers: CSP violations, errors, timings, screenshots |
| `scripts/mock_anthropic.mjs`, `mock_providers.mjs` | stand-ins for the providers' APIs (Anthropic's Messages API, OpenAI's Responses API, chat completions as OpenRouter and a local server speak it), for tests only: each checks every request the run page sends; `--run-page` runs the page against all four |

## Why Vite

The CSP forbids inline scripts (`script-src 'self' 'wasm-unsafe-eval'`, no `unsafe-inline`). Next's
static export inlines its hydration and route data scripts into every page, so it would need
`unsafe-inline` or per-build hashes. Vite's production HTML carries only external
`<script type="module" src=…>` tags, and `check_dist.mjs` enforces that. The pages are plain
TypeScript and DOM: there is no framework at runtime.

## The gate

- `src/gate.worker.ts` owns Pyodide. Messages in: `load`; `audit {log, panel, cls, B, seed,
  replicatePaths}`. Out: `loaded`, `search {tree}` (the logged search, for drawing, before the
  bootstrap starts), `progress {stage, done, total}`, `result {AuditResult.to_dict(), replicate paths}`
  (the exit code is a field of the result), `refused {message}` for `AuditRefused`, `error`.
- `src/gate.ts`: `loadGate()` and `gate.audit(inputs, {onSearch, onProgress})`. The page never runs Python.
- `src/py/glue.py`, run in the worker: registers the two stand-ins (only where the real package
  cannot be imported: `estimator.block_length.install_as_arch`, `estimator.scipy_lite.install_as_scipy`),
  reads the search back from the log, and calls `audit_log`.

## Equivalence with the CLI

    node scripts/equivalence.mjs --python python3

Runs the shipped build (Pyodide from `public/pyodide/`, the wheel from `public/py/`, the worker's own
glue with both stand-ins registered, the served example copies) and `quixote audit --json` on each
example, at the B the demo uses. Verdict, exit code, reasons and support must be identical and every
number within 1e-9; the largest difference is reported. It also runs the full run once per provider (Anthropic,
OpenAI, OpenRouter, a local server), each against its mock, and audits each browser-written log with the CLI; and it holds
the Sancho page's config hash (`src/levers.ts`) equal to `sancho.config.sha256_of` on the default and tailored configs. Last run (wheel 6a13c9a): verdicts, exit codes,
reasons and p values identical on all three; largest difference 2.2e-16, the restart example's class bar at B 500;
every other number exactly equal.

## The Sancho page and the viewer

`sancho.html` (`src/pages/sancho.ts`, `src/levers.ts`): Sancho does not run in a browser (LightGBM has no browser
build). The page edits `sancho/config.json`'s levers, writes the file `quixote sancho --config` reads, and shows its
config hash; the install line is one constant, `src/install.ts`. `viewer.html` (`src/pages/viewer.ts`): a log and its
result (with the panel and class, which the worker's package replays to draw the search), or `sancho.json`, drawn in
the run page's scene (`src/scene.ts`; Sancho as the bonsai in its pot, `src/bonsai.ts`). Checked by
`node scripts/browser_check.mjs --pages --fixtures DIR` (DIR: `result.json` from `quixote audit --json` on the bundled
log at B 500, and `sancho_out/sancho.json` from `quixote sancho` on a panel of at least 764 rows).

## Demo examples

`scripts/examples.mjs`: nothing to find (B 2000), planted edge (B 2000), a longer search (B 500: it
declares no stop rule, so each replicate runs to its 60-move budget; at B 2000 it takes about 60 s under
Pyodide). The 82,240-member ETF class is too large for a browser and will be a recorded replay; the
format is in `docs.html`. No recording exists yet.

## Deploy (Vercel)

Settings, all of which `vercel.json` carries except the first two, which are set when the project is
created:

| setting | value |
|---|---|
| Root directory | `app/web` |
| Framework preset | Other (`"framework": null`) |
| Install command | `npm ci` |
| Build command | `npm run build` (fetches and checks Pyodide, checks the examples and the wheel, typechecks, builds, checks `dist/`) |
| Output directory | `dist` |
| Node.js version | 22.x or 24.x (`engines`: `>=22.12.0`) |
| Environment variables | none |
| Headers | in `vercel.json`: the CSP and security headers on every path; immutable caching for `/assets/`, `/py/*.whl` and `/pyodide/314.0.7/`; revalidation for `.json` and `.html` |
| Set in the dashboard, not in code | Firewall and rate limits; deployment protection for previews if wanted |

A preview deploy, from this directory, logged in to the account:

    npx vercel@64.0.2 login
    npx vercel@64.0.2 deploy

`check_wheel.mjs` skips its git-history check when the build runs from an uploaded copy without
history (as `vercel deploy` from a local directory does); CI runs it with full history.
