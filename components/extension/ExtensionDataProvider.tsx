"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchExtensionSnapshot, patchProtectionPolicy, putProtectionMode } from "@/lib/api";
import type { BacktestPoint, ExtensionSnapshot, RiskItem, Severity } from "@/lib/types";
import type { ProtectionMode } from "@/lib/types";

// Overlay the chart's exact current point onto the polled snapshot so the extension
// numbers match the candlestick frame-for-frame (no backend round-trip lag).
function mergeLive(base: ExtensionSnapshot | null, live: BacktestPoint | null): ExtensionSnapshot | null {
  if (!base || !live) return base;
  const score = live.score;
  const level = (live.level ?? "CALM") as "CALM" | "YELLOW" | "RED";
  const probability = Math.min(95, Math.max(35, Math.round(score * 0.92)));
  const rcs = live.rcs ?? [];
  let primary_risk = base.market.primary_risk;
  let risks: RiskItem[] = base.risks;
  if (rcs.length) {
    primary_risk = `${rcs[0].contract} (RCS epicenter)`;
    const status = score >= 90 ? "Rủi ro cao" : score >= 70 ? "Trung bình" : "Theo dõi";
    const sev = (r: number): Severity => (r === 0 ? (score >= 90 ? "high" : score >= 70 ? "medium" : "low") : r === 1 ? "medium" : "low");
    risks = rcs.slice(0, 3).map((r, i) => ({
      id: String(r.contract),
      title: `${r.contract} — RCS epicenter`,
      probability: Math.min(95, Math.max(35, Math.round(score * (0.95 - 0.2 * i)))),
      horizon: "12-24h",
      status: i === 0 ? status : "Theo dõi",
      severity: sev(i),
    }));
  }
  return {
    ...base,
    source: "live",
    market: { ...base.market, stress_score: score, warning_score: Math.min(100, Math.round(score + 6)), alert_level: level, probability, primary_risk, rcs },
    risks,
  };
}

type BackendStatus = "connecting" | "online" | "offline";
interface ExtensionDataContextValue {
  snapshot: ExtensionSnapshot | null;
  status: BackendStatus;
  refresh: () => Promise<void>;
  updateMode: (mode: ProtectionMode) => Promise<void>;
  updatePolicy: (policyId: number, enabled: boolean) => Promise<void>;
}

const ExtensionDataContext = createContext<ExtensionDataContextValue | null>(null);

export function ExtensionDataProvider({ children, live = null }: { children: React.ReactNode; live?: BacktestPoint | null }) {
  const [snapshot, setSnapshot] = useState<ExtensionSnapshot | null>(null);
  const [status, setStatus] = useState<BackendStatus>("connecting");

  const refresh = useCallback(async () => {
    try {
      const nextSnapshot = await fetchExtensionSnapshot();
      setSnapshot(nextSnapshot);
      setStatus("online");
    } catch {
      setStatus("offline");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchExtensionSnapshot(controller.signal)
      .then((nextSnapshot) => { setSnapshot(nextSnapshot); setStatus("online"); })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setStatus("offline");
      });
    const interval = window.setInterval(refresh, 2_000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, [refresh]);

  const updateMode = useCallback(async (mode: ProtectionMode) => {
    setSnapshot((current) => current ? { ...current, protection: { ...current.protection, mode, ready: mode !== "off" && current.protection.active_count > 0 } } : current);
    try {
      const protection = await putProtectionMode(mode);
      setSnapshot((current) => current ? { ...current, protection } : current);
      setStatus("online");
    } catch { setStatus("offline"); }
  }, []);

  const updatePolicy = useCallback(async (policyId: number, enabled: boolean) => {
    setSnapshot((current) => {
      if (!current) return current;
      const policies = current.protection.policies.map((policy) => policy.id === policyId ? { ...policy, enabled } : policy);
      const active_count = policies.filter((policy) => policy.enabled).length;
      return { ...current, protection: { ...current.protection, policies, active_count, ready: current.protection.mode !== "off" && active_count > 0 } };
    });
    try {
      const protection = await patchProtectionPolicy(policyId, enabled);
      setSnapshot((current) => current ? { ...current, protection } : current);
      setStatus("online");
    } catch { setStatus("offline"); }
  }, []);

  const effective = useMemo(() => mergeLive(snapshot, live), [snapshot, live]);
  const value = useMemo(() => ({ snapshot: effective, status, refresh, updateMode, updatePolicy }), [effective, status, refresh, updateMode, updatePolicy]);
  return <ExtensionDataContext.Provider value={value}>{children}</ExtensionDataContext.Provider>;
}

export function useExtensionData() {
  const context = useContext(ExtensionDataContext);
  if (!context) throw new Error("useExtensionData must be used inside ExtensionDataProvider");
  return context;
}
