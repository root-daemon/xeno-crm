export const API_BASE = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const CLIENT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_TIMEOUT_MS = 2500;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {})
    },
    signal: init?.signal ?? AbortSignal.timeout(API_TIMEOUT_MS),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type Summary = {
  totals: {
    customers: number;
    orders: number;
    campaigns: number;
    active_segments: number;
    campaigns_sent: number;
    communications: number;
    revenue: number;
    revenue_generated: number;
  };
  recommendations: {
    inactive_customers: number;
    potential_recovery_revenue: number;
    default_goal: string;
  };
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
  phone: string;
  email: string;
  city: string;
  gender: string;
  loyalty_tier: string;
  tags: string[];
  whatsapp_opt_in: boolean;
  sms_opt_in: boolean;
  email_opt_in: boolean;
  rcs_opt_in: boolean;
  last_active_days_ago: number;
  order_count: number;
  lifetime_value: number;
  last_order_days_ago: number | null;
  purchase_history?: Order[];
  ai_summary?: string;
};

export type Order = {
  id: string;
  customer_id: string;
  total: number;
  items: string[];
  channel: string;
  days_ago: number;
  created_at: string | null;
};

export type SegmentRules = {
  channel?: string;
  city?: string;
  loyalty_tier?: string;
  min_lifetime_value?: number;
  min_last_order_days_ago?: number;
  max_last_order_days_ago?: number;
  tag?: string;
};

export type Segment = {
  id: string;
  name: string;
  rules: SegmentRules;
  audience_size: number;
  created_at: string | null;
};

export type Performance = {
  campaign: Campaign;
  audience_size: number;
  counts: Record<string, number>;
  revenue: number;
  communications: {
    id: string;
    campaign_id: string;
    customer_id: string;
    channel: string;
    recipient: Record<string, unknown>;
    message: string;
    status: string;
    attributed_revenue: number;
    created_at: string | null;
  }[];
};
