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
export type ProtectionMode = "off" | "advisor" | "auto";
export interface ProtectionPolicy { id: number; condition: string; actions: string[]; goal: string; enabled?: boolean }
export interface ProtectionAction { time: string; label: string; tone: "yellow" | "orange" | "cyan" | "green" | "red" }
export interface BacktestOHLC { o: number; h: number; l: number; c: number }
export interface BacktestPoint {
  block: number;
  score: number;
  level: "RED" | "YELLOW" | null;
  confirmed: boolean;
  rcs: Array<{ contract: string; contribution: number }>;
  price: number | null;
  ohlc: BacktestOHLC | null;
  liq: number;
  b0: number;
  breadth: number;
  n_active: number;
}
export interface BacktestTimeline {
  fixture: string;
  event_name: string;
  category: string;
  cascade_block: number | null;
  first_red_block: number | null;
  lead_hours: number | null;
  points: BacktestPoint[];
  error?: string;
}
export interface BacktestFixtures { fixtures: Array<{ name: string; category: string }> }

export interface ForecastBand { step: number; p10: number; p25: number; p50: number; p75: number; p90: number }
export interface FragilityBand { step: number; p10: number; p50: number; p90: number }
export interface FragilityForecast { horizon: number; bands: FragilityBand[]; p_cascade: number }
export interface Forecast {
  current_price?: number;
  horizon?: number;
  bands?: ForecastBand[];
  p_drawdown?: number;
  drawdown_pct?: number;
  p_down?: number;
  anchor_index: number;
  fragility?: FragilityForecast;
  current_score?: number;
  error?: string;
}

export interface CorrMatrix {
  labels: string[];
  matrix: number[][];
  anchor_index: number;
  error?: string;
}

export interface ExtensionSnapshot {
  version: string;
  generated_at: number;
  source: "demo" | "live";
  market: {
    symbol: string;
    stress_score: number;
    warning_score: number;
    alert_level: "CALM" | "YELLOW" | "RED";
    probability: number;
    confidence: number;
    horizon: string;
    primary_risk: string;
    rcs: Array<{ contract: string; contribution: number }>;
  };
  risks: RiskItem[];
  scenarios?: Array<{ id: string; title: string; probability: number; impact: string; timeframe: string; level: string }>;
  portfolio: {
    expected_loss: string;
    risk_score: number;
    safe_allocation: number;
    assets: Array<{ symbol: string; allocation: number; risk: string; loss: string }>;
  };
  protection: {
    mode: ProtectionMode;
    policies: Array<ProtectionPolicy & { enabled: boolean }>;
    active_count: number;
    ready: boolean;
  };
  actions: ProtectionAction[];
}
