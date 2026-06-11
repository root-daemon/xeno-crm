export const API_BASE = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const CLIENT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type Summary = {
  totals: { customers: number; orders: number; campaigns: number; communications: number; revenue: number };
  recent_campaigns: Campaign[];
};

export type Campaign = {
  id: string;
  name: string;
  goal: string;
  channel: string;
  status: string;
  created_at: string;
  segment_rules: Record<string, unknown>;
  message_template: string;
};

export type Customer = {
  id: string;
  name: string;
  city: string;
  loyalty_tier: string;
  tags: string[];
  lifetime_value: number;
  last_order_days_ago: number | null;
};
