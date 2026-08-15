export type ExtensionPage =
  | "radar"
  | "early-warning"
  | "scenario"
  | "portfolio"
  | "playbook"
  | "auto-protection";

export type Severity = "low" | "medium" | "high" | "critical";
export interface RiskItem { id: string; title: string; probability: number; horizon: string; status: string; severity: Severity }
export interface Scenario { id: string; title: string; probability: number; impact: string; timeframe: string; level: string; actions: string[]; tone: "green" | "red" }
export interface PortfolioAsset { symbol: string; allocation: number; risk: string; loss: string; color: string; detail: string }
export interface ProtectionPolicy { id: number; condition: string; actions: string[]; goal: string }
export interface ProtectionAction { time: string; label: string; tone: "yellow" | "orange" | "cyan" | "green" }
