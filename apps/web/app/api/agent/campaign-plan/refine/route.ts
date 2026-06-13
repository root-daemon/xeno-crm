import { NextRequest, NextResponse } from "next/server";
import { API_BASE } from "../../../../../lib/api";

const REQUEST_TIMEOUT_MS = 10000;

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const response = await fetch(`${API_BASE}/agent/campaign-plan/refine`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      cache: "no-store",
    });

    const payload = await response.json().catch(() => ({ error: response.statusText }));
    return NextResponse.json(payload, { status: response.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("[campaign-plan-refine-proxy]", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
