/**
 * Typed fetch wrapper for CareLoop AI (M10).
 * Adds X-Sandbox-Token and X-Role, parses the error envelope, and retries 3 times
 * (2s, 5s, 10s) on cold-start / network failure while signaling a waking-backend banner.
 */
import type { Role, SandboxResponse } from "@/lib/types";

export const API_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7860";

const TOKEN_STORAGE_KEY = "careloop_sandbox_token";
const ROLE_STORAGE_KEY = "careloop_role";
const RETRY_DELAYS_MS = [800, 2000] as const;

type WakingListener = (waking: boolean, attempt: number) => void;
const wakingListeners = new Set<WakingListener>();

export function subscribeWakingState(fn: WakingListener): () => void {
  wakingListeners.add(fn);
  return () => {
    wakingListeners.delete(fn);
  };
}

function notifyWaking(waking: boolean, attempt: number): void {
  for (const fn of wakingListeners) {
    fn(waking, attempt);
  }
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly requestId: string;

  constructor(status: number, code: string, message: string, requestId = "-") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function getStoredRole(): Role {
  if (typeof window === "undefined") return "coordinator";
  const val = window.sessionStorage.getItem(ROLE_STORAGE_KEY);
  if (val === "clinician" || val === "patient" || val === "coordinator") {
    return val;
  }
  return "coordinator";
}

export function setStoredRole(role: Role): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(ROLE_STORAGE_KEY, role);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function createSandboxSession(): Promise<SandboxResponse> {
  const res = await apiFetch<SandboxResponse>("/api/v1/sandbox", {
    method: "POST",
    skipSandboxHeader: true,
  });
  setStoredToken(res.token);
  return res;
}

export async function ensureSandboxToken(): Promise<string> {
  const existing = getStoredToken();
  if (existing) return existing;
  const created = await createSandboxSession();
  return created.token;
}

interface FetchOptions extends RequestInit {
  skipSandboxHeader?: boolean;
  roleOverride?: "coordinator" | "clinician";
}

export async function apiFetch<T>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipSandboxHeader = false, roleOverride, ...init } = options;
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  if (!skipSandboxHeader) {
    const token = await ensureSandboxToken();
    const role = roleOverride ?? getStoredRole();
    const staffRole = role === "clinician" ? "clinician" : "coordinator";
    headers.set("X-Sandbox-Token", token);
    headers.set("X-Role", staffRole);
  }

  const url = path.startsWith("http") ? path : `${API_URL}${path}`;
  let lastError: unknown = null;

  for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt++) {
    try {
      const response = await fetch(url, { ...init, headers });

      if (
        (response.status === 502 ||
          response.status === 503 ||
          response.status === 504) &&
        attempt < RETRY_DELAYS_MS.length
      ) {
        notifyWaking(true, attempt + 1);
        await sleep(RETRY_DELAYS_MS[attempt]);
        continue;
      }

      notifyWaking(false, 0);

      if (response.status === 401 && !skipSandboxHeader && attempt === 0) {
        // Token expired or DB reset; transparently create a fresh sandbox once
        const created = await createSandboxSession();
        headers.set("X-Sandbox-Token", created.token);
        continue;
      }

      if (!response.ok) {
        let code = "api_error";
        let message = `Request failed (${response.status})`;
        let requestId = "-";
        try {
          const errJson = (await response.json()) as {
            error?: { code?: string; message?: string; request_id?: string };
          };
          if (errJson?.error) {
            code = errJson.error.code ?? code;
            message = errJson.error.message ?? message;
            requestId = errJson.error.request_id ?? requestId;
          }
        } catch {
          // Friendly fallback if non-JSON error returned
        }
        throw new ApiError(response.status, code, message, requestId);
      }

      return (await response.json()) as T;
    } catch (err) {
      if (err instanceof ApiError) {
        throw err;
      }
      lastError = err;
      if (attempt < RETRY_DELAYS_MS.length) {
        notifyWaking(true, attempt + 1);
        await sleep(RETRY_DELAYS_MS[attempt]);
      }
    }
  }

  notifyWaking(false, 0);
  throw new ApiError(
    503,
    "backend_unreachable",
    lastError instanceof Error
      ? `Backend is waking up or temporarily unreachable (${lastError.message}). Please click Retry.`
      : "Backend is temporarily unreachable. Please click Retry."
  );
}

/**
 * Direct SSE connection to backend (EventSource cannot send headers, so pass token in query).
 */
export function openCaseStream(
  caseId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError?: () => void
): () => void {
  const token = getStoredToken() ?? "";
  const url = `${API_URL}/api/v1/cases/${encodeURIComponent(
    caseId
  )}/stream?token=${encodeURIComponent(token)}`;
  const es = new EventSource(url);

  const handle = (evtName: string) => (ev: MessageEvent) => {
    try {
      const parsed = JSON.parse(String(ev.data)) as Record<string, unknown>;
      onEvent(evtName, parsed);
      if (evtName === "done") {
        es.close();
      }
    } catch {
      // ignore malformed frame
    }
  };

  es.addEventListener("status", handle("status"));
  es.addEventListener("token", handle("token"));
  es.addEventListener("done", handle("done"));
  es.onerror = () => {
    es.close();
    if (onError) onError();
  };

  return () => {
    es.close();
  };
}
