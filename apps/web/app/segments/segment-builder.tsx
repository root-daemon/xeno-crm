"use client";

import { useMemo, useState } from "react";
import { Save, Sparkles } from "lucide-react";
import { CLIENT_API_BASE, Customer, Segment, SegmentRules } from "../../lib/api";

const emptyRules: SegmentRules = {};

type Preview = { audience: Customer[] };

export function SegmentBuilder({ initialSegments }: { initialSegments: Segment[] }) {
  const [segments, setSegments] = useState(initialSegments);
  const [name, setName] = useState("Inactive Coffee Buyers");
  const [rules, setRules] = useState<SegmentRules>({ channel: "sms", min_last_order_days_ago: 60, tag: "coffee" });
  const [prompt, setPrompt] = useState("Find loyal customers who stopped buying recently");
  const [audience, setAudience] = useState<Customer[]>([]);
  const [status, setStatus] = useState("");

  const ruleSummary = useMemo(() => summarizeRules(rules), [rules]);

  async function post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${CLIENT_API_BASE}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`${path} failed`);
    return response.json();
  }

  function updateRule<Key extends keyof SegmentRules>(key: Key, value: SegmentRules[Key] | "") {
    setRules((current) => {
      const next = { ...current };
      if (value === "" || value === undefined) {
        delete next[key];
      } else {
        next[key] = value as SegmentRules[Key];
      }
      return next;
    });
  }

  async function preview(nextRules = rules) {
    setStatus("Previewing audience...");
    const result = await post<Preview>("/segments/preview", { rules: nextRules });
    setAudience(result.audience);
    setStatus(`Audience Size: ${result.audience.length} customers`);
  }

  async function saveSegment() {
    setStatus("Saving segment...");
    const result = await post<Segment>("/segments", { name, rules });
    setSegments((current) => [result, ...current]);
    setStatus(`Saved ${result.name} with ${result.audience_size} customers`);
  }

  async function buildWithAi() {
    const nextRules = rulesFromPrompt(prompt);
    setRules(nextRules);
    setStatus("AI generated rules. Previewing audience...");
    await preview(nextRules);
  }

  return (
    <div className="grid two">
      <section className="panel grid">
        <h2>Manual Segment Builder</h2>
        <label>
          Segment name
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <div className="toolbar">
          <label>
            Channel
            <select value={rules.channel ?? ""} onChange={(event) => updateRule("channel", event.target.value)}>
              <option value="">Any</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="sms">SMS</option>
              <option value="email">Email</option>
              <option value="rcs">RCS</option>
            </select>
          </label>
          <label>
            City
            <input value={rules.city ?? ""} onChange={(event) => updateRule("city", event.target.value)} placeholder="Mumbai" />
          </label>
          <label>
            Loyalty
            <select value={rules.loyalty_tier ?? ""} onChange={(event) => updateRule("loyalty_tier", event.target.value)}>
              <option value="">Any</option>
              <option value="bronze">Bronze</option>
              <option value="silver">Silver</option>
              <option value="gold">Gold</option>
              <option value="platinum">Platinum</option>
            </select>
          </label>
          <label>
            Tag
            <input value={rules.tag ?? ""} onChange={(event) => updateRule("tag", event.target.value)} placeholder="coffee" />
          </label>
        </div>
        <div className="toolbar">
          <label>
            Min spend
            <input type="number" value={rules.min_lifetime_value ?? ""} onChange={(event) => updateRule("min_lifetime_value", numberOrBlank(event.target.value))} />
          </label>
          <label>
            Last order after
            <input type="number" value={rules.min_last_order_days_ago ?? ""} onChange={(event) => updateRule("min_last_order_days_ago", numberOrBlank(event.target.value))} />
          </label>
          <label>
            Last order before
            <input type="number" value={rules.max_last_order_days_ago ?? ""} onChange={(event) => updateRule("max_last_order_days_ago", numberOrBlank(event.target.value))} />
          </label>
          <div className="actions">
            <button className="button secondary" onClick={() => preview()}>Preview</button>
            <button className="button" onClick={saveSegment}><Save size={18} />Save</button>
          </div>
        </div>
        <div className="row">
          <strong>Rules</strong>
          <p className="muted">{ruleSummary}</p>
        </div>
      </section>

      <section className="panel grid">
        <h2>AI Segment Builder</h2>
        <label>
          Describe who to target
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <button className="button" onClick={buildWithAi}><Sparkles size={18} />Generate Segment</button>
        <p className="muted">{status || "Preview or generate a segment to see audience size."}</p>
        <div className="split-list">
          {audience.slice(0, 5).map((customer) => (
            <div className="row" key={customer.id}>
              <strong>{customer.name}</strong>
              <p className="muted">{customer.city} · {customer.loyalty_tier} · {customer.last_order_days_ago ?? "no"} days since last order</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel full-span">
        <h2>Saved Segments</h2>
        <div className="grid three">
          {segments.length ? segments.map((segment) => (
            <article className="row" key={segment.id}>
              <strong>{segment.name}</strong>
              <p className="muted">{segment.audience_size} customers</p>
              <div className="chips">
                {Object.entries(segment.rules).map(([key, value]) => <span className="chip" key={key}>{key}: {String(value)}</span>)}
              </div>
            </article>
          )) : <p className="muted">No saved segments yet.</p>}
        </div>
      </section>
    </div>
  );
}

function numberOrBlank(value: string) {
  return value === "" ? "" : Number(value);
}

function rulesFromPrompt(prompt: string): SegmentRules {
  const lower = prompt.toLowerCase();
  const next: SegmentRules = { ...emptyRules };
  if (lower.includes("loyal") || lower.includes("high value") || lower.includes("vip")) {
    next.min_lifetime_value = 5000;
  }
  if (lower.includes("inactive") || lower.includes("stopped") || lower.includes("lapsed") || lower.includes("recently")) {
    next.min_last_order_days_ago = lower.includes("recently") ? 30 : 60;
  }
  if (lower.includes("coffee")) next.tag = "coffee";
  if (lower.includes("festive")) next.tag = "festive";
  if (lower.includes("premium")) next.tag = "premium";
  if (lower.includes("email")) next.channel = "email";
  else if (lower.includes("whatsapp")) next.channel = "whatsapp";
  else if (lower.includes("rcs")) next.channel = "rcs";
  else next.channel = "sms";
  return next;
}

function summarizeRules(rules: SegmentRules) {
  const entries = Object.entries(rules).filter(([, value]) => value !== undefined && value !== "");
  if (!entries.length) return "All customers";
  return entries.map(([key, value]) => `${key} = ${value}`).join(" AND ");
}
