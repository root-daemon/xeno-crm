"use client";

import { Database } from "lucide-react";
import { useRouter } from "next/navigation";
import { CLIENT_API_BASE } from "../lib/api";

export function SeedButton() {
  const router = useRouter();

  async function seed() {
    await fetch(`${CLIENT_API_BASE}/seed`, { method: "POST" });
    router.refresh();
  }

  return <button className="button secondary" onClick={seed}><Database size={18} />Seed Demo Data</button>;
}
