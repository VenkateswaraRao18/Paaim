// Recovery Decision Twin — API client + types (Page 5B / Facility Gate / Factory Memory)

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export type Control = {
  factor_id: string; label: string; type: 'slider' | 'select' | 'toggle';
  default: number | string | boolean; min?: number; max?: number; step?: number;
  options?: (number | string | boolean)[]; unit: string; source: string; business_reason: string;
};
export type Preset = { preset_id: string; label: string; description: string; factor_overrides: Record<string, any> };
export type OptionDef = { option_id: string; label: string; owner: string };
export type TwinConfig = {
  controls: { factors: Control[]; fallback_threshold_min: number; current_downtime_min: number; order: { id: string; customer: string } };
  presets: Preset[]; options: OptionDef[];
};

export type SimOption = {
  option_id: string; label: string; allowed: boolean; blocked_by: string[];
  // null when the factory has no cost model — the twin then ranks on ship
  // probability, QA escape and downtime instead of inventing an hourly rate.
  ship_probability: number; expected_loss: number | null; qa_escape_risk: number;
  downtime_hours?: number; ship_reason?: string;
  safety_status: 'blocked' | 'review' | 'pass'; owner: string; is_recommended: boolean;
};
export type SimResult = {
  scenario_id: string; changed_factors: { factor: string; old: any; new: any }[];
  recommended_option: string; recommended_label: string; next_best_action: string;
  options: SimOption[];
  explanation: { summary: string; triggered_constraints: string[]; business_impact: string; non_bypassable_gates: string[] };
  assumptions: { assumption_id: string; value: any; unit: string; source_file: string; editable: boolean; confidence: string }[];
};

export type GateRow = { gate_id: string; label: string; status: 'hold' | 'review' | 'pass'; reason: string; owner: string; source?: string; allowed_actions: string[] };
export type GateBoard = { overall_status: string; restart_blocked: boolean; gates: GateRow[]; blocked_actions: string[]; allowed_draft_actions: string[]; trust_banner: string };

export type Memory = {
  eight_d: { id: string; discipline: string; content: string; status: string }[];
  similar_incidents: any[]; similar_incidents_found: number; recurrence_pattern: string;
  learned_rule: { rule_text: string; status: string; applies_to: string[] };
  recurrence_risk: { before_action: number; after_corrective_action: number; after_verified_rule: number };
  verification_plan: any[];
};

// Every model below is computed for one real incident — the backend has no
// scripted fallback, so decisionId is required rather than optional.
export const getTwinConfig = (decisionId: string) =>
  fetch(`${API}/twin/config?decision_id=${encodeURIComponent(decisionId)}`).then(r => r.json()) as Promise<TwinConfig>;
export const getGate = (decisionId: string) =>
  fetch(`${API}/twin/gate?decision_id=${encodeURIComponent(decisionId)}`).then(r => r.json()) as Promise<GateBoard>;
export const getMemory = (decisionId: string) =>
  fetch(`${API}/twin/memory?decision_id=${encodeURIComponent(decisionId)}`).then(r => r.json()) as Promise<Memory>;
export const simulate = (factors: Record<string, any>, decisionId: string) =>
  fetch(`${API}/twin/simulate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ factors, decision_id: decisionId }) }).then(r => r.json()) as Promise<SimResult>;
export const postAudit = (event: Record<string, any>) =>
  fetch(`${API}/twin/audit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event) }).then(r => r.json());
