import type { Metadata } from "next";
import { BarChart3, Bot, Send, Settings, SlidersHorizontal, Users } from "lucide-react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Xeno Agentic CRM",
  description: "AI-native CRM for shopper campaigns"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <div className="brand">Xeno CRM</div>
            <nav className="nav">
              <Link href="/"><BarChart3 size={18} />Dashboard</Link>
              <Link href="/customers"><Users size={18} />Customers</Link>
              <Link href="/segments"><SlidersHorizontal size={18} />Segments</Link>
              <Link href="/campaigns"><Send size={18} />Campaigns</Link>
              <Link href="/campaigns/new"><Bot size={18} />AI Agent</Link>
              <Link href="/settings"><Settings size={18} />AI Settings</Link>
            </nav>
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
