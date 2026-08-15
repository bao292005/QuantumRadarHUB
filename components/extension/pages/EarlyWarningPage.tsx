"use client";

import { useEffect, useState } from "react";
import type { ExtensionPage } from "@/lib/types";
import { ActionButton, LiveIndicator, MetricCard, ProgressBar, SectionCard, SidebarHeader } from "../shared/UI";

export default function EarlyWarningPage({ onNavigate }: { onNavigate: (p: ExtensionPage) => void }) {
  const [score, setScore] = useState(72);
  useEffect(() => { const id = window.setTimeout(() => setScore(84), 300); return () => clearTimeout(id); }, []);
  const signals = ["Thanh khoản AAVE giảm 34%", "Khối lượng bán tháo tăng 5.2x", "Tương quan chuỗi chéo tăng", "Stablecoin outflow bất thường"];
  return <div className="page-frame page-enter"><SidebarHeader title="Trung Tâm Cảnh Báo Sớm" subtitle="AAVEUSDT · Phát hiện dị thường"><LiveIndicator /></SidebarHeader><div className="page-body"><SectionCard><div className="eyebrow" style={{ marginBottom: 9 }}>Tóm Tắt Từ QuantumRadar</div><div className="metrics"><MetricCard value="Liquidity Shock" label="Rủi ro chính" /><MetricCard value="72%" label="Xác suất" tone="orange" /><MetricCard value="12-24h" label="Thời gian" /></div></SectionCard><SectionCard><div className="row"><div className="eyebrow orange">Rủi ro đang gia tăng</div><span className="badge red">RẤT CAO</span></div><div style={{ margin: "15px 0 8px" }}><span className="mono red" style={{ fontSize: 36, fontWeight: 900 }}>{score}</span><span className="mono muted"> / 100</span></div><ProgressBar value={score} /><div style={{ marginTop: 10, color: "#f97316", fontSize: 11 }}>↑ Tăng 16.7% <span className="muted">trong 45 phút</span></div></SectionCard><section><h2 className="section-title">Tín Hiệu Dị Thường</h2><div className="stack">{signals.map((signal, index) => <SectionCard key={signal}><div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 11.5 }}><span className={index < 2 ? "orange" : "cyan"}>●</span><span>{signal}</span></div></SectionCard>)}</div></section><ActionButton onClick={() => onNavigate("scenario")}>Xem Kịch Bản Dự Báo →</ActionButton></div></div>;
}
