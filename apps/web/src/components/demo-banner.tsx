/** Global, always-visible disclaimer required on every page (spec rule 7). */
export function DemoBanner() {
  return (
    <div
      role="note"
      aria-label="Demo disclaimer"
      className="w-full bg-amber-100 px-4 py-2 text-center text-sm font-semibold text-amber-950"
    >
      Demo only, synthetic data. Decision support only — no diagnosis, no prescribing.
    </div>
  );
}
