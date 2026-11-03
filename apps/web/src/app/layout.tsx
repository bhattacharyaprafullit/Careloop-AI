import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { DemoBanner } from "@/components/demo-banner";
import { AppProviders } from "@/hooks/use-sandbox";
import { ThemeProvider } from "@/hooks/use-theme";
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
    <html lang="en" className={`${inter.variable} dark`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('careloop-theme');if(t==='light'){document.documentElement.classList.remove('dark');}else{document.documentElement.classList.add('dark');}}catch(e){}})();`,
          }}
        />
      </head>
      <body className={`${inter.className} min-h-screen antialiased bg-slate-50 text-slate-900 dark:bg-[#090d16] dark:text-slate-100`}>
        <ThemeProvider>
          <DemoBanner />
          <AppProviders>{children}</AppProviders>
        </ThemeProvider>
      </body>
    </html>
  );
}
