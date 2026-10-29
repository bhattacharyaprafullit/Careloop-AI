"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BrainCircuit,
  Clock,
  FastForward,
  RotateCcw,
  Sparkles,
  X,
  ChevronRight,
  ChevronLeft,
  CircleCheck,
  UserCheck,
  LoaderCircle,
} from "lucide-react";
import { ErrorBoundary } from "@/components/error-boundary";
import { useSandbox } from "@/hooks/use-sandbox";
import { GUIDED_TOUR_STEPS } from "@/lib/tour";
import type { Role } from "@/lib/types";

export { ErrorBoundary };

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { role, setRole, clockOffsetHours, wakingAttempt, advanceTime, resetDemo, tourStep, setTourStep } = useSandbox();
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const handleAdvance = async (hrs: number) => {
    setBusyAction(`adv-${hrs}`);
    try {
      const res = await advanceTime(hrs);
      setToastMsg(`Clock advanced +${hrs}h (total +${res.clock_offset_hours}h). Overdue cases: ${res.overdue_cases} (${res.newly_breached} new SLA breaches).`);
    } catch (err) {
      setToastMsg(err instanceof Error ? err.message : "Could not advance sandbox clock.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleReset = async () => {
    setBusyAction("reset");
    try {
      await resetDemo();
      setToastMsg("Demo sandbox reset to initial 60 synthetic seed cases.");
    } catch (err) {
      setToastMsg(err instanceof Error ? err.message : "Could not reset demo sandbox.");
    } finally {
      setBusyAction(null);
    }
  };

  const currentTour = tourStep !== null ? GUIDED_TOUR_STEPS.find((s) => s.step === tourStep) ?? null : null;
  const navItems = [
    { href: "/app/queue", label: "Priority Queue" },
    { href: "/app/approvals", label: "Approvals" },
    { href: "/app/clinician", label: "Clinician Desk" },
    { href: "/app/metrics", label: "Metrics" },
    { href: "/app/model-card", label: "Model Card" },
  ];

  return (
    <div className="min-h-screen bg-slate-50/60 text-slate-900 antialiased selection:bg-blue-600 selection:text-white">
      {wakingAttempt > 0 && (
        <div role="status" className="flex items-center justify-center gap-2 bg-gradient-to-r from-blue-900 via-indigo-900 to-blue-900 px-4 py-2 text-center text-xs font-semibold text-white shadow-inner">
          <LoaderCircle className="h-3.5 w-3.5 animate-spin text-blue-300" />
          <span>Waking backend service (attempt {wakingAttempt} of 3) — warm-up in progress...</span>
        </div>
      )}

      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/85 shadow-xs backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/" className="group flex items-center gap-2.5 transition">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-700 via-indigo-600 to-sky-500 text-white shadow-sm shadow-blue-500/25 ring-1 ring-black/5 group-hover:scale-105 transition-transform duration-200">
                <BrainCircuit className="h-5 w-5" />
              </span>
              <div className="flex flex-col">
                <span className="text-base font-extrabold tracking-tight text-slate-900 group-hover:text-blue-700 transition">CareLoop AI</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 -mt-1">Closed-Loop Care</span>
              </div>
            </Link>

            <nav aria-label="Main navigation" className="hidden lg:flex items-center gap-1">
              {navItems.map((it) => {
                const active = pathname === it.href;
                return (
                  <Link
                    key={it.href}
                    href={it.href}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold tracking-wide transition-all ${
                      active
                        ? "bg-blue-600 text-white shadow-xs"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                  >
                    {it.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1 shadow-2xs">
              <UserCheck className="h-3.5 w-3.5 text-slate-400" />
              <label htmlFor="role-select" className="text-[11px] font-semibold text-slate-500">Role:</label>
              <select
                id="role-select"
                aria-label="Active role switcher"
                data-testid="role-switcher"
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
                className="bg-transparent text-xs font-bold text-slate-800 focus:outline-hidden cursor-pointer"
              >
                <option value="coordinator">Coordinator</option>
                <option value="clinician">Clinician</option>
                <option value="patient">Patient</option>
              </select>
            </div>

            <span
              data-testid="clock-offset-badge"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-2xs"
            >
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              <span>+{clockOffsetHours}h</span>
            </span>

            <button
              type="button"
              data-testid="advance-time-btn"
              disabled={busyAction !== null}
              onClick={() => void handleAdvance(48)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs transition hover:bg-amber-700 active:scale-95 disabled:opacity-50"
            >
              {busyAction === "adv-48" ? (
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <FastForward className="h-3.5 w-3.5" />
              )}
              <span>{busyAction === "adv-48" ? "Advancing..." : "+48h"}</span>
            </button>

            <button
              type="button"
              data-testid="reset-demo-btn"
              disabled={busyAction !== null}
              onClick={() => void handleReset()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 hover:text-slate-900 active:scale-95 disabled:opacity-50"
            >
              {busyAction === "reset" ? (
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
              )}
              <span>Reset</span>
            </button>

            <button
              type="button"
              data-testid="start-tour-btn"
              onClick={() => setTourStep(1)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs transition hover:bg-blue-700 active:scale-95"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Guided Tour</span>
              <span className="rounded-full bg-blue-500/80 px-1.5 py-0.2 text-[10px] font-bold">8</span>
            </button>
          </div>
        </div>

        <nav aria-label="Mobile navigation" className="flex lg:hidden overflow-x-auto border-t border-slate-100 px-4 py-2 gap-1 scrollbar-none">
          {navItems.map((it) => {
            const active = pathname === it.href;
            return (
              <Link
                key={it.href}
                href={it.href}
                className={`whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                  active ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {it.label}
              </Link>
            );
          })}
        </nav>
      </header>

      {toastMsg && (
        <div
          role="status"
          data-testid="demo-toast"
          className="mx-auto mt-4 flex max-w-7xl items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50/90 px-4 py-2.5 text-xs font-medium text-blue-950 shadow-md backdrop-blur-xs animate-slide-in-left"
        >
          <div className="flex items-center gap-2">
            <CircleCheck className="h-4 w-4 shrink-0 text-blue-600" />
            <span>{toastMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => setToastMsg(null)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-slate-600 hover:bg-blue-100 hover:text-slate-900 transition"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {currentTour && (
        <aside
          role="dialog"
          aria-label="Guided tour"
          data-testid="guided-tour-banner"
          className="mx-auto mt-4 max-w-7xl rounded-2xl border-2 border-blue-600 bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 p-5 text-white shadow-xl animate-fade-up"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/30 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-200 ring-1 ring-blue-400/30">
                  <Sparkles className="h-3 w-3" /> Step {currentTour.step} of 8
                </span>
                <span className="text-xs text-slate-300">Self-guided verification walk</span>
              </div>
              <h3 className="mt-1.5 text-base font-bold text-white tracking-tight">{currentTour.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-200">{currentTour.body}</p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {currentTour.step > 1 && (
                <button
                  type="button"
                  onClick={() => {
                    const prev = GUIDED_TOUR_STEPS[currentTour.step - 2];
                    setTourStep(prev.step);
                    router.push(prev.route);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-white/20"
                >
                  <ChevronLeft className="h-3.5 w-3.5" /> Prev
                </button>
              )}
              {currentTour.step < 8 ? (
                <button
                  type="button"
                  data-testid="tour-next-btn"
                  onClick={() => {
                    const next = GUIDED_TOUR_STEPS[currentTour.step];
                    setTourStep(next.step);
                    router.push(next.route);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg bg-blue-500 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs transition hover:bg-blue-400 active:scale-95"
                >
                  Next <ChevronRight className="h-3.5 w-3.5" />
                </button>
              ) : (
                <button
                  type="button"
                  data-testid="tour-finish-btn"
                  onClick={() => setTourStep(null)}
                  className="inline-flex items-center gap-1 rounded-lg bg-emerald-500 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs transition hover:bg-emerald-400 active:scale-95"
                >
                  Finish Tour <CircleCheck className="h-3.5 w-3.5" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setTourStep(null)}
                aria-label="Close tour"
                className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </aside>
      )}

      <ErrorBoundary>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
      </ErrorBoundary>
    </div>
  );
}
