"use client";

import React, { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { CaseCollaborationAndClosurePanels } from "@/components/case-action-panels";
import { CaseApprovalBanner } from "@/components/case-approval-banner";
import { ShapWaterfallChart, SurvivalComparisonChart } from "@/components/charts";
import { LifecycleStepper } from "@/components/lifecycle-stepper";
import { useSandbox } from "@/hooks/use-sandbox";
import { apiFetch, openCaseStream } from "@/lib/api";
import { STATE_META, TONE_BADGE, TONE_DOT, pct } from "@/lib/utils";
import {
  ALL_CASE_STATES,
  type CaseDetailsResponse,
  type CaseState,
} from "@/lib/types";

export default function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { refreshKey, triggerRefresh } = useSandbox();
  const [ownerRoleInput, setOwnerRoleInput] = useState<"coordinator" | "clinician">("coordinator");
  const [ownerInput, setOwnerInput] = useState("coord-assigned-1");
  const [targetState, setTargetState] = useState<CaseState>("PATIENT_NOTIFIED");
  const [evidenceInput, setEvidenceInput] = useState("message_sent");
  const [streamedSummary, setStreamedSummary] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: details, isLoading, error } = useQuery<CaseDetailsResponse>({
    queryKey: ["case-details", id, refreshKey],
    queryFn: () => apiFetch<CaseDetailsResponse>(`/api/v1/cases/${id}/details`),
  });

  const handleAssign = async () => {
    setActionError(null);
    try {
      await apiFetch(`/api/v1/cases/${id}/assign`, {
        method: "POST",
        body: JSON.stringify({ owner_role: ownerRoleInput, owner_id: ownerInput }),
      });
      triggerRefresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Assign failed");
    }
  };

  const handleAdvance = async () => {
    setActionError(null);
    try {
      await apiFetch(`/api/v1/cases/${id}/advance`, {
        method: "POST",
        body: JSON.stringify({
          to_state: targetState,
          evidence: {
            type: evidenceInput || "message_sent",
            ref: `ref-${targetState.toLowerCase()}`,
            reason_code: targetState === "REJECTED" ? "referral_rejected_capacity" : null,
          },
        }),
      });
      triggerRefresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Advance failed");
    }
  };

  const handleStreamSummary = () => {
    setStreaming(true);
    setStreamedSummary("");
    const chunks: string[] = [];
    openCaseStream(
      id,
      (evtName, payload) => {
        if (evtName === "token" && typeof payload.text === "string") {
          chunks.push(payload.text);
          setStreamedSummary(chunks.join(" "));
        }
        if (evtName === "done") setStreaming(false);
      },
      () => setStreaming(false)
    );
  };

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-4">
          <div className="h-28 animate-pulse rounded-2xl bg-slate-200/70" />
          <div className="h-64 animate-pulse rounded-2xl bg-slate-200/70" />
        </div>
      </AppShell>
    );
  }

  if (error || !details) {
    return (
      <AppShell>
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-xs font-semibold text-rose-800">
          Case could not be loaded: {error instanceof Error ? error.message : "Not found"}
        </div>
      </AppShell>
    );
  }

  const { case: c, patient: pat, risk } = details;
  const stateMeta = STATE_META[c.state] ?? { label: c.state, tone: "slate" as const };

  return (
    <AppShell>
      {/* Top Header Card */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-blue-600 px-3 py-0.5 text-xs font-bold text-white shadow-2xs">
              {c.screening_type} • Tier {c.urgency_tier}
            </span>
            <span
              data-testid="case-current-state"
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-0.5 text-xs font-bold ${TONE_BADGE[stateMeta.tone]}`}
            >
              <span className={`h-2 w-2 rounded-full ${TONE_DOT[stateMeta.tone]}`} />
              {c.state}
            </span>
            {c.escalated && (
              <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-bold text-purple-900">
                ESCALATED
              </span>
            )}
          </div>
          <h1 className="mt-2 text-2xl font-black text-slate-900 tracking-tight">{pat.alias}</h1>
          <p className="font-mono text-xs text-slate-600">
            Case ID: {c.id} • Severity: Grade {c.severity_grade} • Owner:{" "}
            <strong>{c.owner_role ?? "none"}</strong> ({c.owner_id ?? "Unassigned"})
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 px-3.5 py-2 text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-600">Drop-Off Risk</div>
            <div className="text-base font-black text-slate-900">{pct(risk.p_dropoff)}</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 px-3.5 py-2 text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-600">Median Closure</div>
            <div className="text-base font-black text-slate-900">{risk.median_days.toFixed(1)}d</div>
          </div>
          <div className="rounded-xl border border-blue-200 bg-blue-50/70 px-3.5 py-2 text-center">
            <div className="text-[10px] font-bold uppercase tracking-wider text-blue-700">Priority Score</div>
            <div className="text-base font-black text-blue-900">{c.priority.toFixed(1)}</div>
          </div>
        </div>
      </div>

      {/* 11-State Lifecycle Stepper (R1) */}
      <LifecycleStepper currentState={c.state} timeline={details.timeline} />

      {/* Pending Human Approval Banner */}
      {details.pending_approval && (
        <CaseApprovalBanner
          caseId={id}
          pendingApproval={details.pending_approval}
          onUpdated={triggerRefresh}
        />
      )}

      {/* Owner Assignment & Stage Transition Controls (R2) */}
      <section className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Owner role"
            value={ownerRoleInput}
            onChange={(e) => setOwnerRoleInput(e.target.value as "coordinator" | "clinician")}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-800"
          >
            <option value="coordinator">coordinator</option>
            <option value="clinician">clinician</option>
          </select>
          <input
            type="text"
            aria-label="Owner ID"
            value={ownerInput}
            onChange={(e) => setOwnerInput(e.target.value)}
            className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-mono text-slate-800"
          />
          <button
            type="button"
            data-testid="assign-owner-btn"
            onClick={() => void handleAssign()}
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-slate-800"
          >
            Assign Owner
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Target transition state"
            data-testid="advance-state-select"
            value={targetState}
            onChange={(e) => setTargetState(e.target.value as CaseState)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-800"
          >
            {ALL_CASE_STATES.map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>
          <input
            type="text"
            aria-label="Entry evidence type"
            data-testid="advance-evidence-input"
            value={evidenceInput}
            onChange={(e) => setEvidenceInput(e.target.value)}
            placeholder="Entry evidence type"
            className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-800"
          />
          <button
            type="button"
            data-testid="advance-state-btn"
            onClick={() => void handleAdvance()}
            className="rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-blue-700"
          >
            Advance Stage
          </button>
        </div>
      </section>

      {actionError && (
        <div role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs font-semibold text-rose-800">
          {actionError}
        </div>
      )}

      {/* Charts: SHAP Waterfall + Survival Comparison */}
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <ShapWaterfallChart topPositive={details.shap.top_positive} topNegative={details.shap.top_negative} />
        <SurvivalComparisonChart survivalCurve={details.survival_curve} kmCurve={details.km_curve} />
      </div>

      {/* Grounded Case Summary + ADS Badge */}
      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-slate-900">Grounded Clinical Summary</h2>
            <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700 border border-blue-200/60">
              ADS: {details.summary.ads.toFixed(2)}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
              {details.summary.source === "template" ? "Deterministic Template" : "Validated LLM"}
            </span>
          </div>
          <button
            type="button"
            data-testid="stream-summary-btn"
            disabled={streaming}
            onClick={handleStreamSummary}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-slate-800 disabled:opacity-50"
          >
            <Sparkles className="h-3 w-3" />
            <span>{streaming ? "Streaming..." : "Stream Grounded Summary"}</span>
          </button>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-700">{streamedSummary ?? details.summary.lines.join(" ")}</p>
        <p className="mt-2 text-xs font-bold text-blue-700">Next Step: {details.summary.next_step}</p>
      </section>

      <CaseCollaborationAndClosurePanels details={details} onUpdated={triggerRefresh} />

      {/* Append-Only Audit Timeline */}
      <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-3">
          Append-Only Event Ledger ({details.timeline.length} events)
        </h2>
        <div className="mt-3 space-y-2">
          {details.timeline.map((ev, idx) => (
            <div
              key={idx}
              data-testid={`event-item-${ev.event_type}`}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-2 text-xs"
            >
              <div>
                <span className="font-bold text-slate-900">{ev.event_type}</span> •{" "}
                <span className="text-slate-600 font-medium">
                  {ev.from_state ? `${ev.from_state} → ` : ""}
                  {ev.to_state ?? ""}
                </span>{" "}
                <span className="text-slate-400">({ev.actor_role})</span> — {ev.summary}
              </div>
              <div className="font-mono text-[10px] text-slate-600">{ev.at}</div>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
