"use client";

import type { ReactNode } from "react";

export function SidebarHeader({ title, subtitle, children }: { title: ReactNode; subtitle: string; children?: ReactNode }) {
  return <header className="sidebar-header"><div className="header-row"><div><h1 className="header-title">{title}</h1><div className="header-subtitle">{subtitle}</div></div>{children}</div></header>;
}
export function LiveIndicator() { return <span className="live mono">LIVE</span>; }
export function RadarPulse() { return <div className="radar-pulse" aria-hidden="true"><span /><span /></div>; }
export function SectionCard({ children, className = "" }: { children: ReactNode; className?: string }) { return <section className={`section-card ${className}`}>{children}</section>; }
export function MetricCard({ value, label, tone = "" }: { value: string; label: string; tone?: string }) { return <div className="metric"><div className={`metric-value ${tone}`}>{value}</div><div className="metric-label">{label}</div></div>; }
export function ActionButton({ children, onClick, variant = "primary" }: { children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost" }) { return <button type="button" className={`${variant}-button`} onClick={onClick}>{children}</button>; }
export function ProgressBar({ value }: { value: number }) { return <div style={{ height: 5, borderRadius: 4, overflow: "hidden", background: "#263244" }}><div style={{ width: `${value}%`, height: "100%", background: "linear-gradient(90deg,#22c55e,#f59e0b 58%,#f97316 78%,#ef4444)", transition: "width 1s ease" }} /></div>; }
