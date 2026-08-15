"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { scenarios } from "@/lib/mock-data";
import type { ExtensionPage } from "@/lib/types";
import { ActionButton, MetricCard, SectionCard, SidebarHeader } from "../shared/UI";
import { useExtensionData } from "../ExtensionDataProvider";

export default function ScenarioForecastPage({ onNavigate }: { onNavigate: (p: ExtensionPage) => void }) {
  const { snapshot } = useExtensionData();
  const live = snapshot?.scenarios;
  // Merge real MPS-generative probabilities (matched by id) into the display scenarios.
  const merged = scenarios.map((s) => ({
    ...s,
    probability: live?.find((x) => x.id === s.id)?.probability ?? s.probability,
  }));
  const top = [...merged].sort((a, b) => b.probability - a.probability)[0];
  const rest = merged.filter((s) => s.id !== top.id);
  const [open, setOpen] = useState<string | null>(rest[0]?.id ?? null);
  const subtitle = snapshot?.source === "live" ? "MPS forecast · trực tiếp" : "3 tình huống khả dĩ";

  return <div className="page-frame page-enter"><SidebarHeader title={<>Dự Báo <span className="purple">Kịch Bản</span></>} subtitle={subtitle} /><div className="page-body"><SectionCard className="scenario-main"><div className="row"><span className="eyebrow purple">Kịch bản AI đánh giá cao nhất</span><span className="badge purple">CÓ KHẢ NĂNG NHẤT</span></div><h2 style={{ fontFamily: "Outfit", margin: "10px 0", fontSize: 21 }}>{top.title}</h2><div className="metrics"><MetricCard value={`${top.probability}%`} label="Xác suất" tone="purple" /><MetricCard value={top.impact} label="Tác động" tone="red" /><MetricCard value={top.timeframe} label="Thời gian" /></div><div className="row" style={{ marginTop: 11, fontSize: 11 }}><span>Mức độ: <strong className="red">{top.level}</strong></span></div>{top.actions[0] && <div style={{ marginTop: 10, padding: 9, borderRadius: 7, background: "rgba(167,139,250,.06)", fontSize: 11 }}><span className="purple">AI khuyến nghị</span><br /><strong>{top.actions.join(" → ")}</strong></div>}</SectionCard><section><h2 className="section-title">Kịch Bản Khác</h2><div className="stack">{rest.map((scenario) => <button type="button" className="expand-card" aria-expanded={open === scenario.id} key={scenario.id} onClick={() => setOpen(open === scenario.id ? null : scenario.id)}><div className="row"><strong style={{ fontFamily: "Outfit" }}>{scenario.title}</strong><ChevronDown size={15} style={{ transform: open === scenario.id ? "rotate(180deg)" : undefined, transition: "transform .2s" }} /></div><div className="metrics" style={{ marginTop: 9 }}><MetricCard value={`${scenario.probability}%`} label="Xác suất" /><MetricCard value={scenario.impact} label="Tác động" tone={scenario.tone} /><MetricCard value={scenario.timeframe} label="Thời gian" /></div><div className="expand-content"><div><div style={{ marginTop: 9, paddingTop: 9, borderTop: "1px solid #1f2937", fontSize: 10.5 }}><span className="cyan">AI khuyến nghị</span>{scenario.actions.map((action) => <div key={action} style={{ marginTop: 5 }}>• {action}</div>)}</div></div></div></button>)}</div></section><ActionButton onClick={() => onNavigate("portfolio")}>Xem Tác Động Danh Mục →</ActionButton></div></div>;
}
