import "./globals.css";
import type { Metadata } from "next";
import { Sidebar } from "@/components/shell/Sidebar";
import { Header } from "@/components/shell/Header";

export const metadata: Metadata = {
  title: "Praetor — governed runtime for agentic GRC",
  description:
    "One control plane. Run AI agents to do your compliance work; govern the AI you ship.",
  icons: {
    icon: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect x='2' y='2' width='4' height='12' fill='%23C4A572'/%3E%3Crect x='8' y='6' width='6' height='1' fill='%23F5EFE6'/%3E%3Crect x='8' y='9' width='6' height='1' fill='%23F5EFE6'/%3E%3C/svg%3E"
  }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Sidebar />
        <div className="flex min-h-screen flex-col md:ml-[224px]">
          <Header />
          <main className="flex-1 px-4 pt-6 pb-16 md:px-8 md:pt-8">{children}</main>
          <footer className="border-t border-rule px-4 py-5 text-[11.5px] text-paper-fade flex flex-col gap-2 md:flex-row md:items-center md:justify-between md:px-8">
            <span>
              Praetor — governed runtime for agentic GRC.{" "}
              <span className="text-paper-dim">
                Findings, citations, and proposed changes are not legal advice.
              </span>
            </span>
            <span className="font-mono text-paper-dim">build 2026.04.28-α</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
