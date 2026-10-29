"use client";

import React from "react";
import { AlertCircle } from "lucide-react";

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; message: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error.message || "Unexpected rendering error." };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" className="mx-auto my-12 max-w-lg rounded-2xl border border-rose-200 bg-rose-50/80 p-6 text-slate-900 shadow-lg backdrop-blur-sm">
          <div className="flex items-center gap-3 text-rose-700">
            <AlertCircle className="h-6 w-6 shrink-0" />
            <h2 className="text-base font-bold">Temporary Issue — Safe Fallback</h2>
          </div>
          <p className="mt-2 text-sm text-rose-800 leading-relaxed">{this.state.message}</p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, message: "" })}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-rose-700 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-rose-800"
          >
            Retry View
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
