/**
 * Typed API client. M0: base URL only.
 * M10 adds X-Sandbox-Token / X-Role headers, error-envelope parsing and wake-up retries.
 */
export const API_URL: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7860";
