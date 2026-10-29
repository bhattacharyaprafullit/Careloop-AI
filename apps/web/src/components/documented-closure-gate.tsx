"use client";

import React, { useState } from "react";
import { Lock } from "lucide-react";
import { apiFetch } from "@/lib/api";
import {
  ALLOWED_CLOSURE_EVIDENCE,
  type CaseDetailsResponse,
  type ClosureEvidenceType,
} from "@/lib/types";

export function DocumentedClosureGate({
  details,
  onUpdated,
}: {
  details: CaseDetailsResponse;
  onUpdated: () => void;
}) {
  const { case: c } = details;
  const [selectedEvidence, setSelectedEvidence] = useState<ClosureEvidenceType | "">("");
  const [useOverride, setUseOverride] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [closeError, setCloseError] = useState<string | null>(null);
  const [closeSuccess, setCloseSuccess] = useState<string | null>(null);
  const [closeBusy, setCloseBusy] = useState(false);

  const handleCloseCase = async () => {
    setCloseBusy(true);
    setCloseError(null);
    setCloseSuccess(null);
    try {
      const payload = {
        evidence_type: selectedEvidence || null,
        override: useOverride ? { reason: overrideReason } : null,
      };
      const res = await apiFetch<{ kind?: string; closure_kind?: string; state: string }>(
        `/api/v1/cases/${c.id}/close`,
        {
          method: "POST",
          roleOverride: useOverride ? "clinician" : undefined,
          body: JSON.stringify(payload),
        }
      );
      setCloseSuccess(`Case closed (${res.state}) via ${res.kind ?? res.closure_kind ?? "evidence"}.`);
      onUpdated();
    } catch (err) {
      setCloseError(err instanceof Error ? err.message : "Closure blocked by safety gate.");
    } finally {
      setCloseBusy(false);
    }
  };

  return (
    <section className="flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs">
      <div>
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Documented Closure Gate (R5)</h3>
          </div>
          <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">Safety Guard</span>
        </div>

        <p className="mt-2 text-xs text-slate-500">
          Closure strictly requires documented clinical evidence or authorized override.
        </p>

        <fieldset className="mt-2.5 space-y-1">
          <legend className="text-[11px] font-bold uppercase tracking-wider text-slate-600">Allowed Evidence:</legend>
          {ALLOWED_CLOSURE_EVIDENCE.map((ev) => (
            <label key={ev} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer hover:text-slate-900">
              <input
                type="checkbox"
                data-testid={`evidence-checkbox-${ev}`}
                checked={selectedEvidence === ev}
                onChange={() => setSelectedEvidence((prev) => (prev === ev ? "" : ev))}
                className="rounded text-emerald-600 focus:ring-emerald-500"
              />
              <span>{ev}</span>
            </label>
          ))}
        </fieldset>

        <label className="mt-2.5 flex items-center gap-2 text-xs font-semibold text-slate-800 cursor-pointer">
          <input
            type="checkbox"
            data-testid="override-checkbox"
            checked={useOverride}
            onChange={(e) => setUseOverride(e.target.checked)}
            className="rounded text-amber-600 focus:ring-amber-500"
          />
          <span>Authorized Clinician Override</span>
        </label>

        {useOverride && (
          <input
            type="text"
            data-testid="override-reason-input"
            placeholder="Documented clinician override reason..."
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            className="mt-2 w-full rounded-lg border border-amber-300 bg-amber-50/50 px-2.5 py-1.5 text-xs text-amber-950 focus:border-amber-500 focus:outline-hidden"
          />
        )}

        <button
          type="button"
          data-testid="close-case-btn"
          disabled={closeBusy}
          onClick={() => void handleCloseCase()}
          className="mt-3.5 w-full rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white shadow-xs transition hover:bg-emerald-700 active:scale-98 disabled:opacity-50"
        >
          {closeBusy ? "Evaluating Gate..." : "Attempt Case Closure"}
        </button>

        {closeError && (
          <div role="alert" data-testid="closure-error-banner" className="mt-2.5 rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs font-semibold text-rose-800 animate-pop">
            Closure Blocked (409): {closeError}
          </div>
        )}
        {(closeSuccess || details.closure) && (
          <div role="status" data-testid="closure-success-banner" className="mt-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-2.5 text-xs font-semibold text-emerald-800 animate-pop">
            {closeSuccess ?? `Case closed (${c.state}) via ${details.closure?.kind ?? "evidence"}.`}
          </div>
        )}
      </div>
    </section>
  );
}
