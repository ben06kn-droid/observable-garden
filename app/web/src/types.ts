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
  | ({ type: "audit"; id: number } & AuditInputs);

export type FromWorker =
  | { type: "loaded"; ms: number; standins: Record<string, boolean>; wheel: string }
  | { type: "search"; id: number; tree: SearchTree }
  | ({ type: "progress"; id: number } & Progress)
  | { type: "result"; id: number; result: AuditResult; replicatePaths: ReplicatePath[] | null; ms: number }
  | { type: "refused"; id: number; message: string }
  | { type: "error"; id?: number; message: string };
