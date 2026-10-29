"use client";

import React, { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { Decision, CaseDetailsResponse } from "@/lib/types";

export type PendingApprovalInfo = NonNullable<CaseDetailsResponse["pending_approval"]>;

export function CaseApprovalBanner({
  caseId,
  pendingApproval,
  onUpdated,
}: {
  caseId: string;
  pendingApproval: PendingApprovalInfo;
  onUpdated: () => void;
}) {
  const [approvalNote, setApprovalNote] = useState("Reviewed by coordinator; approved.");
  const [actionError, setActionError] = useState<string | null>(null);

  const handleDecision = async (decision: Decision) => {
    setActionError(null);
    try {
      await apiFetch("/api/v1/workflow/resume", {
        method: "POST",
        body: JSON.stringify({ case_id: caseId, decision, note: approvalNote }),
      });
      onUpdated();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Approval failed");
    }
  };

  return (
    <section className="mt-4 rounded-2xl border-2 border-purple-400 bg-purple-50/70 p-4 shadow-xs animate-pop">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-purple-700" />
            <h2 className="text-xs font-bold text-purple-950 uppercase tracking-wide">Human Gate (R5)</h2>
          </div>
          <p className="mt-1 text-xs text-purple-900 font-medium">
            Paused at LangGraph interrupt() — Action:{" "}
            <strong>{pendingApproval.action_type}</strong> ({pendingApproval.reasons.join(", ")})
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            aria-label="Approval note"
            value={approvalNote}
            onChange={(e) => setApprovalNote(e.target.value)}
            className="rounded-lg border border-purple-300 bg-white px-2.5 py-1 text-xs text-purple-950"
          />
          <button
            type="button"
            data-testid="inline-approve-btn"
            onClick={() => void handleDecision("approve")}
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-emerald-700"
          >
            Approve
          </button>
          <button
            type="button"
            data-testid="inline-reject-btn"
            onClick={() => void handleDecision("reject")}
            className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-rose-700"
          >
            Reject
          </button>
        </div>
      </div>
      {actionError && (
        <p className="mt-2 text-xs font-semibold text-rose-700">{actionError}</p>
      )}
    </section>
  );
}
