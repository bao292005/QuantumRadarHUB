import type { ExtensionSnapshot, ProtectionMode } from "./types";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_QUANTUMRADAR_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`QuantumRadar API ${response.status}`);
  return response.json() as Promise<T>;
}

export function fetchExtensionSnapshot(signal?: AbortSignal) {
  return request<ExtensionSnapshot>("/api/v1/extension/snapshot", { signal });
}

export function putProtectionMode(mode: ProtectionMode) {
  return request<ExtensionSnapshot["protection"]>("/api/v1/protection/mode", {
    method: "PUT",
    body: JSON.stringify({ mode }),
  });
}

export function patchProtectionPolicy(policyId: number, enabled: boolean) {
  return request<ExtensionSnapshot["protection"]>(`/api/v1/protection/policies/${policyId}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
}
