"use client";

import { useState } from "react";
import type { ExtensionPage } from "@/lib/types";
import NavRail from "./NavRail";
import RadarPage from "./pages/RadarPage";
import EarlyWarningPage from "./pages/EarlyWarningPage";
import ScenarioForecastPage from "./pages/ScenarioForecastPage";
import PortfolioImpactPage from "./pages/PortfolioImpactPage";
import CrisisPlaybookPage from "./pages/CrisisPlaybookPage";
import AutoProtectionPage from "./pages/AutoProtectionPage";
import { ExtensionDataProvider } from "./ExtensionDataProvider";

export default function ExtensionShell() {
  const [page, setPage] = useState<ExtensionPage>("radar");
  const pages = { radar: RadarPage, "early-warning": EarlyWarningPage, scenario: ScenarioForecastPage, portfolio: PortfolioImpactPage, playbook: CrisisPlaybookPage, "auto-protection": AutoProtectionPage };
  const CurrentPage = pages[page];
  return <ExtensionDataProvider><div className="extension-shell"><NavRail current={page} onNavigate={setPage} /><CurrentPage onNavigate={setPage} /></div></ExtensionDataProvider>;
}
