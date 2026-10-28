// The shapes the gate's worker sends back. AuditResult is quixote.audit.AuditResult.to_dict().

export interface AuditResult {
  status: "CERTIFIED" | "FAIL" | "INADMISSIBLE" | "UNDECIDABLE" | "DEGENERATE" | "DEPENDS_ON_JUDGMENT" | string;
  exit_code: number;
  submitted_support: [number, number][];
  submitted_feature_names: string[];
  submitted_sharpe: number;
  p_replay: number | null;
  p_class: number;
  class_bar: number;
  alpha: number;
  B: number;
  n_moves: number;
  class_size: number;
  reasons: string[];
}

export interface Candidate { rule: string; sharpe: number }
export interface TreeMove {
  kind: string; stem: number; from_ground: boolean; call: number; text: string;
  candidates: Candidate[]; chosen: number; kept: boolean;
}
export interface SearchTree {
  feature_names: string[]; moves: TreeMove[]; evaluations: number; stems: number; panel_shape: [number, number, number];
}
export interface ReplicateStep { action: string; support: [number, number][]; sharpe: number; rule?: string }
export interface ReplicatePath { score: number; filled: boolean; steps: ReplicateStep[] }

export type Stage = "class" | "replay";
export interface Progress { stage: Stage; done: number; total: number }

export interface AuditInputs {
  log: string;              // the log file's text
  panel: ArrayBuffer;       // the panel .npz, as bytes
  cls: string;              // the class file's text
  B: number;
  seed: number;
  replicatePaths?: number;  // how many of the null's replicates to return for drawing (0: none)
}

export type ToWorker =
  | { type: "load" }
  | ({ type: "audit"; id: number } & AuditInputs)
  | { type: "inspect"; id: number; panel: ArrayBuffer; cls: string }
  | { type: "prompt"; id: number }
  | { type: "run"; id: number; panel: ArrayBuffer; cls: string; key: string; url: string; opts: RunOptions; B: number; seed: number };

/** What the full run sends the model and the harness: the visitor's choices. */
export interface RunOptions { model: string; effort?: string; max_moves: number; system?: string; fallbacks: boolean; seed: number; max_tokens?: number }

export interface InputsInfo { kind?: string; size?: number; rows?: number; assets?: number; features?: number; class_name?: string; describe?: string;
  panel_sha256?: string; class_sha256?: string; table_bytes?: number; error?: string }

export interface RunUsage { input_tokens: number; output_tokens: number; cache_read_input_tokens: number; requests: number }

/** One step of a run as it happens: the model's move, the harness's answer, the tokens, the search so far. */
export type RunEvent =
  | { type: "move"; tool: string | null; args: Record<string, unknown>; text: string; stop_reason?: string }
  | { type: "result"; last: { ok?: boolean; text?: string; refused?: string } }
  | { type: "usage"; usage: RunUsage; model?: string }
  | { type: "tree"; tree: SearchTree };

export type FromWorker =
  | { type: "loaded"; ms: number; standins: Record<string, boolean>; wheel: string }
  | { type: "search"; id: number; tree: SearchTree }
  | ({ type: "progress"; id: number } & Progress)
  | { type: "result"; id: number; result: AuditResult; replicatePaths: ReplicatePath[] | null; ms: number }
  | { type: "refused"; id: number; message: string }
  | { type: "error"; id?: number; message: string }
  | { type: "inspected"; id: number; info: InputsInfo }
  | { type: "prompt"; id: number; system: string; schemas: Record<string, unknown> }
  | { type: "run-event"; id: number; event: RunEvent }
  | { type: "run-done"; id: number; log: unknown; usage: RunUsage; result: AuditResult | null; refused?: string; tree: SearchTree | null; ms: number }
  | { type: "run-stopped"; id: number; message: string; usage: RunUsage | null };
