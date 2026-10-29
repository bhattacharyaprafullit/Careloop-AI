"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  MessageSquare,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Send,
  Building,
  LoaderCircle,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { useSandbox } from "@/hooks/use-sandbox";
import { apiFetch } from "@/lib/api";
import {
  REASON_CODES,
  type ConsultItem,
  type ReasonCode,
  type ReferralItem,
} from "@/lib/types";

export default function ClinicianDeskPage() {
  const { refreshKey, triggerRefresh } = useSandbox();
  const [rejectReason, setRejectReason] = useState<Record<string, ReasonCode>>({});
  const [replyText, setReplyText] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data: refData, isLoading: refLoading } = useQuery<{ items: ReferralItem[] }>({
    queryKey: ["clinician-referrals", refreshKey],
    queryFn: () => apiFetch<{ items: ReferralItem[] }>("/api/v1/referrals"),
  });

  const { data: conData, isLoading: conLoading } = useQuery<{ items: ConsultItem[] }>({
    queryKey: ["clinician-consults", refreshKey],
    queryFn: () => apiFetch<{ items: ConsultItem[] }>("/api/v1/consults"),
  });

  const referrals = refData?.items ?? [];
  const consults = conData?.items ?? [];

  const handleDecision = async (refId: string, decision: "accept" | "reject") => {
    setBusyId(refId);
    setFeedback(null);
    const reason = rejectReason[refId] ?? "referral_rejected_capacity";
    try {
      await apiFetch(`/api/v1/referrals/${refId}/decision`, {
        method: "POST",
        roleOverride: "clinician",
        body: JSON.stringify({
          decision,
          reason_code: decision === "reject" ? reason : null,
        }),
      });
      setFeedback(
        decision === "accept"
          ? `Referral ${refId} accepted (advanced to REFERRAL_ACCEPTED).`
          : `Referral ${refId} rejected (${reason}); case transitioned to REJECTED.`
      );
      triggerRefresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not process referral.");
    } finally {
      setBusyId(null);
    }
  };

  const handleReply = async (threadId: string) => {
    const body = replyText[threadId]?.trim();
    if (!body) return;
    setBusyId(threadId);
    try {
      await apiFetch(`/api/v1/consults/${threadId}/reply`, {
        method: "POST",
        roleOverride: "clinician",
        body: JSON.stringify({ message: body }),
      });
      setReplyText((prev) => ({ ...prev, [threadId]: "" }));
      setFeedback(`Posted clinician reply to thread ${threadId}.`);
      triggerRefresh();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-black tracking-tight text-slate-900">
          Cross-Provider Clinician Desk (R4)
        </h1>
        <p className="mt-1 text-xs text-slate-500 max-w-2xl">
          Review grounded SBAR referral hand-offs, accept or reject with structured ReasonCodes,
          and collaborate across clinician-to-clinician and patient-to-clinician consult threads.
        </p>
      </div>

      {feedback && (
        <div
          role="status"
          data-testid="clinician-feedback"
          className="mt-4 flex items-center gap-2 rounded-2xl border border-blue-200 bg-blue-50/80 p-3.5 text-xs font-bold text-blue-950 animate-pop"
        >
          <CheckCircle2 className="h-4 w-4 text-blue-600 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* SBAR Referrals */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
              <Building className="h-4 w-4 text-blue-600" />
              <span>Specialty Referrals ({referrals.length})</span>
            </h2>
          </div>

          {refLoading ? (
            <div className="h-36 animate-pulse rounded-2xl bg-slate-200/70" />
          ) : (
            referrals.map((r) => (
              <div
                key={r.id}
                data-testid={`clinician-referral-${r.id}`}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition hover:shadow-md"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-blue-700 border border-blue-200/60">
                      {r.to_org}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-black uppercase text-slate-700">
                      {r.status}
                    </span>
                    {r.reason_code && (
                      <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-800">
                        {r.reason_code}
                      </span>
                    )}
                  </div>
                  <Link
                    href={`/app/cases/${r.case_id}`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:underline"
                  >
                    <span>{r.patient_alias} ({r.case_id})</span>
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>

                <div className="mt-3.5 space-y-1.5 rounded-xl bg-slate-50/70 p-3 text-xs leading-relaxed">
                  <div><strong className="text-blue-800">S (Situation):</strong> {r.sbar.situation}</div>
                  <div><strong className="text-slate-700">B (Background):</strong> {r.sbar.background}</div>
                  <div><strong className="text-amber-800">A (Assessment):</strong> {r.sbar.assessment}</div>
                  <div><strong className="text-emerald-800">R (Recommendation):</strong> {r.sbar.recommendation}</div>
                </div>

                {r.status === "sent" && (
                  <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                    <button
                      type="button"
                      data-testid={`clinician-accept-${r.id}`}
                      disabled={busyId === r.id}
                      onClick={() => void handleDecision(r.id, "accept")}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-emerald-700 active:scale-95 disabled:opacity-50"
                    >
                      {busyId === r.id ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                      <span>Accept</span>
                    </button>
                    <select
                      aria-label={`Rejection reason for ${r.id}`}
                      value={rejectReason[r.id] ?? "referral_rejected_capacity"}
                      onChange={(e) =>
                        setRejectReason((prev) => ({ ...prev, [r.id]: e.target.value as ReasonCode }))
                      }
                      className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700"
                    >
                      {REASON_CODES.map((rc) => (
                        <option key={rc} value={rc}>{rc}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      data-testid={`clinician-reject-${r.id}`}
                      disabled={busyId === r.id}
                      onClick={() => void handleDecision(r.id, "reject")}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-rose-700 active:scale-95 disabled:opacity-50"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      <span>Reject</span>
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </section>

        {/* Cross-Provider Consult Threads */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-indigo-600" />
              <span>Consult Threads ({consults.length})</span>
            </h2>
          </div>

          {conLoading ? (
            <div className="h-36 animate-pulse rounded-2xl bg-slate-200/70" />
          ) : (
            consults.map((t) => (
              <div
                key={t.id}
                data-testid={`consult-thread-${t.id}`}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition hover:shadow-md"
              >
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-700 uppercase">
                    {t.kind.replace(/_/g, " ")} • {t.status}
                  </span>
                  <Link
                    href={`/app/cases/${t.case_id}`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:underline"
                  >
                    <span>{t.patient_alias} ({t.case_id})</span>
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>

                <div className="mt-3.5 space-y-2">
                  {t.thread.map((m, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-slate-100 bg-slate-50/70 p-2.5 text-xs leading-relaxed"
                    >
                      <span className="font-black text-slate-900 capitalize">{m.sender_role}:</span>{" "}
                      <span className="text-slate-700">{m.body}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-3.5 flex gap-2 border-t border-slate-100 pt-3">
                  <input
                    type="text"
                    placeholder="Write clinician reply..."
                    value={replyText[t.id] ?? ""}
                    onChange={(e) => setReplyText((prev) => ({ ...prev, [t.id]: e.target.value }))}
                    className="flex-1 rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-1.5 text-xs focus:border-blue-500 focus:bg-white focus:outline-hidden"
                  />
                  <button
                    type="button"
                    data-testid={`reply-consult-${t.id}`}
                    disabled={busyId === t.id}
                    onClick={() => void handleReply(t.id)}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-3.5 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-slate-800 disabled:opacity-50"
                  >
                    <Send className="h-3 w-3" />
                    <span>Reply</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </section>
      </div>
    </AppShell>
  );
}
