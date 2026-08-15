import type { PortfolioAsset, ProtectionAction, ProtectionPolicy, RiskItem, Scenario } from "./types";

export const radarRisks: RiskItem[] = [
  { id: "liquidity", title: "Liquidity Shock", probability: 72, horizon: "12-24h", status: "Rủi ro cao", severity: "high" },
  { id: "depeg", title: "Stablecoin Depeg", probability: 58, horizon: "24-48h", status: "Trung bình", severity: "medium" },
  { id: "cascade", title: "Lending Cascade", probability: 45, horizon: "2-3 ngày", status: "Theo dõi", severity: "low" },
];

export const scenarios: Scenario[] = [
  { id: "recovery", title: "Recovery", probability: 35, impact: "+6%", timeframe: "72h", level: "Tích cực", actions: ["Giữ nguyên danh mục", "Chờ xác nhận trend"], tone: "green" },
  { id: "contagion", title: "Contagion Event", probability: 15, impact: "-38%", timeframe: "6-12h", level: "Rất nghiêm trọng", actions: ["Emergency Exit", "Chuyển toàn bộ sang USDC"], tone: "red" },
];

export const portfolioAssets: PortfolioAsset[] = [
  { symbol: "AAVE", allocation: 35, risk: "Cao", loss: "-8.0%", color: "#f97316", detail: "Thanh khoản suy yếu, áp lực bán tăng 5.2x." },
  { symbol: "ETH", allocation: 28, risk: "Trung", loss: "-3.1%", color: "#a78bfa", detail: "Tương quan hệ thống đang tăng." },
  { symbol: "BNB", allocation: 20, risk: "Thấp", loss: "-1.2%", color: "#f59e0b", detail: "Biến động trong ngưỡng kiểm soát." },
  { symbol: "USDC", allocation: 17, risk: "An toàn", loss: "0%", color: "#22c55e", detail: "Tài sản phòng thủ của danh mục." },
];

export const protectionPolicies: ProtectionPolicy[] = [
  { id: 1, condition: "Liquidity Crisis > 80%", actions: ["Bán 30% AAVE", "Chuyển sang USDC"], goal: "Giảm rủi ro danh mục" },
  { id: 2, condition: "Stablecoin Depeg xác nhận", actions: ["Thoát toàn bộ Stablecoin rủi ro"], goal: "Bảo vệ tài sản ổn định" },
  { id: 3, condition: "Contagion Risk > 90%", actions: ["Emergency Exit", "Về trạng thái phòng thủ"], goal: "Bảo toàn toàn bộ vốn" },
];

export const protectionHistory: ProtectionAction[] = [
  { time: "14:32", label: "AI phát hiện Liquidity Shock", tone: "yellow" },
  { time: "14:35", label: "AI kích hoạt Policy #01", tone: "orange" },
  { time: "14:36", label: "Bán 30% AAVE thành công", tone: "cyan" },
  { time: "14:37", label: "Chuyển sang USDC hoàn tất", tone: "cyan" },
  { time: "14:40", label: "Danh mục giảm rủi ro 18%", tone: "green" },
];
