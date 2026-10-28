// The providers the run page offers, and for each: where requests go, the request shape glue.py
// speaks to it, the effort parameter and every level the provider documents, and the models it
// lists with their list prices (dollars per million tokens, input and output). Every level is offered
// for every model; a model that refuses one answers with the provider's error, shown word for word.
// Sources, read 2026-10-28: Anthropic's model and effort tables; OpenAI's models and pricing pages and
// its reasoning guide (GPT-6 Astra and GPT-6.1 Sol take tools only through the Responses API);
// OpenRouter's reasoning-tokens page; Ollama's OpenAI-compatibility page (tools and reasoning.effort
// supported, tool_choice not).
import type { ProviderId } from "./types";

export interface Model { id: string; name: string; price?: [number, number] }
export interface Provider {
  id: ProviderId; label: string;
  /** the request's endpoint (Local: the base URL the visitor types, plus /chat/completions) */
  url: string;
  shape: "Messages API" | "Responses API" | "chat completions";
  effortParam: string; efforts: string[]; defaultEffort: string;
  keyPlaceholder: string; keyRequired: boolean;
  models: Model[];
}

const OPENAI_LEVELS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"];
/** Local: nothing is sent unless chosen, since servers and models differ in what they accept */
export const NOT_SENT = "not sent";
export const LOCAL_DEFAULT = "http://localhost:11434/v1";

export const PROVIDERS: Record<ProviderId, Provider> = {
  anthropic: {
    id: "anthropic", label: "Anthropic", url: "https://api.anthropic.com/v1/messages", shape: "Messages API",
    effortParam: "output_config.effort", efforts: ["low", "medium", "high", "xhigh", "max"], defaultEffort: "medium",
    keyPlaceholder: "sk-ant-…", keyRequired: true,
    models: [
      { id: "claude-fable-5-1", name: "Claude Fable 5.1", price: [10, 50] },
      { id: "claude-opus-5-5", name: "Claude Opus 5.5", price: [4, 20] },
      { id: "claude-sonnet-5-5", name: "Claude Sonnet 5.5", price: [2, 10] },
      { id: "claude-haiku-5-5", name: "Claude Haiku 5.5", price: [0.1, 0.5] },
    ],
  },
  openai: {
    id: "openai", label: "OpenAI", url: "https://api.openai.com/v1/responses", shape: "Responses API",
    effortParam: "reasoning.effort", efforts: OPENAI_LEVELS, defaultEffort: "medium",
    keyPlaceholder: "sk-…", keyRequired: true,
    models: [
      { id: "gpt-6-astra", name: "GPT-6 Astra", price: [10, 50] },
      { id: "gpt-6.1-sol", name: "GPT-6.1 Sol", price: [2, 10] },
      { id: "gpt-6.1-terra", name: "GPT-6.1 Terra", price: [1, 5] },
      { id: "gpt-6-luna", name: "GPT-6 Luna", price: [0.1, 0.5] },
    ],
  },
  openrouter: {
    id: "openrouter", label: "OpenRouter", url: "https://openrouter.ai/api/v1/chat/completions", shape: "chat completions",
    effortParam: "reasoning.effort", efforts: OPENAI_LEVELS, defaultEffort: "medium",
    keyPlaceholder: "sk-or-…", keyRequired: true,
    models: [],                          // fetched from its /models endpoint once a key is entered
  },
  local: {
    id: "local", label: "Local (OpenAI-compatible)", url: LOCAL_DEFAULT, shape: "chat completions",
    effortParam: "reasoning.effort", efforts: [NOT_SENT, ...OPENAI_LEVELS], defaultEffort: NOT_SENT,
    keyPlaceholder: "none needed", keyRequired: false,
    models: [],
  },
};

export const OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models";

/** Anthropic's server-side fallbacks ("default") are offered on these models only. */
export const FALLBACK_MODELS = new Set(["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5"]);

/** A local server's URL, if it is one the content security policy lets the page reach: http on
 *  localhost or 127.0.0.1, any port (connect-src allows exactly http://localhost:* and http://127.0.0.1:*). Returns the chat-completions endpoint and the host, or a reason. */
export function localEndpoint(typed: string): { url: string; host: string } | { error: string } {
  let u: URL;
  try { u = new URL(typed.trim()); } catch { return { error: "That is not a URL (for Ollama: http://localhost:11434/v1)." }; }
  if (u.protocol !== "http:") return { error: "A local server is reached over http (the site's content security policy allows http://localhost and http://127.0.0.1 only)." };
  if (u.hostname !== "localhost" && u.hostname !== "127.0.0.1")
    return { error: "A local server must be at localhost or 127.0.0.1: the site's content security policy allows nothing else." };
  if (u.username || u.password || u.search || u.hash) return { error: "Give the server's base URL only, with no credentials, query or fragment." };
  return { url: `${u.origin}${u.pathname.replace(/\/+$/, "")}/chat/completions`, host: u.host };
}

/** OpenRouter's /models list, kept to the models that take tools (the harness's moves are tool calls). */
export interface RouterModel { id: string; name: string; price?: [number, number]; maxOut?: number }
export function routerModels(json: unknown): RouterModel[] {
  const data = (json as { data?: unknown[] })?.data ?? [];
  const out: RouterModel[] = [];
  for (const m of data as Record<string, unknown>[]) {
    const params = (m.supported_parameters as string[] | undefined) ?? [];
    if (!params.includes("tools")) continue;
    const p = m.pricing as Record<string, string> | undefined;
    const pi = Number(p?.prompt), po = Number(p?.completion);
    const top = m.top_provider as Record<string, number> | undefined;
    out.push({ id: String(m.id), name: String(m.name ?? m.id),
               price: Number.isFinite(pi) && Number.isFinite(po) && pi >= 0 && po >= 0 ? [pi * 1e6, po * 1e6] : undefined,
               maxOut: top?.max_completion_tokens || undefined });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}
