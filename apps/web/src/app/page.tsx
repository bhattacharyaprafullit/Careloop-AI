"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ShieldCheck,
  Activity,
  FileText,
  Users,
  Sparkles,
  LoaderCircle,
  Clock,
  MessageSquare,
  BarChart3,
} from "lucide-react";
import { ensureSandboxToken } from "@/lib/api";
import { useSandbox } from "@/hooks/use-sandbox";
import { HowItWorks } from "@/components/how-it-works";
import { PatientSafetySection } from "@/components/patient-safety-section";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  const router = useRouter();
  const { setTourStep } = useSandbox();
  const [launching, setLaunching] = useState(false);

  const handleLaunchDemo = () => {
    setLaunching(true);
    void ensureSandboxToken();
    setTourStep(1);
    router.push("/app/queue");
  };

  const featurePillars = [
    {
      icon: Activity,
      title: "11-State Case Visibility",
      desc: "Deterministic lifecycle tracking from result issuance through patient acknowledgement, referral, and documented closure with append-only ledger.",
      tag: "R1 Visibility",
      color: "from-blue-500/10 to-indigo-500/10 text-blue-600 border-blue-200",
    },
    {
      icon: Clock,
      title: "Ownership & SLA Progression",
      desc: "Strict coordinator and clinician assignment at every step. Tiered SLAs (72h vs 14d) with real-time countdowns and overdue breach detection.",
      tag: "R2 Ownership & SLA",
      color: "from-purple-500/10 to-pink-500/10 text-purple-600 border-purple-200",
    },
    {
      icon: Users,
      title: "Multilingual Patient Teach-Back",
      desc: "Culturally appropriate patient communications in English, Hindi, and Spanish with interactive comprehension verification and auto-escalation.",
      tag: "R3 Patient-Centered",
      color: "from-emerald-500/10 to-teal-500/10 text-emerald-600 border-emerald-200",
    },
    {
      icon: MessageSquare,
      title: "Cross-Provider Consults & SBAR",
      desc: "Timely patient-to-clinician and clinician-to-clinician consult threads with structured LLM-generated SBAR notes and referral loops.",
      tag: "R4 Coordination",
      color: "from-cyan-500/10 to-blue-500/10 text-cyan-600 border-cyan-200",
    },
    {
      icon: ShieldCheck,
      title: "Human-in-the-Loop & Closure Gate",
      desc: "LangGraph checkpointed approvals for high-risk cases and strict diagnostic closure enforcement requiring verified clinical evidence.",
      tag: "R5 Governance",
      color: "from-amber-500/10 to-orange-500/10 text-amber-600 border-amber-200",
    },
    {
      icon: BarChart3,
      title: "Impact Metrics & Simulation",
      desc: "100-run stochastic queue simulation proving a 14-day median resolution reduction over traditional FIFO, plus full turnaround KPIs.",
      tag: "R6 Impact & Closure",
      color: "from-violet-500/10 to-purple-500/10 text-violet-600 border-violet-200",
    },
  ];

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-slate-50/50 pb-16 dark:bg-slate-950/60">
      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-dots opacity-40 dark:opacity-20" />
      <div className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-blue-400/10 blur-3xl animate-pulse" />
      <div className="pointer-events-none absolute top-60 -left-20 h-96 w-96 rounded-full bg-indigo-400/10 blur-3xl animate-blob" />

      {/* Top Navbar */}
      <header className="relative mx-auto flex max-w-6xl items-center justify-between px-4 pt-6 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-700 via-indigo-600 to-sky-500 text-white shadow-sm shadow-blue-500/25 group-hover:scale-105 transition-transform duration-200">
            <Activity className="h-5 w-5" />
          </span>
          <div className="flex flex-col">
            <span className="text-base font-extrabold tracking-tight text-slate-900 dark:text-white">CareLoop AI</span>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 -mt-1 dark:text-slate-400">Closed-Loop Care</span>
          </div>
        </Link>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button
            type="button"
            onClick={handleLaunchDemo}
            className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs transition hover:bg-blue-700 active:scale-95"
          >
            <span>Launch App</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative mx-auto max-w-6xl px-4 pt-8 sm:px-6 sm:pt-12">
        <div className="flex flex-col items-center text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-white/90 px-3.5 py-1.5 text-xs font-semibold text-blue-800 shadow-2xs backdrop-blur-xs dark:border-blue-900/60 dark:bg-slate-900/90 dark:text-blue-300">
            <span className="flex h-2 w-2 rounded-full bg-blue-600 animate-pulse" />
            <span>Closing the Screening-to-Care Loop</span>
            <span className="text-slate-300 dark:text-slate-600">•</span>
            <span className="text-slate-600 font-mono dark:text-slate-400">R1–R6 Specification</span>
          </div>

          <h1 className="mt-6 text-4xl font-black tracking-tight text-slate-900 sm:text-6xl sm:leading-[1.1] dark:text-white">
            Every Abnormal Screening. <br className="hidden sm:inline" />
            <span className="text-gradient">Zero Cases Lost in the Loop.</span>
          </h1>

          <p className="mt-5 max-w-2xl text-base text-slate-600 sm:text-lg leading-relaxed dark:text-slate-300">
            CareLoop AI bridges the gap between abnormal screening results and completed care by coordinating
            patient notifications, confirmatory tests, specialist referrals, and follow-ups — with explainable
            ML prioritization, patient understanding checks, and safety-governed human oversight.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              data-testid="launch-demo-btn"
              disabled={launching}
              onMouseEnter={() => void ensureSandboxToken()}
              onClick={handleLaunchDemo}
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
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-5 py-3 text-sm font-semibold text-slate-700 shadow-2xs backdrop-blur-xs transition hover:bg-white hover:text-slate-900 active:scale-98 dark:border-slate-700 dark:bg-slate-800/90 dark:text-slate-200 dark:hover:bg-slate-700 dark:hover:text-white"
            >
              <FileText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <span>Model Card & Audits</span>
            </Link>

            <Link
              href="/app/metrics"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-5 py-3 text-sm font-semibold text-slate-700 shadow-2xs backdrop-blur-xs transition hover:bg-white hover:text-slate-900 active:scale-98 dark:border-slate-700 dark:bg-slate-800/90 dark:text-slate-200 dark:hover:bg-slate-700 dark:hover:text-white"
            >
              <Activity className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <span>FIFO vs CareLoop Simulation</span>
            </Link>
          </div>
        </div>

        {/* 4-Stage How It Works Walkthrough */}
        <HowItWorks />

        {/* Patient Data Safety & Governance Safeguards */}
        <PatientSafetySection />

        {/* Feature Pillars Grid */}
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {featurePillars.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.title}
                className="group relative flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-5 shadow-2xs transition-all duration-200 hover:-translate-y-1 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className={`flex h-10 w-10 items-center justify-center rounded-xl border bg-gradient-to-br ${p.color} shadow-2xs dark:border-slate-700`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                      {p.tag}
                    </span>
                  </div>
                  <h3 className="mt-4 text-sm font-bold text-slate-900 group-hover:text-blue-700 transition dark:text-white dark:group-hover:text-blue-400">
                    {p.title}
                  </h3>
                  <p className="mt-1.5 text-xs text-slate-600 leading-relaxed dark:text-slate-400">
                    {p.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Clinical Problem vs Solution */}
        <div className="mt-10 grid gap-5 md:grid-cols-2">
          <div className="rounded-2xl border border-rose-200/80 bg-rose-50/40 p-6 shadow-2xs dark:border-rose-900/50 dark:bg-rose-950/20">
            <div className="flex items-center gap-2 text-rose-700 dark:text-rose-400">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-100 text-rose-700 dark:bg-rose-900/50 dark:text-rose-300">✕</span>
              <h2 className="text-base font-bold text-slate-900 dark:text-rose-100">The Challenge: Loop Breakage</h2>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
              Abnormal FIT, Mammography, and Pap/HPV screenings stall across fragmented transitions:
              silent notifications, unverified patient comprehension, unassigned drop-offs,
              and capacity-rejected referrals left without closure. Over 30% of high-risk patients
              experience diagnostic delay in traditional FIFO workflows.
            </p>
          </div>

          <div className="rounded-2xl border border-blue-200/80 bg-blue-50/40 p-6 shadow-2xs dark:border-blue-900/50 dark:bg-blue-950/20">
            <div className="flex items-center gap-2 text-blue-700 dark:text-blue-400">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">✓</span>
              <h2 className="text-base font-bold text-slate-900 dark:text-blue-100">The CareLoop Guarantee</h2>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
              Deterministic 11-stage transitions guarantee every case has an assigned owner, active SLA countdown,
              and documented evidence before closure. ML models prioritize highest-risk drop-offs,
              while LangGraph halts automated routing whenever human clinical judgment is required.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
