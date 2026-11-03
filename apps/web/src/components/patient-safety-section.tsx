"use client";

import React from "react";
import { Shield, Lock, EyeOff, FileCheck2, Database, KeyRound } from "lucide-react";

const SAFETY_PILLARS = [
  {
    icon: EyeOff,
    title: "Zero Real PHI Leakage",
    desc: "Built on 100% synthetic clinical cohorts. No real patient health information (PHI) is ever ingested, stored, or exposed, meeting HIPAA & GDPR privacy mandates.",
    badge: "Privacy by Design",
  },
  {
    icon: Lock,
    title: "Cryptographic Token Hashing",
    desc: "Patient portal access uses isolated, single-use access tokens hashed with SHA-256 before database storage. Plaintext keys are never persisted.",
    badge: "SHA-256 Protected",
  },
  {
    icon: FileCheck2,
    title: "Append-Only Immutable Ledger",
    desc: "Database-level triggers forbid UPDATE and DELETE operations on clinical events, maintaining an untamperable audit trail for medical compliance.",
    badge: "Tamper-Proof Audit",
  },
  {
    icon: KeyRound,
    title: "Role-Based Access Control (RBAC)",
    desc: "Strict clinical boundary separation between Coordinators and Clinicians. Critical transitions and case closures require authorized credentialed sign-off.",
    badge: "Strict RBAC",
  },
  {
    icon: Database,
    title: "Multi-Tenant Sandbox Siloing",
    desc: "Every evaluation environment operates in an isolated sandbox with automated TTL expiry and secure cryptographic purging upon session completion.",
    badge: "Siloed Tenancy",
  },
  {
    icon: Shield,
    title: "Grounded Non-Diagnostic Boundary",
    desc: "LLMs operate with strict regex fact validators banning medical prescribing or ungrounded claims, ensuring safe assistive decision support only.",
    badge: "Safety Guardrails",
  },
];

export function PatientSafetySection() {
  return (
    <section aria-label="Patient Data Safety & Privacy Governance" className="mt-16">
      <div className="flex flex-col items-center text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/70 px-3.5 py-1 text-xs font-semibold text-emerald-800 shadow-2xs dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-300">
          <Shield className="h-3.5 w-3.5" />
          <span>Patient Privacy & Clinical Data Governance</span>
        </div>
        <h2 className="mt-3 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
          How CareLoop AI Protects Patient Data & Ensures Safety
        </h2>
        <p className="mt-2 max-w-2xl text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
          Healthcare trust requires absolute data confidentiality. Here are the 6 architectural safeguards
          we engineered to guarantee patient privacy, role isolation, and regulatory compliance.
        </p>
      </div>

      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SAFETY_PILLARS.map((p) => {
          const Icon = p.icon;
          return (
            <div
              key={p.title}
              className="group relative flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-white p-5 shadow-2xs transition-all duration-300 hover:-translate-y-1 hover:shadow-md hover:border-emerald-400/50 dark:bg-slate-900 dark:border-slate-800"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-200 bg-emerald-500/10 text-emerald-600 shadow-2xs dark:border-emerald-800/40 dark:text-emerald-400">
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200/60 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800/50">
                    {p.badge}
                  </span>
                </div>

                <h3 className="mt-4 text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition dark:text-white dark:group-hover:text-emerald-400">
                  {p.title}
                </h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                  {p.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
