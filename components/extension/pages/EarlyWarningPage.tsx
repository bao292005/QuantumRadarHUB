"use client";

import { useEffect, useState } from "react";
import type { ExtensionPage } from "@/lib/types";
import { ActionButton, LiveIndicator, MetricCard, ProgressBar, SectionCard, SidebarHeader } from "../shared/UI";
import { useExtensionData } from "../ExtensionDataProvider";

export default function EarlyWarningPage({ onNavigate }: { onNavigate: (p: ExtensionPage) => void }) {
  const { snapshot } = useExtensionData();
  const [score, setScore] = useState(72);
  const scoreTarget = snapshot?.market.warning_score ?? 84;
  useEffect(() => { const id = window.setTimeout(() => setScore(scoreTarget), 300); return () => clearTimeout(id); }, [scoreTarget]);
  // Signals from the REAL RCS epicenter list when live; illustrative fallback otherwise.
  const rcs = snapshot?.market.rcs ?? [];
  const signals = rcs.length
    ? rcs.slice(0, 4).map((r) => `${r.contract} — đóng góp tương quan RCS ${r.contribution}`)
    : ["Thanh khoản suy yếu (minh hoạ)", "Khối lượng bán tháo tăng (minh hoạ)", "Tương quan chuỗi chéo tăng (minh hoạ)", "Stablecoin outflow bất thường (minh hoạ)"];
  return <div className="page-frame page-enter"><SidebarHeader title="Trung Tâm Cảnh Báo Sớm" subtitle={`${snapshot?.market.symbol ?? "AAVEUSDT"} · Phát hiện dị thường`}><LiveIndicator /></SidebarHeader><div className="page-body"><SectionCard><div className="eyebrow" style={{ marginBottom: 9 }}>Tóm Tắt Từ QuantumRadar</div><div className="metrics"><MetricCard value={snapshot?.market.primary_risk ?? "Liquidity Shock"} label="Rủi ro chính" /><MetricCard value={`${snapshot?.market.probability ?? 72}%`} label="Xác suất" tone="orange" /><MetricCard value={snapshot?.market.horizon ?? "12-24h"} label="Thời gian" /></div></SectionCard><SectionCard><div className="row"><div className="eyebrow orange">Rủi ro đang gia tăng</div><span className="badge red">RẤT CAO</span></div><div style={{ margin: "15px 0 8px" }}><span className="mono red" style={{ fontSize: 36, fontWeight: 900 }}>{score}</span><span className="mono muted"> / 100</span></div><ProgressBar value={score} /><div style={{ marginTop: 10, color: "#f97316", fontSize: 11 }}>{snapshot?.market.alert_level === "RED" ? "🔴 Cảnh báo RED đã xác nhận" : snapshot?.market.alert_level === "YELLOW" ? "🟡 Cảnh báo YELLOW" : "Đang theo dõi"} <span className="muted">· warning {Math.round(snapshot?.market.warning_score ?? 0)}/100</span></div></SectionCard><section><h2 className="section-title">Tín Hiệu Dị Thường</h2><div className="stack">{signals.map((signal, index) => <SectionCard key={signal}><div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 11.5 }}><span className={index < 2 ? "orange" : "cyan"}>●</span><span>{signal}</span></div></SectionCard>)}</div></section><ActionButton onClick={() => onNavigate("scenario")}>Xem Kịch Bản Dự Báo →</ActionButton></div></div>;
}
