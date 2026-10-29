"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  BrainCircuit,
  ArrowRight,
  ShieldCheck,
  Activity,
  FileText,
  Users,
  Sparkles,
  LoaderCircle,
  Network,
} from "lucide-react";
import { createSandboxSession } from "@/lib/api";
import { useSandbox } from "@/hooks/use-sandbox";

export default function Home() {
  const router = useRouter();
  const { setTourStep, triggerRefresh } = useSandbox();
  const [launching, setLaunching] = useState(false);

  const handleLaunchDemo = async () => {
    setLaunching(true);
    try {
      await createSandboxSession();
      triggerRefresh();
      setTourStep(1);
    } catch {
      // Fallback: even if backend is waking up, navigate to queue
    } finally {
      setLaunching(false);
      router.push("/app/queue");
    }
  };

  const featurePillars = [
    {
      icon: Activity,
      title: "11-State Clinical Machine",
      desc: "Deterministic transitions with owner & SLA tracking at every step. Urgent cases automatically halve SLA hours.",
      tag: "R1 & R2 Visibility",
      color: "from-blue-500/10 to-indigo-500/10 text-blue-600 border-blue-200",
    },
    {
      icon: BrainCircuit,
      title: "Calibrated Risk & TreeSHAP",
      desc: "XGBoost drop-off probabilities with feature-attribution waterfalls and patient survival curves vs. cohort Kaplan-Meier.",
      tag: "Explainable ML",
      color: "from-purple-500/10 to-pink-500/10 text-purple-600 border-purple-200",
    },
    {
      icon: Users,
      title: "Multilingual Teach-Back",
      desc: "Culturally appropriate patient communications in English, Hindi, and Spanish with interactive comprehension verification.",
      tag: "R3 Patient-Centered",
      color: "from-emerald-500/10 to-teal-500/10 text-emerald-600 border-emerald-200",
    },
    {
      icon: ShieldCheck,
      title: "Human-in-the-Loop Gate",
      desc: "LangGraph checkpointed interrupt() stops automated routing on high-risk, rejected, or overdue cases for clinician sign-off.",
      tag: "R5 Governance",
      color: "from-amber-500/10 to-orange-500/10 text-amber-600 border-amber-200",
    },
  ];

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-slate-50/50 pb-16">
      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-dots opacity-40" />
      <div className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-blue-400/10 blur-3xl" />
      <div className="pointer-events-none absolute top-60 -left-20 h-96 w-96 rounded-full bg-indigo-400/10 blur-3xl" />

      {/* Hero Section */}
      <section className="relative mx-auto max-w-6xl px-4 pt-10 sm:px-6 sm:pt-14">
        <div className="flex flex-col items-center text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-white/90 px-3.5 py-1.5 text-xs font-semibold text-blue-800 shadow-2xs backdrop-blur-xs">
            <span className="flex h-2 w-2 rounded-full bg-blue-600 animate-pulse" />
            <span>Closing the Screening-to-Care Loop</span>
            <span className="text-slate-300">•</span>
            <span className="text-slate-600 font-mono">R1–R6 Specification</span>
          </div>

          <h1 className="mt-6 text-4xl font-black tracking-tight text-slate-900 sm:text-6xl sm:leading-[1.1]">
            Every Abnormal Screening. <br className="hidden sm:inline" />
            <span className="text-gradient">Zero Cases Lost in the Loop.</span>
          </h1>

          <p className="mt-5 max-w-2xl text-base text-slate-600 sm:text-lg leading-relaxed">
            CareLoop AI coordinates positive cancer screenings across issuance, notification, confirmatory tests,
            and specialist referrals — with explainable ML prioritization, grounded patient teach-back,
            and safety-governed human closure.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              data-testid="launch-demo-btn"
              disabled={launching}
              onClick={() => void handleLaunchDemo()}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-bold text-white shadow-md shadow-blue-500/20 transition hover:bg-blue-700 active:scale-98 disabled:opacity-60"
            >
              {launching ? (
                <>
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                  <span>Preparing Sandbox...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Launch Live Demo</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>

            <Link
              href="/app/model-card"
              data-testid="model-card-link"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-5 py-3 text-sm font-semibold text-slate-700 shadow-2xs backdrop-blur-xs transition hover:bg-white hover:text-slate-900 active:scale-98"
            >
              <FileText className="h-4 w-4 text-slate-500" />
              <span>Model Card & Audits</span>
            </Link>

            <Link
              href="/app/metrics"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-5 py-3 text-sm font-semibold text-slate-700 shadow-2xs backdrop-blur-xs transition hover:bg-white hover:text-slate-900 active:scale-98"
            >
              <Activity className="h-4 w-4 text-slate-500" />
              <span>FIFO vs CareLoop Simulation</span>
            </Link>
          </div>
        </div>

        {/* Feature Pillars Grid */}
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {featurePillars.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.title}
                className="group relative flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-5 shadow-2xs transition-all duration-200 hover:-translate-y-1 hover:shadow-md"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className={`flex h-10 w-10 items-center justify-center rounded-xl border bg-gradient-to-br ${p.color} shadow-2xs`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-600">
                      {p.tag}
                    </span>
                  </div>
                  <h3 className="mt-4 text-sm font-bold text-slate-900 group-hover:text-blue-700 transition">
                    {p.title}
                  </h3>
                  <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                    {p.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Clinical Problem vs Solution */}
        <div className="mt-10 grid gap-5 md:grid-cols-2">
          <div className="rounded-2xl border border-rose-200/80 bg-rose-50/40 p-6 shadow-2xs">
            <div className="flex items-center gap-2 text-rose-700">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-100 text-rose-700">✕</span>
              <h2 className="text-base font-bold text-slate-900">The Challenge: Loop Breakage</h2>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-600">
              Abnormal FIT, Mammography, and Pap/HPV screenings stall across fragmented transitions:
              silent notifications, unverified patient comprehension, unassigned drop-offs,
              and capacity-rejected referrals left without closure. Over 30% of high-risk patients
              experience diagnostic delay in traditional FIFO workflows.
            </p>
          </div>

          <div className="rounded-2xl border border-blue-200/80 bg-blue-50/40 p-6 shadow-2xs">
            <div className="flex items-center gap-2 text-blue-700">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100 text-blue-700">✓</span>
              <h2 className="text-base font-bold text-slate-900">The CareLoop Guarantee</h2>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-600">
              Deterministic 11-stage transitions guarantee every case has an assigned owner, active SLA countdown,
              and documented evidence before closure. ML models prioritize highest-risk drop-offs,
              while LangGraph halts automated routing whenever human clinical judgment is required.
            </p>
          </div>
        </div>

        {/* Architecture & Governance Pipeline */}
        <div className="mt-10 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2.5">
              <Network className="h-5 w-5 text-blue-600" />
              <h2 className="text-base font-bold text-slate-900">System Architecture & Governance Pipeline</h2>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600">
              Pure Domain • Fast-Inference ML • Audit Ledger
            </span>
          </div>

          <pre
            aria-label="Architecture diagram"
            className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-4 font-mono text-[11px] leading-relaxed text-slate-200 shadow-inner"
          >
            {`[Screening Result Issued (FIT, Mammography, Pap/HPV)]
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Pure Domain Engine (apps/api/app/domain)                               │
│  • 11-State Lifecycle: Owner Role & SLA Clock (Urgent tier halves SLA) │
│  • Multi-Factor Priority: 100 * (0.45*Urgency + 0.35*P_drop + 0.20*SLA)│
│  • Strict Evidence Closure Gate: Requires proof or clinician override  │
└────────────────────────────────────────────────────────────────────────┘
        │
        ├──► [Calibrated XGBoost (Brier <0.18) + TreeSHAP + Cox PH S(t)]
        ├──► [Grounded LLM + Regex Fact Validator + ADS Divergence Audit]
        └──► [LangGraph State Machine with Checkpointed interrupt() Gate]
                   │
                   ├── Coordinator Queue & SLA Countdown (R1, R2)
                   ├── Multilingual Patient Portal & Teach-Back (R3)
                   ├── Clinician Desk: SBAR Referral Hand-Offs (R4)
                   └── Append-Only Audit Trail & Queue Simulation (R6)`}
          </pre>
        </div>

        {/* Clinical Safety Banner */}
        <aside className="mt-8 flex items-center gap-3.5 rounded-2xl border border-amber-300/80 bg-amber-50/70 p-5 text-amber-950 shadow-2xs">
          <ShieldCheck className="h-5 w-5 shrink-0 text-amber-600" />
          <div className="text-xs leading-relaxed">
            <strong className="font-bold text-amber-900">Clinical Safety & Synthetic Data Notice:</strong>{" "}
            CareLoop AI is an assistive decision-support platform operating on 100% synthetic patient records.
            It never diagnoses conditions, never prescribes medications, and never closes or escalates urgent
            cases without documented evidence or authorized human clinical sign-off.
          </div>
        </aside>
      </section>
    </div>
  );
}
