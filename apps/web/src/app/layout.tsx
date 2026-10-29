import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { DemoBanner } from "@/components/demo-banner";
import { AppProviders } from "@/hooks/use-sandbox";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "CareLoop AI — Closing the Screening-to-Care Loop",
  description:
    "Decision-support demo for closed-loop screening follow-up. Synthetic data only; no diagnosis or prescribing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} min-h-screen antialiased`}>
        <DemoBanner />
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
