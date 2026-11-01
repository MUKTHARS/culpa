import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import type { ReactNode } from "react";
import { Header } from "@/components/layout/Header/Header";
import { AuthProvider } from "@/context/AuthContext";
import "./globals.css";

// Self-hosted at build time by Next.js, so the CSP needs no external font host.
const brandFont = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-brand", display: "swap" });

export const metadata: Metadata = {
  title: "Culpa — fault attribution for agentic commerce",
  description: "Decides who is at fault when an AI agent's purchase goes wrong, and settles it on PayPal.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={brandFont.variable}>
      <body>
        <AuthProvider>
          <Header />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
