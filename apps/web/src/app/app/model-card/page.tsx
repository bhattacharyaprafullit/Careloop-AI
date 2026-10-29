"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  ShieldCheck,
  BrainCircuit,
  Activity,
  Layers,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { ModelCardMetrics } from "@/lib/types";

export default function ModelCardPage() {
  const { data, isLoading, error } = useQuery<ModelCardMetrics>({
    queryKey: ["model-card"],
    queryFn: () => apiFetch<ModelCardMetrics>("/api/v1/metrics/model-card"),
  });

  if (isLoading) {
    return (
      <AppShell>
        <div className="h-64 animate-pulse rounded-2xl bg-slate-200/70" />
      </AppShell>
    );
  }

  if (error || !data) {
    return (
      <AppShell>
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-xs font-semibold text-rose-800">
          Model card could not be loaded: {error instanceof Error ? error.message : "Unknown error"}
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
                <FileText className="h-5 w-5" />
              </span>
              <div>
                <h1 className="text-2xl font-black tracking-tight text-slate-900">
                  Model Card & Evaluation Audits
                </h1>
                <p className="text-xs text-slate-500">
                  Transparency report for drop-off prediction, survival models, and LLM safety filters.
                </p>
              </div>
            </div>

            <span
              data-testid="model-version-badge"
              className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3.5 py-1 text-xs font-bold text-white shadow-2xs"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Version: {data.model_version ?? "v1.0.0"}</span>
            </span>
          </div>

          <p className="mt-4 text-xs leading-relaxed text-slate-600">
            {data.synthetic_disclaimer}
          </p>
        </div>

        {/* Model Metrics Grid */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Classifier Card */}
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <BrainCircuit className="h-4 w-4 text-blue-600" />
              <h2 className="text-sm font-bold text-slate-900">
                1. Stage Drop-Off Classifier (XGBoost + Platt Calibration)
              </h2>
            </div>

            <dl className="mt-3.5 space-y-2.5 text-xs text-slate-800">
              <div className="flex justify-between border-b border-slate-50 pb-2">
                <dt className="text-slate-600 font-medium">Test ROC-AUC:</dt>
                <dd data-testid="model-roc-auc" className="font-mono font-bold text-slate-900">
                  {data.classification.roc_auc}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-50 pb-2">
                <dt className="text-slate-600 font-medium">Test PR-AUC:</dt>
                <dd className="font-mono font-bold text-slate-900">{data.classification.pr_auc}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-50 pb-2">
                <dt className="text-slate-600 font-medium">Test Brier Score (Cal / Uncal):</dt>
                <dd className="font-mono font-bold text-slate-900">
                  {data.classification.brier_calibrated} / {data.classification.brier_uncalibrated}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-50 pb-2">
                <dt className="text-slate-600 font-medium">Expected Calibration Error (ECE):</dt>
                <dd className="font-mono font-bold text-slate-900">{data.classification.ece_calibrated}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-600 font-medium">Total Model Artifacts:</dt>
                <dd className="font-mono font-bold text-slate-900">{data.artifacts_total_mb} MB (&le; 25 MB)</dd>
              </div>
            </dl>

            {data.classification.diagnostic_note && (
              <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/60 p-3 text-[11px] leading-relaxed text-blue-950">
                <strong>Honest Diagnostic Note:</strong> {data.classification.diagnostic_note}
              </div>
            )}
          </section>

          {/* Survival Card */}
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Activity className="h-4 w-4 text-indigo-600" />
              <h2 className="text-sm font-bold text-slate-900">
                2. Time-to-Closure Survival ({data.survival.model_type})
              </h2>
            </div>

            <dl className="mt-3.5 space-y-2.5 text-xs text-slate-800">
              <div className="flex justify-between border-b border-slate-50 pb-2">
                <dt className="text-slate-600 font-medium">PH Assumption Violated:</dt>
                <dd className="font-mono font-bold text-slate-900">{String(data.survival.ph_violated)}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-50 pb-2">
                <dt className="text-slate-600 font-medium">Test Concordance Index:</dt>
                <dd className="font-mono font-bold text-slate-900">{data.survival.concordance_index}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-600 font-medium">Patient Split (Train / Cal / Test):</dt>
                <dd className="font-mono font-bold text-slate-900">
                  {data.splits.train_patients} / {data.splits.calibration_patients} / {data.splits.test_patients}
                </dd>
              </div>
            </dl>

            <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50/70 p-3 text-[11px] leading-relaxed text-slate-600">
              <strong>Survival Formulation:</strong> S(t) = P(case remains open at day t).
              Higher completion hazard = faster closure. When proportional hazards are violated (p &lt; 0.01),
              the training pipeline automatically falls back to WeibullAFTFitter.
            </div>
          </section>
        </div>

        {/* Audits: Fairness, SHAP Stability & LLM Faithfulness */}
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-600" />
              <h2 className="text-sm font-bold text-slate-900">
                3. Subgroup Fairness, SHAP Stability & Faithfulness Audits
              </h2>
            </div>
            <span className="text-[10px] font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
              Automated M5 & M6 Checks
            </span>
          </div>

          <pre className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-4 font-mono text-[11px] leading-relaxed text-slate-200 shadow-inner">
            {JSON.stringify(
              {
                fairness: data.fairness,
                shap_stability: data.shap?.stability,
                llm_faithfulness: data.llm_faithfulness,
              },
              null,
              2
            )}
          </pre>
        </section>

        {/* Disclosures & Notice */}
        <aside className="rounded-2xl border border-amber-300/80 bg-amber-50/60 p-5 text-xs text-amber-950 shadow-2xs">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-amber-700 shrink-0" />
            <h2 className="font-bold text-amber-900">Intended Use, Limitations & Regulatory Disclosures</h2>
          </div>
          <ul className="mt-2.5 list-disc space-y-1 pl-5 leading-relaxed text-amber-900">
            <li>
              <strong>Intended use:</strong> Care-coordination priority ranking and explainable outreach timing on synthetic records.
            </li>
            <li>
              <strong>Out of scope:</strong> Diagnostic findings, drug prescriptions, or automated case closure without human authorization.
            </li>
            <li>
              <strong>Synthetic data boundary:</strong> Evaluated on a parametric synthetic dataset. Clinical effectiveness requires prospective multi-site validation.
            </li>
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}
