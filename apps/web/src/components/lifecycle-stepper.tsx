import React from "react";
import { Check } from "lucide-react";
import { ALL_CASE_STATES, type TimelineEntry, type CaseState } from "@/lib/types";

export function LifecycleStepper({
  currentState,
  timeline,
}: {
  currentState: CaseState;
  timeline: TimelineEntry[];
}) {
  return (
    <section
      aria-label="11-state lifecycle stepper"
      data-testid="lifecycle-stepper"
      className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs"
    >
      <h2 className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
        End-to-End 11-State Screening-to-Care Lifecycle (R1)
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-11">
        {ALL_CASE_STATES.map((st, i) => {
          const isCurrent = currentState === st;
          const visited = timeline.some((ev) => ev.to_state === st);
          return (
            <div
              key={st}
              data-testid={`stepper-state-${st}`}
              className={`flex flex-col items-center justify-center rounded-xl border p-2 text-center text-[10px] font-bold transition-all ${
                isCurrent
                  ? "border-blue-600 bg-blue-600 text-white shadow-xs ring-2 ring-blue-400/40"
                  : visited
                  ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                  : "border-slate-200 bg-slate-50/60 text-slate-600"
              }`}
            >
              <div className="flex items-center gap-1">
                <span>{i + 1}.</span>
                {visited && !isCurrent && <Check className="h-3 w-3 text-emerald-600" />}
              </div>
              <span className="mt-0.5 leading-tight">{st}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
