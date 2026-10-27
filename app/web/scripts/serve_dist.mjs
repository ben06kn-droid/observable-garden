// Serves dist/ on 127.0.0.1 with the headers vercel.json declares, so the content security policy
// and the rest can be tested before a deploy. Two of them only make sense over https and are left
// out here, on plain http: `upgrade-insecure-requests` (Safari applies it to localhost and would
// rewrite every request to an https port nobody listens on) and Strict-Transport-Security.
//   node scripts/serve_dist.mjs [port]
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(web, "dist");
const conf = JSON.parse(readFileSync(join(web, "vercel.json"), "utf8"));
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".wasm": "application/wasm", ".whl": "application/zip", ".zip": "application/zip",
  ".npz": "application/octet-stream", ".woff2": "font/woff2", ".woff": "font/woff", ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8" };
const rules = conf.headers.map((h) => ({ re: new RegExp("^" + h.source.replace(/\(\.\*\)/g, ".*") + "$"), headers: h.headers }));

export function serve(port = 4173) {
  return new Promise((resolve) => {
    const srv = createServer((req, res) => {
      let path = decodeURIComponent(new URL(req.url, "http://x").pathname);
      if (path.endsWith("/")) path += "index.html";
      let file = join(dist, path);
      if (!file.startsWith(dist) || !existsSync(file) || statSync(file).isDirectory()) { file = join(dist, "404.html"); res.statusCode = 404; }
      for (const r of rules) if (r.re.test(path)) for (const h of r.headers) {
        if (h.key === "Strict-Transport-Security") continue;
        res.setHeader(h.key, h.key === "Content-Security-Policy" ? h.value.replace(/;\s*upgrade-insecure-requests/, "") : h.value);
      }
      res.setHeader("Content-Type", TYPES[extname(file)] ?? "application/octet-stream");
      res.end(readFileSync(file));
    });
    srv.listen(port, "127.0.0.1", () => resolve(srv));
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const port = Number(process.argv[2] ?? 4173);
  await serve(port);
  console.log(`dist on http://127.0.0.1:${port}/ with vercel.json's headers`);
}
