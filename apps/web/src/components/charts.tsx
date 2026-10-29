"use client";

import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CurvePoint, ShapDriverItem } from "@/lib/types";

/**
 * SHAP Waterfall chart using a Recharts stacked BarChart with a transparent first segment (base)
 * and colored delta segment, reported strictly in log-odds units (spec requirement).
 */
export function ShapWaterfallChart({
  topPositive,
  topNegative,
}: {
  topPositive: ShapDriverItem[];
  topNegative: ShapDriverItem[];
}) {
  const combined = [...topPositive, ...topNegative];
  let cumulative = 0;
  const rows = combined.map((d) => {
    const start = cumulative;
    const end = cumulative + d.value;
    cumulative = end;
    const base = Math.min(start, end);
    const span = Math.abs(d.value);
    return {
      name: d.feature,
      label: d.label,
      base: Number(base.toFixed(4)),
      span: Number(span.toFixed(4)),
      signed: d.value,
      positive: d.value >= 0,
    };
  });

  return (
    <div
      data-testid="shap-waterfall"
      className="h-72 w-full rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs"
    >
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-bold text-slate-800">
          SHAP Feature Contributions
        </p>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
          log-odds of drop-off (+ risk, − safe)
        </span>
      </div>
      <ResponsiveContainer width="100%" height="86%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} />
          <YAxis
            type="category"
            dataKey="name"
            width={130}
            tick={{ fontSize: 11, fill: "#334155", fontWeight: 600 }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "rgba(255, 255, 255, 0.95)",
              borderRadius: "12px",
              boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
              border: "1px solid #e2e8f0",
              fontSize: "12px",
            }}
            formatter={(_val, _name, props) => {
              const p = props.payload as { signed: number; label: string };
              return [`${p.signed > 0 ? "+" : ""}${p.signed} log-odds`, p.label];
            }}
          />
          <Bar dataKey="base" stackId="waterfall" fill="transparent" />
          <Bar dataKey="span" stackId="waterfall" radius={[4, 4, 4, 4]}>
            {rows.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.positive ? "#e11d48" : "#2563eb"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Survival curve S(t) = P(case remains open at day t) vs cohort Kaplan-Meier step line.
 * Hazard here means completion rate (higher hazard = faster closure / steeper drop in S(t)).
 */
export function SurvivalComparisonChart({
  survivalCurve,
  kmCurve,
}: {
  survivalCurve: CurvePoint[];
  kmCurve: CurvePoint[];
}) {
  const kmByDay = new Map(kmCurve.map((p) => [p.day, p.s]));
  const merged = survivalCurve.map((pt) => ({
    day: pt.day,
    case_open_prob: pt.s,
    cohort_km_open_prob: kmByDay.get(pt.day) ?? pt.s,
  }));

  return (
    <div
      data-testid="survival-chart"
      className="h-72 w-full rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs"
    >
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-bold text-slate-800">
          Time-to-Closure S(t) vs. Cohort Kaplan-Meier
        </p>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
          Steeper slope = faster resolution
        </span>
      </div>
      <ResponsiveContainer width="100%" height="86%">
        <LineChart
          data={merged}
          margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 11, fill: "#64748b" }}
            label={{
              value: "Days from abnormal result",
              position: "insideBottom",
              offset: -4,
              fontSize: 10,
              fill: "#94a3b8",
            }}
          />
          <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "#64748b" }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "rgba(255, 255, 255, 0.95)",
              borderRadius: "12px",
              boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
              border: "1px solid #e2e8f0",
              fontSize: "12px",
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11, paddingTop: "8px" }} />
          <Line
            type="stepAfter"
            dataKey="case_open_prob"
            name="Patient S(t) P(Open)"
            stroke="#d97706"
            strokeWidth={2.5}
            dot={false}
          />
          <Line
            type="stepAfter"
            dataKey="cohort_km_open_prob"
            name="Cohort Kaplan-Meier"
            stroke="#2563eb"
            strokeWidth={2}
            strokeDasharray="4 4"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
