"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Plus,
  X,
  Clock,
  TriangleAlert,
  ArrowUpRight,
  Filter,
  CheckCircle2,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { IngestScreeningForm } from "@/components/ingest-screening-form";
import { useSandbox } from "@/hooks/use-sandbox";
import { apiFetch } from "@/lib/api";
import { STATE_META, TONE_BADGE, TONE_DOT, pct } from "@/lib/utils";
import type { PriorityQueueItem, PriorityQueueResponse } from "@/lib/types";

type QueueTab = "all" | "overdue" | "unassigned" | "rejected" | "needs_approval";

export default function QueuePage() {
  const { refreshKey, triggerRefresh } = useSandbox();
  const [activeTab, setActiveTab] = useState<QueueTab>("all");
  const [showIngest, setShowIngest] = useState(false);

  const queryString = (() => {
    if (activeTab === "overdue") return "?overdue=true&page_size=50";
    if (activeTab === "unassigned") return "?unassigned=true&page_size=50";
    if (activeTab === "rejected") return "?rejected=true&page_size=50";
    if (activeTab === "needs_approval") return "?needs_approval=true&page_size=50";
    return "?page_size=50";
  })();

  const { data, isLoading, error } = useQuery<PriorityQueueResponse>({
    queryKey: ["priority-queue", activeTab, refreshKey],
    queryFn: () => apiFetch<PriorityQueueResponse>(`/api/v1/cases/priority-queue${queryString}`),
  });

  const cases: PriorityQueueItem[] = data?.items ?? [];

  const tabs: { id: QueueTab; label: string }[] = [
    { id: "all", label: "All Cases" },
    { id: "overdue", label: "Overdue" },
    { id: "unassigned", label: "Unassigned" },
    { id: "rejected", label: "Rejected" },
    { id: "needs_approval", label: "Needs approval" },
  ];

  return (
    <AppShell>
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight text-slate-900">Coordinator Priority Queue</h1>
            <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-bold text-blue-800">
              {cases.length} active
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500 max-w-2xl">
            Ranked by multi-factor clinical priority: urgency tier (45%), calibrated drop-off risk (35%),
            and SLA breach pressure (20%).
          </p>
        </div>

        <button
          type="button"
          data-testid="toggle-ingest-btn"
          onClick={() => setShowIngest((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs transition hover:bg-blue-700 active:scale-95"
        >
          {showIngest ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          <span>{showIngest ? "Close Ingest" : "New Screening Result"}</span>
        </button>
      </div>

      {/* Ingest Form Drawer */}
      {showIngest && (
        <IngestScreeningForm
          onSuccess={() => {
            setShowIngest(false);
            triggerRefresh();
          }}
          onCancel={() => setShowIngest(false)}
        />
      )}

      {/* Tabs Filter Bar */}
      <div role="tablist" aria-label="Queue filters" className="mt-6 flex flex-wrap items-center gap-1.5 border-b border-slate-200 pb-3">
        <span className="mr-1 text-slate-400">
          <Filter className="h-4 w-4" />
        </span>
        {tabs.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={active}
              data-testid={`tab-${t.id}`}
              type="button"
              onClick={() => setActiveTab(t.id)}
              className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all ${
                active
                  ? "bg-slate-900 text-white shadow-xs"
                  : "bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-slate-200/80"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Table & Loading States */}
      {isLoading ? (
        <div className="mt-4 space-y-2.5" aria-label="Loading queue">
          {[1, 2, 3, 4, 5].map((n) => (
            <div key={n} className="h-16 animate-pulse rounded-2xl bg-slate-200/70" />
          ))}
        </div>
      ) : error ? (
        <div role="alert" className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800">
          Failed to load priority queue: {error instanceof Error ? error.message : "Unknown error"}
        </div>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="border-b border-slate-100 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3">Patient / Case ID</th>
                  <th className="px-4 py-3">Screening</th>
                  <th className="px-4 py-3">Lifecycle State</th>
                  <th className="px-4 py-3">Owner</th>
                  <th className="px-4 py-3">SLA Status</th>
                  <th className="px-4 py-3">Drop-Off Risk</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {cases.map((c) => {
                  const remHrs = c.hours_remaining;
                  const stateMeta = STATE_META[c.state] ?? { label: c.state, tone: "slate" as const };
                  return (
                    <tr
                      key={c.case_id}
                      data-testid={`case-row-${c.case_id}`}
                      className="transition hover:bg-blue-50/30"
                    >
                      <td className="px-4 py-3">
                        <div className="font-bold text-slate-900">{c.patient_alias}</div>
                        <div className="font-mono text-[10px] text-slate-600">{c.case_id}</div>
                      </td>

                      <td className="px-4 py-3">
                        <span className="font-bold text-slate-900">{c.screening_type}</span>
                        <div className="text-[10px] text-slate-600">
                          Tier {c.urgency_tier} {c.urgency_tier === 1 && "• Urgent"}
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${TONE_BADGE[stateMeta.tone]}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${TONE_DOT[stateMeta.tone]}`} />
                            {c.state}
                          </span>
                          {c.escalated && (
                            <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-bold text-purple-800">
                              ESCALATED
                            </span>
                          )}
                          {c.needs_approval && (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                              NEEDS APPROVAL
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        {c.owner_id ? (
                          <div className="text-slate-800">
                            <span className="font-bold capitalize">{c.owner_role}:</span>{" "}
                            <span className="font-mono text-[11px]">{c.owner_id}</span>
                          </div>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-900">
                            <TriangleAlert className="h-3 w-3" />
                            UNASSIGNED ({c.owner_role ?? "none"})
                          </span>
                        )}
                      </td>

                      <td className="px-4 py-3">
                        {c.state === "CLOSED" ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700">
                            <CheckCircle2 className="h-3.5 w-3.5" /> Closed
                          </span>
                        ) : c.overdue ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-800">
                            <Clock className="h-3 w-3 animate-pulse text-rose-600" />
                            OVERDUE ({remHrs?.toFixed(1)}h)
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-700">
                            <Clock className="h-3 w-3 text-slate-400" />
                            {remHrs !== null ? `${remHrs.toFixed(1)}h left` : "Active"}
                          </span>
                        )}
                      </td>

                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900">{pct(c.p_dropoff)}</span>
                          <div className="h-1.5 w-12 rounded-full bg-slate-100 overflow-hidden">
                            <div
                              className={`h-full ${c.p_dropoff > 0.4 ? "bg-rose-500" : c.p_dropoff > 0.2 ? "bg-amber-500" : "bg-emerald-500"}`}
                              style={{ width: `${Math.min(100, c.p_dropoff * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        <span className="rounded-lg bg-blue-50 px-2.5 py-1 font-mono text-xs font-black text-blue-700 border border-blue-200/60">
                          {c.priority.toFixed(1)}
                        </span>
                      </td>

                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/app/cases/${c.case_id}`}
                          data-testid={`open-case-${c.case_id}`}
                          className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-bold text-white shadow-2xs transition hover:bg-blue-600 active:scale-95"
                        >
                          <span>Open</span>
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}

                {cases.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-xs text-slate-400">
                      No cases match the &ldquo;{activeTab}&rdquo; filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </AppShell>
  );
}
