export interface TourStepSpec {
  step: number;
  title: string;
  body: string;
  route: string;
}

export const GUIDED_TOUR_STEPS: TourStepSpec[] = [
  { step: 1, title: "1. Priority Queue & SLA Visibility (R1, R2)", body: "Abnormal screening results ranked by urgency tier, calibrated drop-off probability, and SLA pressure. Filter by Overdue, Unassigned, Rejected, or Needs Approval.", route: "/app/queue" },
  { step: 2, title: "2. Explainable Risk & Survival Curves (M3)", body: "Open any case to inspect the 11-state lifecycle stepper, SHAP log-odds waterfall drivers, and patient survival curve vs. cohort Kaplan-Meier.", route: "/app/queue" },
  { step: 3, title: "3. Grounded AI Summary & ADS Check (M6)", body: "LLM outputs strictly validated against case FACTS (no invented numbers or banned phrases) and audited with the Explanation-Summary Divergence Score (ADS).", route: "/app/queue" },
  { step: 4, title: "4. Safe Human-in-the-Loop Escalation (R5)", body: "High-risk, overdue urgent, rejected, or confused teach-back cases pause at the LangGraph interrupt() gate until a human approves, modifies, or rejects.", route: "/app/approvals" },
  { step: 5, title: "5. Multilingual Patient Teach-Back (R3)", body: "Patients view a 3-step tracker in English, Hindi, or Spanish, click 'I understand' to acknowledge, and complete teach-back confirmation.", route: "/p/pt-seed-001" },
  { step: 6, title: "6. Cross-Provider SBAR & Consults (R4)", body: "Clinicians review SBAR referral hand-offs, accept or reject with structured ReasonCodes, and collaborate across consult threads.", route: "/app/clinician" },
  { step: 7, title: "7. Time Simulation & Documented Closure Gate (R5)", body: "Use 'Advance time (+48h)' to trigger SLA breaches, and verify that closing a case is blocked without documented evidence or clinician override.", route: "/app/queue" },
  { step: 8, title: "8. Loop Closure & Queue Impact Metrics (R6)", body: "Review transition intervals, unresolved aging, delay reasons, documented closure rate, and the 100-run FIFO vs. CareLoop priority simulation.", route: "/app/metrics" },
];
