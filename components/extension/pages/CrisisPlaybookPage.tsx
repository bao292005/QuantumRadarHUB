"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { ExtensionPage } from "@/lib/types";
import { ActionButton, MetricCard, SectionCard, SidebarHeader } from "../shared/UI";
import { useExtensionData } from "../ExtensionDataProvider";

// Playbook plans are ILLUSTRATIVE advisory strings — the algorithm does not emit
// remediation steps. Only the current Risk Score + worst-scenario loss are live.
const plans = [
  { id: "a", title: "Kế Hoạch A", badge: "AN TOÀN HƠN", tone: "green", steps: ["Bán 15% AAVE", "Tăng stablecoin"], loss: "-8%" },
  { id: "c", title: "Kế Hoạch C", badge: "RỦI RO HƠN", tone: "red", steps: ["Emergency Exit", "Bán toàn bộ AAVE"], loss: "-1%" },
];

export default function CrisisPlaybookPage({ onNavigate }: { onNavigate: (p: ExtensionPage) => void }) {
  const { snapshot } = useExtensionData();
  const [open, setOpen] = useState<string | null>(null);

  const riskScore = Math.round(snapshot?.market.stress_score ?? 78);
  // no-action loss = worst (most negative) MPS scenario impact; illustrative fallback
  const worst = (snapshot?.scenarios ?? [])
    .map((s) => ({ s, n: parseFloat(s.impact) }))
    .filter((x) => !Number.isNaN(x.n))
    .sort((a, b) => a.n - b.n)[0]?.s;
  const noActionLoss = worst?.impact ?? "-21%";

  return <div className="page-frame page-enter"><SidebarHeader title="Playbook Xử Lý Khủng Hoảng" subtitle="Risk Score trực tiếp · phương án minh hoạ" /><div className="page-body"><SectionCard><div className="row"><span className="eyebrow cyan">Khuyến nghị từ AI</span><span className="badge cyan">KẾ HOẠCH B</span></div><h2 style={{ margin: "10px 0 3px", fontFamily: "Outfit", fontSize: 20 }}>Chuyển sang USDC</h2><p className="muted" style={{ margin: "0 0 10px", fontSize: 11 }}>Giảm rủi ro cho danh mục</p><div className="metrics"><MetricCard value="18%" label="Giảm rủi ro" tone="green" /><MetricCard value="CAO" label="Độ tin cậy AI" tone="cyan" /><MetricCard value="B" label="Kế hoạch" /></div></SectionCard><div className="metrics"><SectionCard><div className="muted" style={{ fontSize: 9 }}>Không hành động</div><div className="mono red" style={{ fontSize: 18, margin: "7px 0" }}>{noActionLoss}</div><div className="muted" style={{ fontSize: 8.5 }}>Risk Score {riskScore}</div></SectionCard><SectionCard><div className="muted" style={{ fontSize: 9 }}>Sau kế hoạch B <span style={{ opacity: .6 }}>(minh hoạ)</span></div><div className="mono green" style={{ fontSize: 18, margin: "7px 0" }}>-3%</div><div className="muted" style={{ fontSize: 8.5 }}>Risk Score {Math.max(0, riskScore - 18)}</div></SectionCard><SectionCard><div className="muted" style={{ fontSize: 9 }}>Mức cải thiện</div><div className="mono cyan" style={{ fontSize: 18, margin: "7px 0" }}>18%</div><div className="muted" style={{ fontSize: 8.5 }}>Tổn thất giảm</div></SectionCard></div><section><h2 className="section-title">Phương Án Khác <span className="muted" style={{ fontSize: 9, fontWeight: 400 }}>· minh hoạ</span></h2><div className="stack">{plans.map((plan) => <button key={plan.id} className="expand-card" aria-expanded={open === plan.id} onClick={() => setOpen(open === plan.id ? null : plan.id)}><div className="row"><strong style={{ fontFamily: "Outfit" }}>{plan.title}</strong><span className={`badge ${plan.tone}`}>{plan.badge}</span><ChevronDown size={14} /></div><div className="expand-content"><div><div style={{ marginTop: 10, paddingTop: 8, borderTop: "1px solid #1f2937", fontSize: 11 }}>{plan.steps.map((step) => <div key={step}>• {step}</div>)}<div className="row" style={{ marginTop: 8 }}><span className="muted">Tổn thất dự kiến</span><strong className="mono">{plan.loss}</strong></div></div></div></div></button>)}</div></section><ActionButton onClick={() => onNavigate("auto-protection")}>Thiết Lập Auto Protection</ActionButton><ActionButton variant="ghost" onClick={() => onNavigate("portfolio")}>← Quay Lại Danh Mục</ActionButton></div></div>;
}
