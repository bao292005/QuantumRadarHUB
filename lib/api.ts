import type { BacktestFixtures, BacktestTimeline, Forecast, CorrMatrix, ExtensionSnapshot, ProtectionMode } from "./types";

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

export function fetchBacktestFixtures(signal?: AbortSignal) {
  return request<BacktestFixtures>("/api/v1/backtest/fixtures", { signal });
}

export function fetchBacktestTimeline(fixture: string, signal?: AbortSignal) {
  return request<BacktestTimeline>(
    `/api/v1/backtest/timeline?fixture=${encodeURIComponent(fixture)}`,
    { signal },
  );
}

export function fetchForecast(fixture: string, i: number, signal?: AbortSignal) {
  return request<Forecast>(
    `/api/v1/backtest/forecast?fixture=${encodeURIComponent(fixture)}&i=${i}`,
    { signal },
  );
}

export function fetchCorr(fixture: string, i: number, signal?: AbortSignal) {
  return request<CorrMatrix>(
    `/api/v1/backtest/corr?fixture=${encodeURIComponent(fixture)}&i=${i}`,
    { signal },
  );
}

export function startReplay(fixture: string, speed = 1) {
  return request<{ ok: boolean; running: boolean; fixture: string; i: number; n: number }>(
    "/api/v1/replay",
    { method: "POST", body: JSON.stringify({ fixture, speed }) },
  );
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
