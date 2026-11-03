"use client";

import React from "react";
import { Activity, Users, MessageSquare, ShieldCheck, ArrowRight, CheckCircle2 } from "lucide-react";

const WORKFLOW_STEPS = [
  {
    step: "01",
    title: "Abnormal Screening & AI Triage",
    badge: "Predictive Risk Engine",
    color: "from-blue-500/10 to-indigo-500/10 text-blue-600 border-blue-200 dark:border-blue-800/40 dark:text-blue-400",
    icon: Activity,
    desc: "Lab findings (FIT, Mammography, Pap/HPV) are ingested instantly. The explainable risk engine calculates drop-off risk and assigns dynamic SLA deadlines.",
  },
  {
    step: "02",
    title: "Multilingual Patient Outreach",
    badge: "Comprehension Verification",
    color: "from-emerald-500/10 to-teal-500/10 text-emerald-600 border-emerald-200 dark:border-emerald-800/40 dark:text-emerald-400",
    icon: Users,
    desc: "Patients receive reassuring follow-up guidance in English, Hindi, or Spanish. A 1-click acknowledgement and teach-back verify understanding, auto-escalating if confused.",
  },
  {
    step: "03",
    title: "Specialist Referral & SBAR Hand-Off",
    badge: "Cross-Provider Loop",
    color: "from-cyan-500/10 to-blue-500/10 text-cyan-600 border-cyan-200 dark:border-cyan-800/40 dark:text-cyan-400",
    icon: MessageSquare,
    desc: "Clinicians coordinate care with structured SBAR notes. If a referral is rejected due to capacity or insurance, the case is immediately re-queued for navigator rebooking.",
  },
  {
    step: "04",
    title: "Evidence-Guarded Closure",
    badge: "Zero Unconfirmed Cases",
    color: "from-amber-500/10 to-orange-500/10 text-amber-600 border-amber-200 dark:border-amber-800/40 dark:text-amber-400",
    icon: ShieldCheck,
    desc: "No case can be closed on assumptions. The system enforces verifiable medical evidence (pathology reports, confirmatory procedures) or authorized clinician rationale.",
  },
];

export function HowItWorks() {
  return (
    <section aria-label="How CareLoop AI Works" className="mt-16">
      <div className="flex flex-col items-center text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50/70 px-3.5 py-1 text-xs font-semibold text-indigo-800 shadow-2xs dark:border-indigo-800/50 dark:bg-indigo-950/40 dark:text-indigo-300">
          <CheckCircle2 className="h-3.5 w-3.5" />
          <span>The 4-Stage Closed-Loop Care Pathway</span>
        </div>
        <h2 className="mt-3 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
          What is CareLoop AI & Exactly How It Works
        </h2>
        <p className="mt-2 max-w-2xl text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
          From the moment an abnormal screening is issued to final verified treatment,
          CareLoop AI actively coordinates patients, navigators, and clinicians so no critical finding is lost.
        </p>
      </div>

      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {WORKFLOW_STEPS.map((s, idx) => {
          const Icon = s.icon;
          return (
            <div
              key={s.step}
              className="group relative flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-5 shadow-2xs transition-all duration-300 hover:-translate-y-1 hover:shadow-md hover:border-blue-400/50 dark:bg-slate-900 dark:border-slate-800"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className={`flex h-10 w-10 items-center justify-center rounded-xl border bg-gradient-to-br ${s.color} shadow-2xs`}>
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="font-mono text-xs font-black text-slate-300 group-hover:text-blue-500 transition dark:text-slate-700">
                    {s.step}
                  </span>
                </div>

                <div className="mt-4">
                  <span className="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {s.badge}
                  </span>
                  <h3 className="mt-2 text-sm font-bold text-slate-900 group-hover:text-blue-700 transition dark:text-white dark:group-hover:text-blue-400">
                    {s.title}
                  </h3>
                  <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                    {s.desc}
                  </p>
                </div>
              </div>

              {idx < WORKFLOW_STEPS.length - 1 && (
                <div className="mt-4 hidden lg:flex items-center gap-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400">
                  <span>Next hand-off</span>
                  <ArrowRight className="h-3 w-3" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
