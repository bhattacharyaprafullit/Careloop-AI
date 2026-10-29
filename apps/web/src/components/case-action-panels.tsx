"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  ExternalLink,
  MessageSquare,
  Send,
  CheckCircle2,
  XCircle,
  FileText,
} from "lucide-react";
import { DocumentedClosureGate } from "@/components/documented-closure-gate";
import { apiFetch } from "@/lib/api";
import {
  REASON_CODES,
  type CaseDetailsResponse,
  type ReasonCode,
} from "@/lib/types";

export function CaseCollaborationAndClosurePanels({
  details,
  onUpdated,
}: {
  details: CaseDetailsResponse;
  onUpdated: () => void;
}) {
  const { case: c, patient: pat, referral: ref } = details;
  const [toOrg, setToOrg] = useState("Metro Diagnostic Gastroenterology");
  const [refBusy, setRefBusy] = useState(false);
  const [rejectReason, setRejectReason] = useState<ReasonCode>("referral_rejected_capacity");

  const [consultKind, setConsultKind] = useState<"clinician_to_clinician" | "patient_to_clinician">("clinician_to_clinician");
  const [consultMsg, setConsultMsg] = useState("Reviewing abnormal screening result and confirming diagnostic workup.");
  const [consultBusy, setConsultBusy] = useState(false);

  const handleCreateReferral = async () => {
    setRefBusy(true);
    try {
      await apiFetch("/api/v1/referrals", {
        method: "POST",
        roleOverride: "clinician",
        body: JSON.stringify({ case_id: c.id, to_org: toOrg }),
      });
      onUpdated();
    } finally {
      setRefBusy(false);
    }
  };

  const handleDecideReferral = async (refId: string, decision: "accept" | "reject") => {
    setRefBusy(true);
    try {
      await apiFetch(`/api/v1/referrals/${refId}/decision`, {
        method: "POST",
        roleOverride: "clinician",
        body: JSON.stringify({ decision, reason_code: decision === "reject" ? rejectReason : null }),
      });
      onUpdated();
    } finally {
      setRefBusy(false);
    }
  };

  const handleCreateConsult = async () => {
    if (!consultMsg.trim()) return;
    setConsultBusy(true);
    try {
      await apiFetch("/api/v1/consults", {
        method: "POST",
        body: JSON.stringify({ case_id: c.id, kind: consultKind, message: consultMsg }),
      });
      onUpdated();
    } finally {
      setConsultBusy(false);
    }
  };

  return (
    <div className="mt-6 grid gap-5 lg:grid-cols-3">
      {/* Patient Portal & Outreach */}
      <section className="flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs">
        <div>
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-blue-600" />
              <h3 className="text-sm font-bold text-slate-900">Patient Outreach (R3)</h3>
            </div>
            <Link
              href={`/p/${c.patient_token}`}
              data-testid="patient-portal-link"
              className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1 text-xs font-bold text-white shadow-2xs transition hover:bg-blue-700"
            >
              <span>Portal</span>
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>

          <div className="mt-2.5 text-[11px] text-slate-600">
            Token: <code className="font-mono font-semibold text-slate-800">{c.patient_token}</code> • Lang:{" "}
            <strong className="text-blue-700">{pat.language.toUpperCase()}</strong>
          </div>

          <div className="mt-3 space-y-2">
            {details.messages.slice(-3).map((m) => (
              <div key={m.id} className="rounded-xl border border-slate-100 bg-slate-50/80 p-2.5 text-xs">
                <div className="flex items-center justify-between font-bold text-slate-700 text-[10px]">
                  <span>{m.direction.toUpperCase()} • {m.language.toUpperCase()}</span>
                  {m.teachback_label && (
                    <span className="rounded-full bg-amber-100 px-1.5 py-0.2 font-semibold text-amber-900">
                      Teach-back: {m.teachback_label}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-slate-800 leading-snug">{m.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Referral & Consults (R4) */}
      <section className="flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs">
        <div>
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-indigo-600" />
              <h3 className="text-sm font-bold text-slate-900">SBAR Referrals & Consults (R4)</h3>
            </div>
            <span className="text-[10px] font-semibold text-slate-600">Cross-Provider</span>
          </div>

          <div className="mt-3 flex gap-2">
            <input
              type="text"
              aria-label="Target specialty organization"
              value={toOrg}
              onChange={(e) => setToOrg(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium focus:border-blue-500 focus:outline-hidden"
            />
            <button
              type="button"
              data-testid="create-referral-btn"
              disabled={refBusy}
              onClick={() => void handleCreateReferral()}
              className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-bold text-white shadow-2xs transition hover:bg-indigo-700 disabled:opacity-50"
            >
              Send SBAR
            </button>
          </div>

          {ref && (
            <div data-testid={`referral-card-${ref.id}`} className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-2.5 text-xs">
              <div className="flex items-center justify-between font-bold text-slate-800">
                <span>{ref.to_org}</span>
                <span className="rounded-full bg-indigo-100 px-2 py-0.2 text-[10px] uppercase font-bold text-indigo-800">
                  {ref.status}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-600">
                <strong>S:</strong> {ref.sbar.situation} | <strong>R:</strong> {ref.sbar.recommendation}
              </p>
              {ref.status === "sent" && (
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    data-testid={`accept-referral-${ref.id}`}
                    onClick={() => void handleDecideReferral(ref.id, "accept")}
                    className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-[11px] font-bold text-white shadow-2xs hover:bg-emerald-700"
                  >
                    <CheckCircle2 className="h-3 w-3" /> Accept
                  </button>
                  <select
                    aria-label="Rejection reason code"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value as ReasonCode)}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                  >
                    {REASON_CODES.map((rc) => (
                      <option key={rc} value={rc}>{rc}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    data-testid={`reject-referral-${ref.id}`}
                    onClick={() => void handleDecideReferral(ref.id, "reject")}
                    className="inline-flex items-center gap-1 rounded-lg bg-rose-600 px-2.5 py-1 text-[11px] font-bold text-white shadow-2xs hover:bg-rose-700"
                  >
                    <XCircle className="h-3 w-3" /> Reject
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="mt-3 border-t border-slate-100 pt-2.5">
            <div className="flex gap-2">
              <select
                aria-label="Consult thread type"
                value={consultKind}
                onChange={(e) => setConsultKind(e.target.value as "clinician_to_clinician" | "patient_to_clinician")}
                className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
              >
                <option value="clinician_to_clinician">Clinician-to-Clinician</option>
                <option value="patient_to_clinician">Patient-to-Clinician</option>
              </select>
              <button
                type="button"
                data-testid="start-consult-btn"
                disabled={consultBusy}
                onClick={() => void handleCreateConsult()}
                className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-2.5 py-1 text-[11px] font-bold text-white shadow-2xs hover:bg-slate-800 disabled:opacity-50"
              >
                <Send className="h-3 w-3" /> Post
              </button>
            </div>
            <input
              type="text"
              aria-label="Consult message body"
              value={consultMsg}
              onChange={(e) => setConsultMsg(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-slate-200 px-2.5 py-1 text-xs focus:border-blue-500 focus:outline-hidden"
            />
          </div>
        </div>
      </section>

      {/* Safe Closure Gate (R5) */}
      <DocumentedClosureGate details={details} onUpdated={onUpdated} />
    </div>
  );
}
