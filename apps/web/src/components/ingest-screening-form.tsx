"use client";

import React, { useState } from "react";
import { LoaderCircle, TriangleAlert } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { ScreeningType } from "@/lib/types";

export function IngestScreeningForm({
  onSuccess,
  onCancel,
}: {
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [screeningType, setScreeningType] = useState<ScreeningType>("FIT");
  const [severityGrade, setSeverityGrade] = useState<number>(3);
  const [urgentFlag, setUrgentFlag] = useState<boolean>(true);
  const [leadTime, setLeadTime] = useState<number>(14);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    setIngestLoading(true);
    setIngestError(null);
    try {
      await apiFetch("/api/v1/screenings", {
        method: "POST",
        body: JSON.stringify({
          screening_type: screeningType,
          severity_grade: severityGrade,
          urgent_flag: urgentFlag,
          finding_to_order_days: 4.0,
          scheduling_lead_time: leadTime,
        }),
      });
      onSuccess();
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Failed to ingest screening");
    } finally {
      setIngestLoading(false);
    }
  };

  return (
    <form
      onSubmit={(e) => void handleIngest(e)}
      data-testid="ingest-screening-form"
      className="mt-5 rounded-2xl border border-blue-200 bg-white p-5 shadow-md animate-fade-up"
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h2 className="text-sm font-bold text-slate-900">
          Ingest Abnormal Screening Result{" "}
          <span className="font-normal text-slate-500">(Creates RESULT_ISSUED Case)</span>
        </h2>
        <span className="text-[11px] font-semibold text-blue-600">Deterministic Engine</span>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-4">
        <div>
          <label htmlFor="screening-type-select" className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
            Screening Type
          </label>
          <select
            id="screening-type-select"
            value={screeningType}
            onChange={(e) => setScreeningType(e.target.value as ScreeningType)}
            className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs font-semibold text-slate-800 transition focus:border-blue-500 focus:bg-white focus:outline-hidden"
          >
            <option value="FIT">FIT (Colorectal)</option>
            <option value="MAMMOGRAPHY">Mammography (Breast)</option>
            <option value="PAP_HPV">Pap / HPV (Cervical)</option>
          </select>
        </div>

        <div>
          <label htmlFor="severity-grade-input" className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
            Severity Grade (0-5)
          </label>
          <input
            id="severity-grade-input"
            type="number"
            min={0}
            max={5}
            value={severityGrade}
            onChange={(e) => setSeverityGrade(Number(e.target.value))}
            className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs font-semibold text-slate-800 transition focus:border-blue-500 focus:bg-white focus:outline-hidden"
          />
        </div>

        <div>
          <label htmlFor="lead-time-input" className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
            Lead Time (Days)
          </label>
          <input
            id="lead-time-input"
            type="number"
            min={0}
            max={365}
            value={leadTime}
            onChange={(e) => setLeadTime(Number(e.target.value))}
            className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs font-semibold text-slate-800 transition focus:border-blue-500 focus:bg-white focus:outline-hidden"
          />
        </div>

        <div className="flex flex-col justify-end">
          <label className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/60 p-2.5 text-xs font-semibold text-amber-950 cursor-pointer">
            <input
              type="checkbox"
              checked={urgentFlag}
              onChange={(e) => setUrgentFlag(e.target.checked)}
              className="rounded text-amber-600 focus:ring-amber-500"
            />
            <span>Urgent Tier 1 (Halves SLA)</span>
          </label>
        </div>
      </div>

      {ingestError && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-rose-50 p-2.5 text-xs font-semibold text-rose-700">
          <TriangleAlert className="h-4 w-4 shrink-0" />
          <span>{ingestError}</span>
        </div>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={ingestLoading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50"
        >
          {ingestLoading && <LoaderCircle className="h-3.5 w-3.5 animate-spin" />}
          <span>{ingestLoading ? "Creating..." : "Submit Screening"}</span>
        </button>
      </div>
    </form>
  );
}
