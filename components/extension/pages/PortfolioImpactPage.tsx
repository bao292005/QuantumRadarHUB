"use client";

import { useState } from "react";
import { portfolioAssets } from "@/lib/mock-data";
import type { ExtensionPage } from "@/lib/types";
import { ActionButton, MetricCard, SectionCard, SidebarHeader } from "../shared/UI";
import { useExtensionData } from "../ExtensionDataProvider";

// Pure PRESENTATION (color + copy) keyed by symbol — not algorithm data.
// The holdings themselves come from the backend snapshot (illustrative: there is
// no wallet feed yet, so allocations/loss are demo values single-sourced on the API).
const PRESENTATION: Record<string, { color: string; detail: string }> = {
  AAVE: { color: "#f97316", detail: "Thanh khoản suy yếu, áp lực bán tăng." },
  ETH: { color: "#a78bfa", detail: "Tương quan hệ thống đang tăng." },
  BNB: { color: "#f59e0b", detail: "Biến động trong ngưỡng kiểm soát." },
  USDC: { color: "#22c55e", detail: "Tài sản phòng thủ của danh mục." },
};

export default function PortfolioImpactPage({ onNavigate }: { onNavigate: (p: ExtensionPage) => void }) {
  const { snapshot } = useExtensionData();
  const [details, setDetails] = useState(false);

  const pf = snapshot?.portfolio;
  const riskScore = Math.round(snapshot?.market.stress_score ?? pf?.risk_score ?? 78);
  const expectedLoss = pf?.expected_loss ?? "-8%";
  const safeAllocation = pf?.safe_allocation ?? 17;
  const assets = (pf?.assets ?? portfolioAssets).map((a) => {
    const p = PRESENTATION[a.symbol];
    return { ...a, color: p?.color ?? "#64748b", detail: p?.detail ?? "" };
  });

  return <div className="page-frame page-enter"><SidebarHeader title="Tác Động Danh Mục" subtitle="Risk Score trực tiếp · danh mục minh hoạ" /><div className="page-body"><div className="metrics"><MetricCard value={expectedLoss} label="Tổn thất dự kiến" tone="red" /><MetricCard value={`${riskScore}/100`} label="Risk Score" tone="orange" /><MetricCard value={`${safeAllocation}%`} label="Danh mục an toàn" tone="green" /></div><SectionCard><div className="row"><h2 className="section-title">Phân bổ tài sản</h2><span className="muted" style={{ fontSize: 9 }}>minh hoạ · 100%</span></div><div className="segmented">{assets.map((asset) => <span key={asset.symbol} style={{ width: `${asset.allocation}%`, background: asset.color }} />)}</div></SectionCard><div className="stack">{assets.map((asset) => <SectionCard key={asset.symbol}><div className="row"><div><strong style={{ fontFamily: "Outfit" }}>{asset.symbol}</strong><span className="muted" style={{ marginLeft: 7, fontSize: 10 }}>Risk: {asset.risk}</span></div><strong className="mono" style={{ color: asset.color }}>{asset.allocation}%</strong></div><div className="row" style={{ marginTop: 7, fontSize: 10 }}><span className="muted">Tổn thất dự kiến</span><span className={asset.loss.startsWith("-") ? "red mono" : "green mono"}>{asset.loss}</span></div>{details && asset.detail && <p style={{ margin: "9px 0 0", paddingTop: 8, borderTop: "1px solid #1f2937", color: "#9aa8b9", fontSize: 10.5 }}>{asset.detail}</p>}</SectionCard>)}</div><ActionButton variant="secondary" onClick={() => setDetails(!details)}>{details ? "Thu gọn" : "Xem chi tiết"}</ActionButton><ActionButton onClick={() => onNavigate("playbook")}>Xem Playbook Xử Lý →</ActionButton></div></div>;
}
