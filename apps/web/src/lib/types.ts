/** Strict TypeScript domain & API contracts mirroring the FastAPI backend (M10). */

export type Role = "coordinator" | "clinician" | "patient";
export type ScreeningType = "FIT" | "MAMMOGRAPHY" | "PAP_HPV";
export type UrgencyTier = 1 | 2 | 3;
export type Language = "en" | "hi" | "es";
export type Decision = "approve" | "modify" | "reject";
export type ActionType =
  | "send_portal_message"
  | "send_sms"
  | "create_navigator_task"
  | "request_consult"
  | "reassign_owner"
  | "priority_rebook";

export const ALL_CASE_STATES = [
  "RESULT_ISSUED",
  "PATIENT_NOTIFIED",
  "ACKNOWLEDGED",
  "CONFIRMATORY_PENDING",
  "REFERRAL_SENT",
  "REJECTED",
  "REFERRAL_ACCEPTED",
  "APPOINTMENT_BOOKED",
  "SEEN",
  "TREATMENT_OR_SURVEILLANCE",
  "CLOSED",
] as const;

export type CaseState = (typeof ALL_CASE_STATES)[number];

export const ALLOWED_CLOSURE_EVIDENCE = [
  "treatment_started",
  "surveillance_plan",
  "benign_confirmed",
  "patient_declined_counseled",
] as const;

export type ClosureEvidenceType = (typeof ALLOWED_CLOSURE_EVIDENCE)[number];

export const REASON_CODES = [
  "patient_unreachable",
  "transport_barrier",
  "cost_concern",
  "language_barrier",
  "scheduling_conflict",
  "referral_rejected_capacity",
  "referral_incomplete",
  "no_appointment_available",
  "patient_declined",
  "clinician_delay",
  "lost_result",
  "unknown",
] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

export interface TeachBackResponse {
  label: "understood" | "partial" | "confused";
  followup_text: string;
  escalated: boolean;
}

export interface SandboxResponse {
  token: string;
  expires_at: string;
  case_count: number;
}

export interface PriorityQueueItem {
  case_id: string;
  patient_alias: string;
  screening_type: string;
  state: CaseState;
  owner_role: string | null;
  owner_id: string | null;
  urgency_tier: number;
  p_dropoff: number;
  priority: number;
  sla_due_at: string | null;
  hours_remaining: number | null;
  overdue: boolean;
  escalated: boolean;
  needs_approval: boolean;
}

export interface PriorityQueueResponse {
  items: PriorityQueueItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface TimelineEntry {
  at: string;
  event_type: string;
  from_state: string | null;
  to_state: string | null;
  actor_role: string;
  summary: string;
}

export interface ShapDriverItem {
  feature: string;
  label: string;
  value: number;
}

export interface CurvePoint {
  day: number;
  s: number;
}

export interface SbarNote {
  situation: string;
  background: string;
  assessment: string;
  recommendation: string;
}

export interface CaseDetailsResponse {
  case: {
    id: string; patient_id: string; screening_type: string; severity_grade: number;
    urgency_tier: number; state: CaseState; state_entered_at: string;
    owner_role: string | null; owner_id: string | null; escalated: boolean; overdue: boolean;
    sla_due_at: string | null; hours_remaining: number | null; priority: number;
    finding_to_order_days: number; scheduling_lead_time: number; contact_attempts: number;
    acknowledged: boolean; patient_token: string; created_at: string; closed_at: string | null;
    evidence: Array<{ id: string; type: string; ref: string; created_by: string; at: string }>;
  };
  patient: {
    id: string; alias: string; age: number; language: string; insurance: string;
    distance_miles: number; portal_active: boolean; prior_noshow_count: number;
    prior_noshow_ratio: number; days_since_last_encounter: number;
  };
  timeline: TimelineEntry[];
  risk: {
    stage: string; p_dropoff: number; median_days: number;
    p_open_30: number; p_open_60: number; p_open_90: number; model_version: string;
  };
  shap: { top_positive: ShapDriverItem[]; top_negative: ShapDriverItem[] };
  survival_curve: CurvePoint[];
  km_curve: CurvePoint[];
  summary: {
    lines: string[]; next_step: string; cited_drivers: string[]; ads: number; source: string;
  };
  messages: Array<{
    id: string; channel: string; language: string; body: string;
    direction: string; status: string; teachback_label: string | null; at: string;
  }>;
  referral: {
    id: string; from_org: string; to_org: string; status: string;
    reason_code: string | null; sbar: SbarNote; created_at: string; decided_at: string | null;
  } | null;
  consults: Array<{
    id: string; kind: string; status: string; created_at: string;
    thread: Array<{ sender_role: string; body: string; at: string }>;
  }>;
  pending_approval: {
    id: string; action_type: string; payload: Record<string, unknown>;
    reasons: string[]; status: string; at: string;
  } | null;
  closure: {
    id: string; kind: string; evidence_type: string | null;
    override_by: string | null; override_reason: string | null; at: string;
  } | null;
}

export interface ApprovalItem {
  id: string; case_id: string; patient_alias: string; screening_type: string;
  state: string; urgency_tier: number; action_type: string;
  payload: Record<string, unknown>; reasons: string[]; status: string; at: string;
}

export interface ReferralItem {
  id: string; case_id: string; patient_alias: string; screening_type: string;
  urgency_tier: number; from_org: string; to_org: string; status: string;
  reason_code: string | null; sbar: SbarNote; created_at: string; decided_at: string | null;
}

export interface ConsultItem {
  id: string; case_id: string; patient_alias: string; screening_type: string;
  kind: string; status: string; created_at: string;
  thread: Array<{ sender_role: string; body: string; at: string }>;
}

export interface MetricsSummary {
  state_counts: Record<string, number>;
  intervals: Record<string, { median_hours: number | null; p90_hours: number | null; n: number }>;
  referral_completion_rate: number;
  appointment_completion_rate: number;
  unresolved: {
    total: number;
    aging: { d0_30: number; d31_60: number; d61_90: number; d90_plus: number };
  };
  delay_reasons: Array<{ code: string; count: number }>;
  documented_closure_rate: number;
  acknowledgement_rate: number;
  teachback: { understood: number; partial: number; confused: number };
  simulation: {
    label?: string;
    runs: number;
    fifo: { median_days: number; unresolved_day60: number };
    careloop: { median_days: number; unresolved_day60: number };
    ci95: {
      fifo_median_days: [number, number];
      careloop_median_days: [number, number];
      fifo_unresolved_day60: [number, number];
      careloop_unresolved_day60: [number, number];
    };
  };
}

export interface PatientPortalView {
  case_id: string; status_text: string; next_step_text: string; due_date: string;
  language: string; language_fallback: boolean; acknowledged: boolean;
  steps: Array<{ label: string; done: boolean }>;
}

export interface ModelCardMetrics {
  model_version: string;
  synthetic_disclaimer: string;
  artifacts_total_mb: number;
  splits: {
    train_rows: number; calibration_rows: number; test_rows: number;
    train_patients: number; calibration_patients: number; test_patients: number;
  };
  classification: {
    roc_auc: number; roc_auc_diagnostic_target?: [number, number]; diagnostic_note?: string;
    pr_auc: number; brier_uncalibrated: number; brier_calibrated: number;
    ece_uncalibrated: number; ece_calibrated: number; best_iteration: number;
    reliability_curve: Array<{ bin: number; count: number; mean_pred: number; frac_pos: number }>;
  };
  survival: {
    model_type: string; ph_violated: boolean; violated_covariates?: string[];
    concordance_index: number; km_curve: CurvePoint[];
  };
  shap: {
    units: string;
    global_top_features: Array<{
      feature: string; label: string; mean_abs_log_odds: number; units: string;
    }>;
    stability?: { bootstrap_runs: number; mean_spearman_rho: number; top3_overlap_rate: number };
  };
  fairness: {
    threshold: number; largest_fpr_gap: number; largest_fnr_gap: number;
    largest_gap_dimension: string;
    dimensions: Record<
      string,
      {
        fpr_gap: number; fnr_gap: number;
        slices: Record<string, { n: number; positive_rate: number; fpr: number; fnr: number }>;
      }
    >;
  };
  llm_faithfulness?: {
    evaluated_cases: number; validator_pass_rate: number; fallback_rate: number; mean_ads: number;
  };
}
