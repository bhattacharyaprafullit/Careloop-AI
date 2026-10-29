"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  XCircle,
  Pencil,
  ExternalLink,
  LoaderCircle,
  Inbox,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useSandbox } from "@/hooks/use-sandbox";
import { apiFetch } from "@/lib/api";
import type { ActionType, ApprovalItem, Decision } from "@/lib/types";

export default function ApprovalsPage() {
  const { refreshKey, triggerRefresh } = useSandbox();
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [modChannel, setModChannel] = useState<Record<string, ActionType>>({});
  const [modOwner, setModOwner] = useState<Record<string, string>>({});
  const [busyCase, setBusyCase] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data, isLoading } = useQuery<{ items: ApprovalItem[] }>({
    queryKey: ["approvals", refreshKey],
    queryFn: () =>
      apiFetch<{ items: ApprovalItem[] }>("/api/v1/workflow/approvals"),
  });

  const pendingApprovals = data?.items ?? [];

  const handleDecision = async (caseId: string, decision: Decision) => {
    setBusyCase(caseId);
    setFeedback(null);
    try {
      await apiFetch("/api/v1/workflow/resume", {
        method: "POST",
        body: JSON.stringify({
          case_id: caseId,
          decision,
          note:
            notes[caseId] ||
            `Human governance ${decision} recorded for case ${caseId}.`,
          modified_action:
            decision === "modify"
              ? {
                  action_type:
                    modChannel[caseId] ?? "create_navigator_task",
                  owner_id: modOwner[caseId] ?? "coord-nav-1",
                }
              : null,
        }),
      });
      setFeedback(
        `Decision "${decision.toUpperCase()}" recorded and checkpoint resumed for case ${caseId}.`
      );
      triggerRefresh();
    } catch (err) {
      setFeedback(
        err instanceof Error ? err.message : "Could not record approval."
      );
    } finally {
      setBusyCase(null);
    }
  };

  return (
    <AppShell>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight text-slate-900">
              Human-Governed Escalation Inbox (R5)
            </h1>
            <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-bold text-purple-800">
              {pendingApprovals.length} pending
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500 max-w-2xl">
            Cases paused at the LangGraph interrupt() checkpoint requiring authorized human review:
            urgent overdue, high drop-off (&gt; 0.65), confused teach-back, or ADS divergence (&gt; 0.50).
          </p>
        </div>
      </div>

      {feedback && (
        <div
          role="status"
          data-testid="approval-feedback"
          className="mt-4 flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-3.5 text-xs font-bold text-emerald-950 animate-pop"
        >
          <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {isLoading ? (
        <div className="mt-5 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-2xl bg-slate-200/70" />
          ))}
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          {pendingApprovals.map((pa) => (
            <div
              key={pa.id}
              data-testid={`approval-card-${pa.case_id}`}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition hover:shadow-md"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-[10px] font-black uppercase text-purple-800">
                      PAUSED AT GATE • Tier {pa.urgency_tier}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-700">
                      {pa.state}
                    </span>
                  </div>
                  <h2 className="mt-2 text-base font-black text-slate-900">
                    {pa.patient_alias} <span className="font-mono text-xs text-slate-400">({pa.case_id})</span> — {pa.screening_type}
                  </h2>
                  <p className="mt-1 text-xs text-slate-600">
                    Proposed Action: <strong>{pa.action_type}</strong> • Reasons:{" "}
                    <strong className="text-amber-800">{pa.reasons.join(", ")}</strong>
                  </p>
                </div>
                <Link
                  href={`/app/cases/${pa.case_id}`}
                  className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-700 transition hover:bg-slate-100"
                >
                  <span>Inspect Case</span>
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Modified Action
                  </label>
                  <select
                    aria-label={`Modify action for ${pa.case_id}`}
                    value={modChannel[pa.case_id] ?? "create_navigator_task"}
                    onChange={(e) =>
                      setModChannel((prev) => ({
                        ...prev,
                        [pa.case_id]: e.target.value as ActionType,
                      }))
                    }
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs font-semibold text-slate-800 focus:border-blue-500 focus:outline-hidden"
                  >
                    <option value="create_navigator_task">create_navigator_task</option>
                    <option value="send_portal_message">send_portal_message</option>
                    <option value="send_sms">send_sms</option>
                    <option value="request_consult">request_consult</option>
                    <option value="reassign_owner">reassign_owner</option>
                    <option value="priority_rebook">priority_rebook</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Assignee Override
                  </label>
                  <input
                    type="text"
                    value={modOwner[pa.case_id] ?? "coord-senior-1"}
                    onChange={(e) =>
                      setModOwner((prev) => ({
                        ...prev,
                        [pa.case_id]: e.target.value,
                      }))
                    }
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs font-mono text-slate-800 focus:border-blue-500 focus:outline-hidden"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Governance Audit Note
                  </label>
                  <input
                    type="text"
                    placeholder="Audit reason for decision..."
                    value={notes[pa.case_id] ?? ""}
                    onChange={(e) =>
                      setNotes((prev) => ({
                        ...prev,
                        [pa.case_id]: e.target.value,
                      }))
                    }
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden"
                  />
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                <button
                  type="button"
                  data-testid={`approve-btn-${pa.case_id}`}
                  disabled={busyCase === pa.case_id}
                  onClick={() => void handleDecision(pa.case_id, "approve")}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-2xs hover:bg-emerald-700 active:scale-95 disabled:opacity-50"
                >
                  {busyCase === pa.case_id ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  <span>Approve Action</span>
                </button>
                <button
                  type="button"
                  data-testid={`modify-btn-${pa.case_id}`}
                  disabled={busyCase === pa.case_id}
                  onClick={() => void handleDecision(pa.case_id, "modify")}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-2xs hover:bg-blue-700 active:scale-95 disabled:opacity-50"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  <span>Modify & Resume</span>
                </button>
                <button
                  type="button"
                  data-testid={`reject-btn-${pa.case_id}`}
                  disabled={busyCase === pa.case_id}
                  onClick={() => void handleDecision(pa.case_id, "reject")}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white shadow-2xs hover:bg-rose-700 active:scale-95 disabled:opacity-50"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  <span>Reject Action</span>
                </button>
              </div>
            </div>
          ))}

          {pendingApprovals.length === 0 && (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-xs">
              <Inbox className="h-10 w-10 text-slate-300" />
              <p className="mt-3 text-sm font-semibold text-slate-600">
                No pending approvals awaiting human decision.
              </p>
              <p className="text-xs text-slate-400 mt-1">
                All cases are progressing through autonomous or completed pathways.
              </p>
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
