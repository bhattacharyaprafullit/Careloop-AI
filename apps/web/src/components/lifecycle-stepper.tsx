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
      <div className="mt-3 overflow-x-auto pb-1">
        <div className="grid min-w-[860px] grid-cols-11 gap-2">
          {ALL_CASE_STATES.map((st, i) => {
            const isCurrent = currentState === st;
            const visited = timeline.some((ev) => ev.to_state === st);
            const parts = st.split("_");
            return (
              <div
                key={st}
                data-testid={`stepper-state-${st}`}
                className={`flex min-h-[58px] flex-col items-center justify-center rounded-xl border px-1.5 py-2 text-center transition-all ${
                  isCurrent
                    ? "border-blue-600 bg-blue-600 text-white shadow-xs ring-2 ring-blue-400/40"
                    : visited
                    ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                    : "border-slate-200 bg-slate-50/60 text-slate-600"
                }`}
              >
                <div className="flex items-center gap-1 text-[10px] font-bold">
                  <span>{i + 1}.</span>
                  {visited && !isCurrent && <Check className="h-3 w-3 text-emerald-600" />}
                </div>
                <span className="mt-1 block max-w-full text-center text-[9px] font-bold leading-[1.15] tracking-tight">
                  {parts.map((part, idx) => (
                    <React.Fragment key={idx}>
                      <span>{part}</span>
                      {idx < parts.length - 1 && <span className="opacity-40">_</span>}
                      {idx < parts.length - 1 && <wbr />}
                    </React.Fragment>
                  ))}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
