import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuantumRadar AI",
  description: "AI-powered DeFi crisis forecasting and portfolio risk guardian.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}
