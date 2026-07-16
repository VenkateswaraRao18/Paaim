/**
 * Types for the 8-step incident flow, plus the PLC//symptom semantic dictionary.
 *
 * The hand-authored Line 3 scenario used to live here and was rendered whenever a
 * real incident could not be mapped — which meant one machine's scripted story
 * could appear as another's analysis. Every screen is now built from the record;
 * if that fails the UI says so rather than substituting fiction.
 */



// ── Multi-agent coordination board ─────────────────────────────────
/** A raw machine tag as it appears on the fault console. */
export type Tag = {
  tag: string;
  displayName: string;
  value: string;
  unit: string;
  normal: string;
  tone: 'ok' | 'warn' | 'bad';
  meaning: string;
  likelyCauses: string;
};

export type Agent = {
  id: string;
  name: string;
  role: string;
  finding: string;
  confidence: number | null;   // null = the agent stated none
  sources: number;
  actionImplication: string;
  tone: 'ok' | 'warn' | 'bad';
};


// ── Incident evidence timeline (normalized risk index) ─────────────
// minutes relative to the 8:17 fault (t=14 is the fault marker)

// ── Ground-truth / evidence scoreboard ─────────────────────────────
export type EvidenceRow = {
  type: string;
  source: string;
  groundTruth: string;
  captured: 'PASS' | 'REVIEW';
  actionSurfaced: string;
};


// ── Safe restart decision pack ─────────────────────────────────────

// ── Generated action drafts (Page 6) ───────────────────────────────

// ── Machine-code semantic search entries ───────────────────────────
export const semanticEntries: Record<string, {
  query: string;
  tagDict: string;
  tribalKnowledge: string;
  sopRule: string;
  humanAction: string;
}> = {
  '0x4f3': {
    query: 'Error 0x4F3',
    tagDict: 'Station C3 interlock / torque fault. Likely clamp-actuator binding or torque-tool overload.',
    tribalKnowledge: 'Prior reset-only attempt failed. Inspection of clamp and air-line resolved a similar issue (WO-3391).',
    sopRule: 'SOP-MNT-007: inspection required before restart when torque + temperature + interlock are active.',
    humanAction: 'Inspect clamp actuator and torque tool before restart; escalate to Maintenance and QA.',
  },
  'db12.dbx4.3': {
    query: 'DB12.DBX4.3',
    tagDict: 'Discrete input — Station C3 safety interlock bit. ACTIVE means the guard/clamp circuit is open.',
    tribalKnowledge: 'Recurs with clamp binding; check air-line pressure before assuming a sensor fault.',
    sopRule: 'SOP-MNT-007: an active interlock blocks restart until mechanical inspection is signed off.',
    humanAction: 'Do not bypass the interlock. Inspect the clamp mechanism and confirm guard seating.',
  },
  'mtr03_torque': {
    query: 'MTR03_TORQUE',
    tagDict: 'Analog tag — spindle-motor torque on Station C3. Normal 40–55 Nm; 68.9 Nm is high.',
    tribalKnowledge: 'Sustained high torque precedes tool-wear failures; often paired with clamp binding.',
    sopRule: 'SOP-MNT-007: elevated torque with active interlock requires inspection before restart.',
    humanAction: 'Inspect torque tool and clamp; replace tool if wear exceeds 200 min.',
  },
};

export function lookupSemantic(raw: string) {
  const key = raw.trim().toLowerCase();
  if (semanticEntries[key]) return semanticEntries[key];
  // loose match on "hi trq c3 clamp" / "restart fail" style symptom text
  if (/trq|torque|clamp|restart|0x4f3|interlock/.test(key)) return semanticEntries['0x4f3'];
  return null;
}

// ── Bundle everything into one scenario object so the flow can be data-driven ──
// (the same 8-step flow renders for any incident, seeded by a scenario like this)
export type Draft = {
  id: string; label: string; owner: string; sop: string; urgency: string; body: string;
};

export type RescueScenario = {
  incident: {
    line: string; station: string; errorCode: string; errorMeaning: string; runId: string;
    timestamp: string; decisionDeadline: string;
    // null = this factory has no cost model / the agents estimated no downtime.
    // Typed nullable on purpose: a plain `number` is what let a UI default of
    // $1,300/min stand in for a figure nobody had supplied.
    downtimeMinutes: number | null; costPerMinute: number | null;
    costModelConfigured?: boolean;
    unitsAtRisk: number; order: { id: string; customer: string; dueTime: string };
    headline: string; question: string;
  };
  estimatedLoss: number | null;
  tags: Tag[];
  agents: Agent[];
  timeline: {
    minutes: number[]; torque: number[]; tempDelta: number[]; cameraAnomaly: number[]; faultAt: number;
    faultLabel: string; snippets: { source: string; text: string }[]; readout: string;
    hasSeries: boolean;
    /** Generic series; when present it replaces the scripted torque/temp/camera trio. */
    series?: { name: string; color: string; data: number[] }[];
    /** Caption under the x-axis (defaults to the Line 3 "minutes" wording). */
    xUnitLabel?: string;
    /** Per-point x tick labels; thinned automatically when crowded. */
    xTickLabels?: string[];
  };
  evidenceRows: EvidenceRow[];
  decision: {
    title: string; verdict: string; reason: string; requiredBeforeRestart: string[]; fallback: string;
    avoidableLoss: { min: number; max: number } | null; approvals: string[];
    rootCause: { cause: string; pct: number | null }[]; actions: { id: string; title: string; owner: string; urgency: string }[];
    /** What the bars actually mean. Defaults to the scripted scenario's wording;
     *  real incidents override it, because we can report an agent's stated
     *  confidence but cannot honestly attribute a cause a percentage. */
    rootCauseTitle?: string;
    rootCauseNote?: string;
  };
  drafts: Draft[];
  lookupSemantic: typeof lookupSemantic;
  context: { machine: string; order?: string };
  priority?: { level: 'L1' | 'L2' | 'L3'; score: number; rationale: string; drivers: string[] };
  /** The real incident this flow is showing. */
  decisionId?: string;
};

