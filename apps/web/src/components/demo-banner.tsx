import React from "react";

/** Global, always-visible disclaimer required on every page (spec rule 7). */
export function DemoBanner() {
  return (
    <aside
      role="note"
      aria-label="Demo disclaimer"
      className="relative z-50 flex flex-wrap items-center justify-center gap-2 border-b border-amber-500/20 bg-gradient-to-r from-amber-50/90 via-orange-50/70 to-amber-50/90 px-4 py-1.5 text-center text-xs text-amber-950 shadow-2xs backdrop-blur-xs dark:from-amber-950/40 dark:via-orange-950/30 dark:to-amber-950/40 dark:text-amber-200"
    >
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-900 dark:bg-amber-400/20 dark:text-amber-200">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-600 animate-pulse" />
        Simulation Sandbox
      </span>
      <span className="font-normal text-amber-900/90 dark:text-amber-200/90">
        Powered by <strong className="font-semibold text-amber-950 dark:text-amber-100">Synthetic Clinical Data</strong> • Clinical Decision Support System (CDSS)
      </span>
    </aside>
  );
}
