"use client";

import { useState } from "react";
import { portfolioAssets } from "@/lib/mock-data";
import type { ExtensionPage } from "@/lib/types";
import { ActionButton, MetricCard, SectionCard, SidebarHeader } from "../shared/UI";

export default function PortfolioImpactPage({ onNavigate }: { onNavigate: (p: ExtensionPage) => void }) {
  const [details, setDetails] = useState(false);
  return <div className="page-frame page-enter"><SidebarHeader title="Tác Động Danh Mục" subtitle="4 tài sản · Phân tích theo thời gian thực" /><div className="page-body"><div className="metrics"><MetricCard value="-8%" label="Tổn thất dự kiến" tone="red" /><MetricCard value="78/100" label="Risk Score" tone="orange" /><MetricCard value="17%" label="Danh mục an toàn" tone="green" /></div><SectionCard><div className="row"><h2 className="section-title">Phân bổ tài sản</h2><span className="muted" style={{ fontSize: 9 }}>100%</span></div><div className="segmented">{portfolioAssets.map((asset) => <span key={asset.symbol} style={{ width: `${asset.allocation}%`, background: asset.color }} />)}</div></SectionCard><div className="stack">{portfolioAssets.map((asset) => <SectionCard key={asset.symbol}><div className="row"><div><strong style={{ fontFamily: "Outfit" }}>{asset.symbol}</strong><span className="muted" style={{ marginLeft: 7, fontSize: 10 }}>Risk: {asset.risk}</span></div><strong className="mono" style={{ color: asset.color }}>{asset.allocation}%</strong></div><div className="row" style={{ marginTop: 7, fontSize: 10 }}><span className="muted">Tổn thất dự kiến</span><span className={asset.loss.startsWith("-") ? "red mono" : "green mono"}>{asset.loss}</span></div>{details && <p style={{ margin: "9px 0 0", paddingTop: 8, borderTop: "1px solid #1f2937", color: "#9aa8b9", fontSize: 10.5 }}>{asset.detail}</p>}</SectionCard>)}</div><ActionButton variant="secondary" onClick={() => setDetails(!details)}>{details ? "Thu gọn" : "Xem chi tiết"}</ActionButton><ActionButton onClick={() => onNavigate("playbook")}>Xem Playbook Xử Lý →</ActionButton></div></div>;
}
