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
    "CareLoop AI bridges the gap between abnormal screening results and completed care by coordinating patient notifications, confirmatory tests, specialist referrals, and follow-ups.",
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
