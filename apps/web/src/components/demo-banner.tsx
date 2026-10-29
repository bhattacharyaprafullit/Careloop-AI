import { ShieldAlert } from "lucide-react";

/** Global, always-visible disclaimer required on every page (spec rule 7). */
export function DemoBanner() {
  return (
    <aside
      role="note"
      aria-label="Demo disclaimer"
      className="relative z-50 flex items-center justify-center gap-2.5 border-b border-amber-500/20 bg-gradient-to-r from-amber-500/10 via-amber-500/15 to-amber-500/10 px-4 py-2 text-center text-xs font-medium tracking-wide text-amber-900 shadow-xs backdrop-blur-xs transition-colors dark:from-amber-950/40 dark:via-amber-900/30 dark:to-amber-950/40 dark:text-amber-200"
    >
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
      </span>
      <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-400" />
      <span>
        <strong className="font-semibold">Demo only, synthetic data.</strong>{" "}
        Decision support only — no diagnosis, no prescribing.
      </span>
    </aside>
  );
}
