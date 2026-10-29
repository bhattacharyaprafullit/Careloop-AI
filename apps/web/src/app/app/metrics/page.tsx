"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppShell } from "@/components/app-shell";
import { useSandbox } from "@/hooks/use-sandbox";
import { apiFetch } from "@/lib/api";
import type { MetricsSummary } from "@/lib/types";

export default function MetricsPage() {
  const { refreshKey } = useSandbox();
  const { data, isLoading, error } = useQuery<MetricsSummary>({
    queryKey: ["metrics-summary", refreshKey],
    queryFn: () => apiFetch<MetricsSummary>("/api/v1/metrics/summary"),
  });

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-4">
          <div className="h-28 animate-pulse rounded-2xl bg-slate-200/70" />
          <div className="h-64 animate-pulse rounded-2xl bg-slate-200/70" />
        </div>
      </AppShell>
    );
  }

  if (error || !data) {
    return (
      <AppShell>
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-xs font-semibold text-rose-800">
          Metrics unavailable: {error instanceof Error ? error.message : "Failed to load"}
        </div>
      </AppShell>
    );
  }

  const transitionRows = Object.entries(data.intervals).map(([key, val]) => ({
    stage: key.replace("time_to_", ""),
    median_hours: val.median_hours ?? 0,
    p90_hours: val.p90_hours ?? 0,
  }));
  const stateRows = Object.entries(data.state_counts).map(([state, count]) => ({ state, count }));
  const agingRows = [
    { bucket: "0-30d", count: data.unresolved.aging.d0_30 },
    { bucket: "31-60d", count: data.unresolved.aging.d31_60 },
    { bucket: "61-90d", count: data.unresolved.aging.d61_90 },
    { bucket: "90+d", count: data.unresolved.aging.d90_plus },
  ];
  const delayRows = data.delay_reasons.map((d) => ({ reason: d.code, count: d.count }));
  const totalTeachback = data.teachback.understood + data.teachback.partial + data.teachback.confused;
  const understandingRate = totalTeachback > 0 ? data.teachback.understood / totalTeachback : 0;

  const simRows = [
    {
      policy: "FIFO Outreach",
      median_days: data.simulation.fifo.median_days,
      unresolved_pct: Number((data.simulation.fifo.unresolved_day60 * 100).toFixed(1)),
    },
    {
      policy: "CareLoop Priority",
      median_days: data.simulation.careloop.median_days,
      unresolved_pct: Number((data.simulation.careloop.unresolved_day60 * 100).toFixed(1)),
    },
  ];

  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-black tracking-tight text-slate-900">
          Loop-Closure & Impact Metrics (R6)
        </h1>
        <p className="mt-1 text-xs text-slate-500 max-w-2xl">
          Real-time metrics computed strictly from the append-only event ledger, plus a 100-run
          Monte Carlo simulation validating CareLoop prioritization over legacy FIFO outreach.
        </p>
      </div>

      {/* Top KPI Cards */}
      <div data-testid="metrics-kpi-grid" className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-2xl border border-emerald-200/80 bg-emerald-50/50 p-4 shadow-2xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-800">Documented Closure</div>
          <div data-testid="kpi-documented-closure" className="mt-1.5 text-2xl font-black text-emerald-950">
            {(data.documented_closure_rate * 100).toFixed(1)}%
          </div>
        </div>

        <div className="rounded-2xl border border-blue-200/80 bg-blue-50/50 p-4 shadow-2xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-blue-800">Acknowledgement</div>
          <div className="mt-1.5 text-2xl font-black text-blue-950">
            {(data.acknowledgement_rate * 100).toFixed(1)}%
          </div>
        </div>

        <div className="rounded-2xl border border-indigo-200/80 bg-indigo-50/50 p-4 shadow-2xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-indigo-800">Teach-Back Understood</div>
          <div data-testid="kpi-patient-understanding" className="mt-1.5 text-2xl font-black text-indigo-950">
            {(understandingRate * 100).toFixed(1)}%
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-600">Referral Completed</div>
          <div className="mt-1.5 text-2xl font-black text-slate-900">
            {(data.referral_completion_rate * 100).toFixed(1)}%
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-600">Appt Completed</div>
          <div className="mt-1.5 text-2xl font-black text-slate-900">
            {(data.appointment_completion_rate * 100).toFixed(1)}%
          </div>
        </div>

        <div className="rounded-2xl border border-amber-200/80 bg-amber-50/50 p-4 shadow-2xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-amber-800">Unresolved Open</div>
          <div data-testid="kpi-unresolved-total" className="mt-1.5 text-2xl font-black text-amber-950">
            {data.unresolved.total}
          </div>
        </div>
      </div>

      {/* Stage Transition Medians & State Distribution */}
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Median & P90 Hours by Milestone Transition (R6)
          </h2>
          <div className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={transitionRows} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="stage" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="median_hours" name="Median Hours" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="p90_hours" name="P90 Hours" fill="#93c5fd" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Current Case Distribution Across 11 States
          </h2>
          <div className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stateRows} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="state" tick={{ fontSize: 8, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0" }} />
                <Bar dataKey="count" name="Cases" fill="#0d9488" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* Unresolved Aging & Delay Reasons */}
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Unresolved Results by Aging Bucket
          </h2>
          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agingRows} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0" }} />
                <Bar dataKey="count" name="Open Cases" fill="#d97706" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Documented Delay & Rejection Reasons
          </h2>
          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={delayRows} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="reason" tick={{ fontSize: 9, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0" }} />
                <Bar dataKey="count" name="Occurrences" fill="#e11d48" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* Labeled Simulation: FIFO vs CareLoop */}
      <section data-testid="simulation-panel" className="mt-6 rounded-2xl border-2 border-blue-600 bg-white p-6 shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <span className="rounded-full bg-amber-100 px-3 py-0.5 text-xs font-bold text-amber-900">
              {data.simulation.label ?? "Simulated comparison (synthetic cohort)"}
            </span>
            <h2 className="mt-2 text-lg font-black text-slate-900">
              FIFO Outreach vs. CareLoop Priority Queue ({data.simulation.runs} Monte Carlo Runs)
            </h2>
          </div>
        </div>

        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={simRows} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="policy" tick={{ fontSize: 11, fill: "#334155", fontWeight: 600 }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="median_days" name="Median Days to Closure" fill="#2563eb" radius={[6, 6, 0, 0]} />
                <Bar dataKey="unresolved_pct" name="Unresolved at Day 60 (%)" fill="#ef4444" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-3 text-xs leading-relaxed">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="font-black text-slate-900">Standard FIFO Outreach</div>
              <div className="mt-1 text-slate-600">
                Median Days: <strong>{data.simulation.fifo.median_days} days</strong> (95% CI [
                {data.simulation.ci95.fifo_median_days[0]}, {data.simulation.ci95.fifo_median_days[1]}])
              </div>
              <div className="text-slate-600">
                Unresolved at Day 60: <strong className="text-rose-700">{(data.simulation.fifo.unresolved_day60 * 100).toFixed(1)}%</strong>
              </div>
            </div>

            <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-4">
              <div className="font-black text-blue-950">CareLoop Multi-Factor Priority Queue</div>
              <div className="mt-1 text-blue-900">
                Median Days: <strong>{data.simulation.careloop.median_days} days</strong> (95% CI [
                {data.simulation.ci95.careloop_median_days[0]}, {data.simulation.ci95.careloop_median_days[1]}])
              </div>
              <div className="text-blue-900">
                Unresolved at Day 60: <strong className="text-emerald-700">{(data.simulation.careloop.unresolved_day60 * 100).toFixed(1)}%</strong>
              </div>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
