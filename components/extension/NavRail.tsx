"use client";

import { Activity, Bot, BriefcaseBusiness, CircleUserRound, Radar, ShieldAlert, Target } from "lucide-react";
import type { ExtensionPage } from "@/lib/types";

const nav = [
  ["radar", "Radar", Radar], ["early-warning", "Cảnh báo", ShieldAlert], ["scenario", "Kịch bản", Activity],
  ["portfolio", "Danh mục", BriefcaseBusiness], ["playbook", "Xử lý", Target], ["auto-protection", "Auto AI", Bot],
] as const;

export default function NavRail({ current, onNavigate }: { current: ExtensionPage; onNavigate: (page: ExtensionPage) => void }) {
  return <nav className="nav-rail" aria-label="Điều hướng QuantumRadar"><div className="nav-logo" aria-hidden="true" /><div className="nav-rule" />{nav.map(([page, label, Icon]) => <button key={page} type="button" title={label} aria-label={label} aria-current={current === page ? "page" : undefined} className={`nav-button ${current === page ? "active" : ""}`} onClick={() => onNavigate(page)}><Icon size={17} /></button>)}<div className="nav-spacer" /><button type="button" className="nav-button" title="Hồ sơ" aria-label="Hồ sơ"><CircleUserRound size={17} /></button></nav>;
}
