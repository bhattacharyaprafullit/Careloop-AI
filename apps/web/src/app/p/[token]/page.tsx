"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  HeartHandshake,
  Calendar,
  ArrowLeft,
  Send,
  LoaderCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { Language, PatientPortalView, TeachBackResponse } from "@/lib/types";

export default function PatientPortalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const [selectedLang, setSelectedLang] = useState<Language | null>(null);
  const [ackDone, setAckDone] = useState(false);
  const [teachbackAnswer, setTeachbackAnswer] = useState(
    "I will attend my follow-up confirmatory test and appointment this week."
  );
  const [teachbackResult, setTeachbackResult] = useState<TeachBackResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const {
    data: portalData,
    isLoading,
    refetch,
  } = useQuery<PatientPortalView>({
    queryKey: ["patient-portal", token, selectedLang],
    queryFn: () => {
      const qs = selectedLang ? `?lang=${selectedLang}` : "";
      return apiFetch<PatientPortalView>(`/api/v1/patient/${token}${qs}`);
    },
  });

  const handleAcknowledge = async () => {
    setBusy(true);
    setErrorMsg(null);
    try {
      await apiFetch(`/api/v1/patient/${token}/acknowledge`, {
        method: "POST",
      });
      setAckDone(true);
      await refetch();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Could not acknowledge");
    } finally {
      setBusy(false);
    }
  };

  const handleTeachBack = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await apiFetch<TeachBackResponse>(
        `/api/v1/patient/${token}/teachback`,
        {
          method: "POST",
          body: JSON.stringify({ reply_text: teachbackAnswer }),
        }
      );
      setTeachbackResult(res);
      await refetch();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Could not submit teach-back");
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <div className="h-64 animate-pulse rounded-3xl bg-slate-200/80" />
      </main>
    );
  }

  if (!portalData) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-800">
          Patient portal link expired or invalid.
        </div>
      </main>
    );
  }

  const activeLang = (selectedLang ?? portalData.language) as Language;

  return (
    <main className="min-h-screen bg-slate-50/70 px-4 py-8 text-slate-900 antialiased">
      <div className="mx-auto max-w-3xl space-y-5">
        {/* Top Header Card */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-xs">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
                <HeartHandshake className="h-4 w-4" />
              </span>
              <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Patient Follow-Up Care (R3)
              </p>
            </div>
            <h1 className="mt-2 text-2xl font-black text-slate-900 sm:text-3xl">
              Case {portalData.case_id}
            </h1>
            <p className="mt-1 flex items-center gap-2 text-xs text-slate-600">
              <Calendar className="h-3.5 w-3.5 text-slate-400" />
              <span>Target Due Date: <strong>{portalData.due_date}</strong></span>
              <span>•</span>
              <span className="font-semibold text-slate-800">
                {portalData.acknowledged || ackDone ? "Acknowledged" : "Awaiting Acknowledgement"}
              </span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {(["en", "hi", "es"] as Language[]).map((lang) => (
              <button
                key={lang}
                type="button"
                data-testid={`lang-btn-${lang}`}
                onClick={() => setSelectedLang(lang)}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all ${
                  activeLang === lang
                    ? "bg-blue-600 text-white shadow-xs"
                    : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                {lang === "en" ? "English" : lang === "hi" ? "हिन्दी" : "Español"}
              </button>
            ))}
            <Link
              href={`/app/cases/${portalData.case_id}`}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"
            >
              <ArrowLeft className="h-3 w-3" />
              <span>Coord View</span>
            </Link>
          </div>
        </div>

        {/* 3-Step Patient Tracker */}
        <section
          aria-label="3-step patient progress tracker"
          data-testid="patient-3-step-tracker"
          className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xs"
        >
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600">
            Your 3-Step Care Loop Journey
          </h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {portalData.steps.map((st, idx) => (
              <div
                key={idx}
                className={`rounded-2xl border p-4 transition ${
                  st.done
                    ? "border-emerald-300 bg-emerald-50/70 text-emerald-950"
                    : "border-slate-200 bg-slate-50/60 text-slate-700"
                }`}
              >
                <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wider">
                  <span>Step {idx + 1}</span>
                  {st.done ? (
                    <span className="inline-flex items-center gap-1 text-emerald-700">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Done
                    </span>
                  ) : (
                    <span className="text-slate-600 font-normal">Next Step</span>
                  )}
                </div>
                <div className="mt-2 text-sm font-bold leading-snug">{st.label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Multilingual Message */}
        <section className="rounded-3xl border border-blue-200 bg-gradient-to-br from-white to-blue-50/30 p-6 shadow-xs">
          <div className="flex items-center justify-between border-b border-blue-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900">
              Message from Your Care Team ({activeLang.toUpperCase()})
            </h2>
            {portalData.language_fallback && (
              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold text-amber-900">
                English Fallback
              </span>
            )}
          </div>

          <p
            data-testid="patient-message-body"
            className="mt-4 text-base leading-relaxed text-slate-800"
          >
            {portalData.status_text}
          </p>

          <div className="mt-4 rounded-2xl border border-blue-200/80 bg-blue-50/60 p-4 text-xs font-semibold text-blue-950">
            <strong>Next Action:</strong> {portalData.next_step_text}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              data-testid="patient-acknowledge-btn"
              disabled={busy}
              onClick={() => void handleAcknowledge()}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs transition hover:bg-emerald-700 active:scale-95 disabled:opacity-50"
            >
              <CheckCircle2 className="h-4 w-4" />
              <span>I understand (Acknowledge Result)</span>
            </button>
            {(ackDone || portalData.acknowledged) && (
              <span
                data-testid="ack-confirmed-badge"
                className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800 animate-pop"
              >
                ✓ Acknowledgement recorded
              </span>
            )}
          </div>
        </section>

        {/* Teach-Back Confirmation Form */}
        <form
          onSubmit={(e) => void handleTeachBack(e)}
          className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xs"
        >
          <div className="border-b border-slate-100 pb-3">
            <h2 className="text-sm font-bold text-slate-900">
              Confirm Your Understanding (Teach-Back)
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              In your own words, what is your next follow-up step?
            </p>
          </div>

          <textarea
            aria-label="Your teach-back response"
            data-testid="teachback-input"
            rows={3}
            value={teachbackAnswer}
            onChange={(e) => setTeachbackAnswer(e.target.value)}
            className="mt-4 w-full rounded-2xl border border-slate-200 bg-slate-50/50 p-3.5 text-xs leading-relaxed text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-hidden"
          />

          <div className="mt-3.5 flex flex-wrap items-center gap-2">
            <button
              type="submit"
              data-testid="submit-teachback-btn"
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700 active:scale-95 disabled:opacity-50"
            >
              {busy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              <span>Submit Response</span>
            </button>
            <button
              type="button"
              data-testid="fill-confused-btn"
              onClick={() => setTeachbackAnswer("I am not sure what to do or where to go.")}
              className="rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
            >
              Test &ldquo;Confused&rdquo; Response
            </button>
          </div>

          {teachbackResult && (
            <div
              role="status"
              data-testid="teachback-result-banner"
              className={`mt-4 rounded-2xl border p-4 text-xs animate-pop ${
                teachbackResult.label === "understood"
                  ? "border-emerald-300 bg-emerald-50/80 text-emerald-950"
                  : "border-amber-300 bg-amber-50/80 text-amber-950"
              }`}
            >
              <div className="font-black text-sm">
                Teach-Back Classification:{" "}
                <span data-testid="teachback-label" className="underline">
                  {teachbackResult.label.toUpperCase()}
                </span>
                {teachbackResult.escalated && " • (Escalated to Coordinator Queue)"}
              </div>
              <p className="mt-1 leading-relaxed">{teachbackResult.followup_text}</p>
            </div>
          )}

          {errorMsg && (
            <p className="mt-3 text-xs font-semibold text-rose-700">{errorMsg}</p>
          )}
        </form>
      </div>
    </main>
  );
}
