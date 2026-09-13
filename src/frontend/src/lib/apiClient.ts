/**
 * Thin API client.  All fetch calls go through here so base URL and error
 * handling are centralised in one place.
 */
import type { ErrorEnvelope, OkEnvelope } from "../types/api";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<OkEnvelope<T>> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  const json = await response.json();

  if (!response.ok) {
    const envelope = json as ErrorEnvelope;
    throw new ApiError(
      response.status,
      envelope.error?.code ?? "UNKNOWN",
      envelope.error?.message ?? "Unknown error",
    );
  }

  return json as OkEnvelope<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export { ApiError };
