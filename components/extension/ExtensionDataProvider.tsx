"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchExtensionSnapshot, patchProtectionPolicy, putProtectionMode } from "@/lib/api";
import type { ExtensionSnapshot, ProtectionMode } from "@/lib/types";

type BackendStatus = "connecting" | "online" | "offline";
interface ExtensionDataContextValue {
  snapshot: ExtensionSnapshot | null;
  status: BackendStatus;
  refresh: () => Promise<void>;
  updateMode: (mode: ProtectionMode) => Promise<void>;
  updatePolicy: (policyId: number, enabled: boolean) => Promise<void>;
}

const ExtensionDataContext = createContext<ExtensionDataContextValue | null>(null);

export function ExtensionDataProvider({ children }: { children: React.ReactNode }) {
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
    const interval = window.setInterval(refresh, 15_000);
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

  const value = useMemo(() => ({ snapshot, status, refresh, updateMode, updatePolicy }), [snapshot, status, refresh, updateMode, updatePolicy]);
  return <ExtensionDataContext.Provider value={value}>{children}</ExtensionDataContext.Provider>;
}

export function useExtensionData() {
  const context = useContext(ExtensionDataContext);
  if (!context) throw new Error("useExtensionData must be used inside ExtensionDataProvider");
  return context;
}
