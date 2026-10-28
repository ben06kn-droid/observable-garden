// A shared result: the verdict and the hashes, read from the URL's fragment (which the browser never
// sends to a server), inflated and shown as plain type. It is unverified, and the page says so: it
// shows what the link claims and how to check it with the log, the panel, the class and the CLI.
import { h, MEANING, word } from "../common";

const body = document.getElementById("sh-body") as HTMLElement;

async function read(): Promise<Record<string, any> | null> {   // eslint-disable-line @typescript-eslint/no-explicit-any
  const m = /(?:^#|&)r=([A-Za-z0-9_-]+)/.exec(location.hash);
  if (!m) return null;
  const b64 = m[1].replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "===".slice((b64.length + 3) % 4));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  const text = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).text();
  return JSON.parse(text);
}

read().then((d) => {
  if (!d || d.v !== 1 || !d.result || !d.record) { h("p", null, "This link carries no result the page can read.", body); return; }
  const r = d.result, rec = d.record, w = word(String(r.status));
  h("p", "share-word", w, body);
  h("p", "meaning", MEANING[w] ?? "", body);
  const kv = h("dl", "kv", null, body);
  const fmt = (x: unknown, n: number) => (typeof x === "number" ? x.toFixed(n) : "n/a");
  const rows: [string, string][] = [["Submitted", `${(r.submitted_feature_names ?? []).join(" ")} · in-sample Sharpe ${fmt(r.submitted_sharpe, 3)}`],
    ["Bar", fmt(r.class_bar, 3)], ["p", fmt(r.p_replay, 4)], ["B", String(r.B)], ["Class size", String(r.class_size)],
    ["Panel", `${rec.panel_file} · ${rec.panel_sha256}`], ["Class", `${rec.class_file} · ${rec.class_sha256}`], ["Log", String(rec.log_sha256)],
    ["Model", String(rec.served_by && rec.served_by !== rec.model ? `${rec.model} (served by ${rec.served_by})` : rec.model)], ["Budget", `${rec.budget_moves} moves`],
    ["Prompt", rec.prompt === "edited" ? `edited, not the adapter's own: a different search · ${rec.prompt_sha256}` : `default · ${rec.prompt_sha256}`],
    ["Seed", String(rec.seed)], ["Audit id", String(rec.audit_id)], ["Package", String(rec.package)]];
  for (const [k, v] of rows) { h("dt", null, k, kv); h("dd", null, v, kv); }
  h("h2", null, "Check it", body);
  h("pre", "cmd", `quixote audit log.json --panel ${rec.panel_file} --class ${rec.class_file} --B ${r.B} --seed ${rec.seed}`, body);
  if (Array.isArray(r.reasons)) { h("h2", null, "Reasons, as the link states them", body); const ul = h("ul", "reasons", null, body); for (const x of r.reasons) h("li", null, String(x), ul); }
}).catch(() => { h("p", null, "This link is damaged: its fragment could not be read.", body); });
