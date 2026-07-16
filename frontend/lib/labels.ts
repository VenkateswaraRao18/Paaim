/**
 * Plain-language vocabulary for the shop floor.
 *
 * Factory staff know manufacturing terms (work order, NCR, scrap, OEE) but not
 * AI/software jargon (agent, orchestration, confidence, latency, red-team).
 * This module is the single place that translates the engine's internal terms
 * into words an operator or supervisor understands. Tune wording here once.
 */

// ── Sensor signals → plain English ──────────────────────────────────────────
const SIGNAL_PLAIN: Record<string, string> = {
  tool_wear_degradation: 'Tool wearing out',
  heat_dissipation_loss: 'Machine overheating',
  power_envelope_breach: 'Power spike / drop',
  mechanical_overstrain: 'Machine overstrain',
  unexplained_quality_fault: 'Quality problem',
  general_machine_failure: 'Machine failure',
  zone_intrusion: 'Person in danger zone',
  defect_detection: 'Defect found',
  temperature_trend: 'Temperature rising',
  vibration_anomaly: 'Unusual vibration',
  bearing_temperature: 'Bearing getting hot',
  coolant_pressure: 'Coolant pressure issue',
};

// ── Recommended actions → plain English ─────────────────────────────────────
const ACTION_PLAIN: Record<string, string> = {
  escalate_critical: 'Escalate to manager',
  schedule_maintenance: 'Schedule maintenance',
  stop_line: 'Stop the line',
  acknowledge_estop: 'Acknowledge emergency stop',
  contain_batch: 'Hold this batch',
  release_batch: 'Release batch',
  inspect_root_cause: 'Investigate the cause',
  reduce_consumption: 'Reduce power use',
  shift_non_critical_load: 'Shift non-urgent work',
  adjust_schedule: 'Adjust the schedule',
  propose_recovery_plan: 'Plan recovery',
};

// ── Event categories → plain English ────────────────────────────────────────
const EVENT_TYPE_PLAIN: Record<string, string> = {
  safety: 'Safety',
  quality: 'Quality',
  maintenance: 'Maintenance',
  production: 'Production',
  energy: 'Energy use',
  compliance: 'Compliance',
};

// ── Technical UI terms → plain labels ───────────────────────────────────────
export const TERMS = {
  agents: 'Monitors',
  agentsSub: 'Set up machine watchdogs',
  confidence: 'Certainty',
  confidenceShort: 'sure',
  latency: 'Response time',
  pipeline: 'How this decision was made',
  redTeam: 'Safety double-check',
  evidence: 'Why we recommend this',
  agentAnalysis: 'What each monitor found',
  impact: 'Predicted impact',
  decisionTwin: 'Impact forecast',
  approvalRoute: 'Who needs to approve',
} as const;

// ── One-line glossary for "?" tooltips ──────────────────────────────────────
export const GLOSSARY: Record<string, string> = {
  Certainty: 'How sure the system is about this finding, from 0 to 100%.',
  'Safety double-check': 'A second automated review that questions the recommendation and looks for risks before it reaches you.',
  Monitor: 'An automated watcher for one kind of problem (e.g. overheating, defects). Like a tireless inspector.',
  'Predicted impact': 'The estimated cost, downtime and quality effect if this happens or if you act.',
  Risk: 'How serious this is: Critical needs immediate action, Low can wait.',
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Plain phrase for a sensor signal, falling back to a tidied version. */
export function plainSignal(signal?: string | null): string {
  if (!signal) return 'Unknown signal';
  return SIGNAL_PLAIN[signal] ?? titleCase(signal);
}

/** Plain phrase for a recommended action. */
export function plainAction(action?: string | null): string {
  if (!action || action === 'unknown') return 'No action yet';
  return ACTION_PLAIN[action] ?? titleCase(action);
}

/** Plain label for an event category. */
export function plainEventType(t?: string | null): string {
  if (!t) return 'Event';
  return EVENT_TYPE_PLAIN[t] ?? titleCase(t);
}

/** Friendly machine name from an id like "robot_arm_01". */
export function plainMachine(id?: string | null): string {
  if (!id) return 'Floor sensor';
  return id
    .replace(/_/g, ' ')
    .replace(/\b(\d+)\b/g, ' $1')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}
