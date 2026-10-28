// A stand-in for the Claude Messages API, for tests only: it answers like the API (a message with a
// thinking block and one tool_use block, usage, stop_reason "tool_use"; errors in the API's shape)
// with a fixed, deterministic search, so a full run can be tested end to end without a key or any
// network. Used two ways: `reply(body)` as a function (scripts/equivalence.mjs, inside Node) and
// `handle(req, res)` over HTTP (scripts/serve_dist.mjs mounts it at /__mock/anthropic/v1/messages
// when asked to; the run page only lets the provider URL be overridden on 127.0.0.1 or localhost).
//
// Keys: "sk-ant-bad" -> 401, "sk-ant-ratelimit" -> 429, "sk-ant-nocredit" -> 400 credit message,
// "sk-ant-badversion" -> a long 400 of the kind a rejected anthropic-version would give;
// anything else is accepted. Every request is checked for what the run page must send.

export const LONG_400 = 'anthropic-version: "2026-10-21" is not a supported version for this request. Use one of the versions listed at https://platform.claude.com/docs/en/api/versioning, or omit the header to use your organization\'s default; beta header "server-side-fallback-2026-07-01" was also checked and is valid for this model.';

export const SCRIPT = [
  ["declare_triggers", { triggers: [{ trigger: "last_gain_at_most", param: 0.0, action: "stop" }] }],
  ["init", {}],
  ["extend_best", {}],
  ["extend_best", {}],
  ["swap_worst", {}],
  ["refine", {}],
  ["predict", { mean: 0.2, sd: 0.5, note: "a weak edge at best" }],
  ["submit", {}],
];

/** What the run page must send; returns a problem or null. */
export function check(body, headers = null) {
  if (headers) {
    if (!headers["x-api-key"]) return "no x-api-key header";
    if (headers["anthropic-version"] !== "2026-10-21") return `anthropic-version ${headers["anthropic-version"]}`;
    if (headers["anthropic-dangerous-direct-browser-access"] !== "true") return "no direct-browser-access header";
    if (body.fallbacks && headers["anthropic-beta"] !== "server-side-fallback-2026-07-01") return "fallbacks without its beta header";
  }
  if (!body.model || !body.max_tokens || !Array.isArray(body.messages) || !Array.isArray(body.tools)) return "not a Messages request";
  if (body.tool_choice?.type !== "auto" || body.tool_choice?.disable_parallel_tool_use !== true) return "tool_choice must be auto, one call per turn";
  if ("temperature" in body || "top_p" in body || "top_k" in body) return "sampling parameters are refused by the API";
  return null;
}

export function reply(body) {
  const turns = body.messages.filter((m) => m.role === "assistant").length;
  const [name, input] = SCRIPT[Math.min(turns, SCRIPT.length - 1)];
  const chars = JSON.stringify(body).length;
  return {
    id: `msg_mock_${turns}`, type: "message", role: "assistant", model: body.model,
    content: [{ type: "thinking", thinking: "", signature: `mock-${turns}` },
              { type: "tool_use", id: `toolu_mock_${turns}`, name, input }],
    stop_reason: "tool_use", stop_details: null,
    usage: { input_tokens: Math.round(chars / 4), output_tokens: 60, cache_read_input_tokens: 0 },
  };
}

const err = (type, message) => JSON.stringify({ type: "error", error: { type, message } });

export function handle(req, res) {
  const cors = { "access-control-allow-origin": req.headers.origin ?? "*", "access-control-allow-headers": "*", "access-control-allow-methods": "POST, OPTIONS" };
  if (req.method === "OPTIONS") { res.writeHead(204, cors); res.end(); return; }
  let data = "";
  req.on("data", (c) => { data += c; });
  req.on("end", () => {
    const send = (code, text) => { res.writeHead(code, { ...cors, "content-type": "application/json" }); res.end(text); };
    let body;
    try { body = JSON.parse(data); } catch { return send(400, err("invalid_request_error", "the body is not JSON")); }
    const key = req.headers["x-api-key"];
    if (key === "sk-ant-bad") return send(401, err("authentication_error", "invalid x-api-key"));
    if (key === "sk-ant-ratelimit") return send(429, err("rate_limit_error", "Number of request tokens has exceeded your per-minute rate limit"));
    if (key === "sk-ant-badversion") return send(400, err("invalid_request_error", LONG_400));
    if (key === "sk-ant-nocredit") return send(400, err("invalid_request_error", "Your credit balance is too low to access the Anthropic API."));
    const problem = check(body, req.headers);
    if (problem) return send(400, err("invalid_request_error", `mock: ${problem}`));
    send(200, JSON.stringify(reply(body)));
  });
}
