/** Shared UI helpers: class merging, formatting, and state presentation metadata. */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { CaseState } from "@/lib/types";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function humanize(code: string): string {
  const s = code.replace(/_/g, " ").toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export type Tone = "slate" | "sky" | "indigo" | "violet" | "rose" | "amber" | "teal" | "emerald";

export const TONE_BADGE: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  sky: "bg-sky-50 text-sky-700 ring-sky-200",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  violet: "bg-violet-50 text-violet-700 ring-violet-200",
  rose: "bg-rose-50 text-rose-700 ring-rose-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  teal: "bg-teal-50 text-teal-700 ring-teal-200",
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

export const TONE_DOT: Record<Tone, string> = {
  slate: "bg-slate-400",
  sky: "bg-sky-500",
  indigo: "bg-indigo-500",
  violet: "bg-violet-500",
  rose: "bg-rose-500",
  amber: "bg-amber-500",
  teal: "bg-teal-500",
  emerald: "bg-emerald-500",
};

interface StateMeta {
  label: string;
  phase: "Notify" | "Confirm" | "Refer" | "Care" | "Closed";
  tone: Tone;
}

export const STATE_META: Record<CaseState, StateMeta> = {
  RESULT_ISSUED: { label: "Result issued", phase: "Notify", tone: "sky" },
  PATIENT_NOTIFIED: { label: "Patient notified", phase: "Notify", tone: "sky" },
  ACKNOWLEDGED: { label: "Acknowledged", phase: "Notify", tone: "sky" },
  CONFIRMATORY_PENDING: { label: "Confirmatory test", phase: "Confirm", tone: "violet" },
  REFERRAL_SENT: { label: "Referral sent", phase: "Refer", tone: "indigo" },
  REJECTED: { label: "Referral rejected", phase: "Refer", tone: "rose" },
  REFERRAL_ACCEPTED: { label: "Referral accepted", phase: "Refer", tone: "indigo" },
  APPOINTMENT_BOOKED: { label: "Appointment booked", phase: "Care", tone: "amber" },
  SEEN: { label: "Patient attended", phase: "Care", tone: "teal" },
  TREATMENT_OR_SURVEILLANCE: { label: "Care plan active", phase: "Care", tone: "teal" },
  CLOSED: { label: "Loop closed", phase: "Closed", tone: "emerald" },
};

export function riskTone(p: number): Tone {
  if (p >= 0.65) return "rose";
  if (p >= 0.4) return "amber";
  return "emerald";
}

export const RISK_BAR: Record<Tone, string> = {
  slate: "from-slate-300 to-slate-400",
  sky: "from-sky-300 to-sky-500",
  indigo: "from-indigo-300 to-indigo-500",
  violet: "from-violet-300 to-violet-500",
  rose: "from-rose-400 to-rose-600",
  amber: "from-amber-300 to-amber-500",
  teal: "from-teal-300 to-teal-500",
  emerald: "from-emerald-300 to-emerald-500",
};
