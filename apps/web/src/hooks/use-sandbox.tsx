"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  apiFetch,
  getStoredToken,
  getStoredRole,
  setStoredRole,
  subscribeWakingState,
} from "@/lib/api";
import type { Role } from "@/lib/types";

interface SandboxContextValue {
  role: Role;
  setRole: (r: Role) => void;
  clockOffsetHours: number;
  wakingAttempt: number;
  advanceTime: (hours: number) => Promise<{
    clock_offset_hours: number;
    overdue_cases: number;
    newly_breached: number;
  }>;
  resetDemo: () => Promise<void>;
  refreshKey: number;
  triggerRefresh: () => void;
  tourStep: number | null;
  setTourStep: (step: number | null) => void;
}

const SandboxContext = createContext<SandboxContextValue | null>(null);

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );
  const [role, setRoleState] = useState<Role>("coordinator");
  const [clockOffsetHours, setClockOffsetHours] = useState<number>(0);
  const [wakingAttempt, setWakingAttempt] = useState<number>(0);
  const [refreshKey, setRefreshKey] = useState<number>(0);
  const [tourStep, setTourStep] = useState<number | null>(null);

  useEffect(() => {
    setRoleState(getStoredRole());
    // Only prefetch in the background when the main thread is idle and a token already exists
    const existingToken = getStoredToken();
    if (existingToken && typeof window !== "undefined") {
      const scheduleIdle = window.requestIdleCallback || ((cb: () => void) => setTimeout(cb, 1200));
      scheduleIdle(() => {
        void queryClient.prefetchQuery({
          queryKey: ["priority-queue", "all", 0],
          queryFn: () => apiFetch("/api/v1/cases/priority-queue?page_size=50"),
        });
      });
    }
    return subscribeWakingState((waking, attempt) => {
      setWakingAttempt(waking ? attempt : 0);
    });
  }, [queryClient]);

  const setRole = useCallback((next: Role) => {
    setStoredRole(next);
    setRoleState(next);
    setRefreshKey((k) => k + 1);
  }, []);

  const triggerRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    void queryClient.invalidateQueries();
  }, [queryClient]);

  const advanceTime = useCallback(
    async (hours: number) => {
      const res = await apiFetch<{
        clock_offset_hours: number;
        overdue_cases: number;
        newly_breached: number;
      }>("/api/v1/demo/advance-time", {
        method: "POST",
        body: JSON.stringify({ hours }),
      });
      setClockOffsetHours(res.clock_offset_hours);
      setRefreshKey((k) => k + 1);
      void queryClient.invalidateQueries();
      return res;
    },
    [queryClient]
  );

  const resetDemo = useCallback(async () => {
    await apiFetch("/api/v1/demo/reset", { method: "POST" });
    setClockOffsetHours(0);
    setRefreshKey((k) => k + 1);
    void queryClient.invalidateQueries();
  }, [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      <SandboxContext.Provider
        value={{
          role,
          setRole,
          clockOffsetHours,
          wakingAttempt,
          advanceTime,
          resetDemo,
          refreshKey,
          triggerRefresh,
          tourStep,
          setTourStep,
        }}
      >
        {children}
      </SandboxContext.Provider>
    </QueryClientProvider>
  );
}

export function useSandbox(): SandboxContextValue {
  const ctx = useContext(SandboxContext);
  if (!ctx) {
    throw new Error("useSandbox must be used inside AppProviders");
  }
  return ctx;
}
