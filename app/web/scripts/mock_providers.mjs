// Stand-ins for the providers other than Anthropic, for tests only (scripts/mock_anthropic.mjs is
// Anthropic's): OpenAI's Responses API, and chat completions as OpenRouter and a local server speak
// it, with OpenRouter's /models list. Each answers the same fixed search as the Anthropic mock
// (mock_anthropic.SCRIPT), in its own shape, and checks every request for what the run page must
// send: the tools in the provider's form, the key only in its header, one tool call per turn, the
// harness's answer tied to the call it answers, and the model's own turn passed back unchanged (its
// encrypted reasoning items or reasoning details). On the third turn each mock returns two tool calls
// at once; the page must send back only the first.
//
// Keys (any provider): ending "-bad" -> 401, "-ratelimit" -> 429, "-nocredit" -> the provider's
// no-credit error (OpenAI 429 insufficient_quota, OpenRouter 402), "-badeffort" -> the 400 a model
// gives for an effort level it does not take; anything else is accepted. A local server takes no key.
//   handle(req, res)      the routes /__mock/openai/v1/responses, /__mock/openrouter/api/v1/... and
//                         /__mock/anthropic/v1/messages (serve_dist.mjs mounts it when asked to)
//   serveLocal(port)      a local server at http://localhost:PORT/v1/chat/completions, on its own port
//   reply / check         the same, as functions (scripts/equivalence.mjs)
import { createServer } from "node:http";
import { handle as anthropic, SCRIPT } from "./mock_anthropic.mjs";

export const BAD_EFFORT = "Unsupported value: 'reasoning.effort' does not support 'none' with this model. Supported values are: 'low', 'medium', 'high', 'xhigh' and 'max'.";
const TWO_CALLS_AT = 2;              // the turn (0-based) on which a mock names two tools at once
const SPURIOUS = ["flip", {}];

const step = (n) => SCRIPT[Math.min(n, SCRIPT.length - 1)];

// ---- OpenAI, the Responses API -------------------------------------------------------------------
export function checkResponses(body, headers = null) {
  if (headers) {
    if (!/^Bearer \S+$/.test(headers.authorization ?? "")) return "no Authorization: Bearer header";
    if (headers["x-api-key"]) return "an x-api-key header sent to OpenAI";
  }
  if (!body.model || typeof body.instructions !== "string" || !Array.isArray(body.input) || !Array.isArray(body.tools)) return "not a Responses request";
  if (body.tools.some((t) => t.type !== "function" || !t.name || !t.parameters)) return "tools not in the Responses function form";
  if (body.tool_choice !== "auto" || body.parallel_tool_calls !== false) return "tool_choice must be auto, one call per turn";
  if (body.store !== false || !(body.include ?? []).includes("reasoning.encrypted_content")) return "must be stateless: store false, encrypted reasoning included";
  if (body.reasoning && typeof body.reasoning.effort !== "string") return "reasoning.effort is not a level";
  for (let i = 0; i < body.input.length; i++) {
    const it = body.input[i];
    if (it.type === "reasoning" && !it.encrypted_content) return "a reasoning item came back without its encrypted content";
    if (it.type === "function_call_output") {
      const prev = body.input[i - 1];
      if (prev?.type !== "function_call" || prev.call_id !== it.call_id) return "a function_call_output not tied to the call before it";
    }
  }
  const calls = body.input.filter((x) => x.type === "function_call");
  for (let t = 0; t < calls.length; t++) if (calls[t].name !== step(t)[0]) return `turn ${t}: the history does not carry the model's own call back (${calls[t].name})`;
  if (calls.length > TWO_CALLS_AT && body.input.filter((x) => x.type === "reasoning").length !== calls.length) return "reasoning items dropped from the history";
  return null;
}

export function replyResponses(body) {
  const n = body.input.filter((x) => x.type === "function_call").length;
  const [name, input] = step(n);
  const fc = (i, nm, args) => ({ type: "function_call", id: `fc_mock_${n}_${i}`, call_id: `call_mock_${n}_${i}`, name: nm, arguments: JSON.stringify(args), status: "completed" });
  const output = [{ type: "reasoning", id: `rs_mock_${n}`, summary: [], encrypted_content: `enc-mock-${n}` }, fc(0, name, input)];
  if (n === TWO_CALLS_AT) output.push(fc(1, ...SPURIOUS));
  return { id: `resp_mock_${n}`, object: "response", status: "completed", model: body.model, output,
           usage: { input_tokens: Math.round(JSON.stringify(body).length / 4), output_tokens: 70, input_tokens_details: { cached_tokens: 0 } } };
}

// ---- chat completions (OpenRouter, a local server) -------------------------------------------------
export function checkChat(body, headers = null, { local = false } = {}) {
  if (headers) {
    if (!local && !/^Bearer \S+$/.test(headers.authorization ?? "")) return "no Authorization: Bearer header";
    if (headers["x-api-key"]) return "an x-api-key header sent";
  }
  if (!body.model || !Array.isArray(body.messages) || !Array.isArray(body.tools)) return "not a chat-completions request";
  if (body.messages[0]?.role !== "system") return "the prompt is not the first, system, message";
  if (body.tools.some((t) => t.type !== "function" || !t.function?.name || !t.function?.parameters)) return "tools not in the chat-completions function form";
  if (local) { if ("tool_choice" in body || "parallel_tool_calls" in body) return "a local server is sent tool_choice, which Ollama does not take"; }
  else if (body.tool_choice !== "auto" || body.parallel_tool_calls !== false) return "tool_choice must be auto, one call per turn";
  if (body.reasoning && typeof body.reasoning.effort !== "string") return "reasoning.effort is not a level";
  if ("reasoning_effort" in body) return "reasoning_effort sent; the run page sends reasoning.effort";
  for (let i = 0; i < body.messages.length; i++) {
    const m = body.messages[i];
    if (m.role === "assistant") {
      if ((m.tool_calls ?? []).length > 1) return "an assistant turn sent back with more than one tool call";
      if (!local && !m.reasoning_details) return "the reasoning details were not passed back";
    }
    if (m.role === "tool") {
      const prev = body.messages[i - 1];
      if (prev?.role !== "assistant" || prev.tool_calls?.[0]?.id !== m.tool_call_id) return "a tool message not tied to the call before it";
    }
  }
  return null;
}

export function replyChat(body, { local = false } = {}) {
  const n = body.messages.filter((m) => m.role === "assistant").length;
  const [name, input] = step(n);
  const call = (i, nm, args) => ({ id: `call_mock_${n}_${i}`, type: "function", function: { name: nm, arguments: JSON.stringify(args) } });
  const tool_calls = [call(0, name, input)];
  if (n === TWO_CALLS_AT) tool_calls.push(call(1, ...SPURIOUS));
  const message = { role: "assistant", content: null, tool_calls, ...(local ? {} : { reasoning_details: [{ type: "reasoning.encrypted", data: `enc-mock-${n}` }] }) };
  return { id: `gen_mock_${n}`, object: "chat.completion", model: body.model, choices: [{ index: 0, message, finish_reason: "tool_calls" }],
           usage: { prompt_tokens: Math.round(JSON.stringify(body).length / 4), completion_tokens: 65, prompt_tokens_details: { cached_tokens: 0 } } };
}

/** OpenRouter's /models, a few entries in its shape: two take tools, one does not (the page drops it) */
export const ROUTER_MODELS = { data: [
  { id: "qwen/qwen3-235b-a22b", name: "Qwen: Qwen3 235B A22B", pricing: { prompt: "0.00000013", completion: "0.0000006" },
    top_provider: { max_completion_tokens: 8192 }, supported_parameters: ["tools", "tool_choice", "reasoning", "max_tokens"] },
  { id: "deepseek/deepseek-v4", name: "DeepSeek: DeepSeek V4", pricing: { prompt: "0.0000003", completion: "0.0000012" },
    top_provider: { max_completion_tokens: null }, supported_parameters: ["tools", "tool_choice", "reasoning", "max_tokens"] },
  { id: "example/no-tools", name: "Example: No Tools", pricing: { prompt: "0", completion: "0" }, top_provider: {}, supported_parameters: ["max_tokens"] },
] };

// ---- over HTTP ----------------------------------------------------------------------------------
const cors = (req) => ({ "access-control-allow-origin": req.headers.origin ?? "*", "access-control-allow-headers": "*", "access-control-allow-methods": "GET, POST, OPTIONS" });

function respond(req, res, kind) {
  if (req.method === "OPTIONS") { res.writeHead(204, cors(req)); res.end(); return; }
  let data = "";
  req.on("data", (c) => { data += c; });
  req.on("end", () => {
    const send = (code, obj) => { res.writeHead(code, { ...cors(req), "content-type": "application/json" }); res.end(JSON.stringify(obj)); };
    let body;
    try { body = JSON.parse(data); } catch { return send(400, { error: { message: "the body is not JSON", type: "invalid_request_error" } }); }
    const key = (req.headers.authorization ?? "").replace(/^Bearer /, "");
    if (kind !== "local") {
      if (key.endsWith("-bad")) return send(401, { error: kind === "openrouter" ? { code: 401, message: "No auth credentials found" } : { message: "Incorrect API key provided: sk-...-bad.", type: "invalid_request_error", code: "invalid_api_key" } });
      if (key.endsWith("-ratelimit")) return send(429, { error: kind === "openrouter" ? { code: 429, message: "Rate limit exceeded: free-models-per-min." } : { message: "Rate limit reached for requests per min.", type: "requests", code: "rate_limit_exceeded" } });
      if (key.endsWith("-nocredit")) return kind === "openrouter"
        ? send(402, { error: { code: 402, message: "Insufficient credits. Add more using https://openrouter.ai/settings/credits" } })
        : send(429, { error: { message: "You exceeded your current quota, please check your plan and billing details.", type: "insufficient_quota", code: "insufficient_quota" } });
      if (key.endsWith("-badeffort")) return send(400, kind === "openrouter" ? { error: { code: 400, message: BAD_EFFORT } } : { error: { message: BAD_EFFORT, type: "invalid_request_error", param: "reasoning.effort", code: "unsupported_value" } });
    }
    const problem = kind === "openai" ? checkResponses(body, req.headers) : checkChat(body, req.headers, { local: kind === "local" });
    if (problem) return send(400, { error: { message: `mock: ${problem}`, type: "invalid_request_error" } });
    send(200, kind === "openai" ? replyResponses(body) : replyChat(body, { local: kind === "local" }));
  });
}

/** Every mock route the test server mounts; false if the path is not one of them. */
export function handle(req, res, path) {
  if (path === "/__mock/anthropic/v1/messages") { anthropic(req, res); return true; }
  if (path === "/__mock/openai/v1/responses") { respond(req, res, "openai"); return true; }
  if (path === "/__mock/openrouter/api/v1/chat/completions") { respond(req, res, "openrouter"); return true; }
  if (path === "/__mock/openrouter/api/v1/models") {
    res.writeHead(200, { ...cors(req), "content-type": "application/json" }); res.end(JSON.stringify(ROUTER_MODELS)); return true;
  }
  return false;
}

/** A local OpenAI-compatible server on its own port (loopback), as Ollama would be. */
export function serveLocal(port) {
  return new Promise((resolve) => {
    const srv = createServer((req, res) => {
      const path = new URL(req.url, "http://x").pathname;
      if (path === "/v1/chat/completions") return respond(req, res, "local");
      res.writeHead(404, cors(req)); res.end();
    });
    srv.listen(port, "127.0.0.1", () => resolve(srv));        // loopback only; the page reaches it as localhost
  });
}
