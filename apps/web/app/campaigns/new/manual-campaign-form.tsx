"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle, Database, ExternalLink, Save, Send } from "lucide-react";
import { Campaign, CLIENT_API_BASE, Segment } from "../../../lib/api";

const defaultMessage = "Hi {{name}}, we miss you. Enjoy 20% off your next order this weekend.";

export function ManualCampaignForm() {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedSegmentId, setSelectedSegmentId] = useState("");
  const [name, setName] = useState("Weekend Winback Campaign");
  const [goal, setGoal] = useState("Bring inactive shoppers back with a limited-time offer.");
  const [channel, setChannel] = useState("sms");
  const [message, setMessage] = useState(defaultMessage);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [status, setStatus] = useState("");

  const selectedSegment = useMemo(
    () => segments.find((segment) => segment.id === selectedSegmentId),
    [segments, selectedSegmentId],
  );

  useEffect(() => {
    loadSegments();
  }, []);

  async function loadSegments() {
    try {
      const response = await fetch(`${CLIENT_API_BASE}/segments`);
      const data = response.ok ? await response.json() as Segment[] : [];
      setSegments(data);
      const preferred = data.find((segment) => segment.audience_size > 0) ?? data[0];
      if (preferred) {
        setSelectedSegmentId(preferred.id);
        if (preferred.rules.channel) setChannel(preferred.rules.channel);
      }
      return data;
    } catch {
      setSegments([]);
      return [];
    }
  }

  useEffect(() => {
    if (selectedSegment?.rules.channel) setChannel(selectedSegment.rules.channel);
  }, [selectedSegment]);

  async function createDraft() {
    if (!selectedSegment) {
      setStatus("Save a segment before creating a manual draft.");
      return;
    }
    if (selectedSegment.audience_size === 0) {
      setStatus("This segment has 0 customers. Seed demo data or choose an audience with matching customers.");
      return;
    }
    setStatus("Creating draft...");
    const response = await fetch(`${CLIENT_API_BASE}/campaigns`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name,
        goal,
        channel,
        segment_rules: { ...selectedSegment.rules, channel },
        message_template: message,
        approved_plan: {
          source: "manual",
          segment_name: selectedSegment.name,
          audience_size: selectedSegment.audience_size,
        },
      }),
    });
    if (!response.ok) {
      setStatus("Draft creation failed. Check channel and segment rules.");
      return;
    }
    const result = await response.json() as Campaign;
    setCampaign(result);
    setStatus("Draft created. Approval is required before sending.");
  }

  async function createDefaultSegment() {
    setStatus("Creating default winback segment...");
    const response = await fetch(`${CLIENT_API_BASE}/segments`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name: "Inactive SMS Shoppers",
        rules: { channel: "sms", min_last_order_days_ago: 60 },
      }),
    });
    if (!response.ok) {
      setStatus("Default segment creation failed. Seed customers first or create a segment manually.");
      return;
    }

    const result = await response.json() as Segment;
    setSegments((current) => [result, ...current]);
    setSelectedSegmentId(result.id);
    if (result.rules.channel) setChannel(result.rules.channel);
    setStatus(`Default segment saved with ${result.audience_size} customers. You can create the draft now.`);
  }

  async function seedDemoData() {
    setStatus("Seeding demo customers, orders, segments, and campaigns...");
    const response = await fetch(`${CLIENT_API_BASE}/seed`, { method: "POST" });
    if (!response.ok) {
      setStatus("Seed failed. Check that the API is running.");
      return;
    }
    const data = await loadSegments();
    const preferred = data.find((segment) => segment.audience_size > 0);
    setStatus(preferred ? `Demo data seeded. Selected ${preferred.name} with ${preferred.audience_size} customers.` : "Demo data seeded, but no matching audience was found.");
  }

  async function approveAndSend() {
    if (!campaign) return;
    setStatus("Approving and queueing sends...");
    const approveResponse = await fetch(`${CLIENT_API_BASE}/campaigns/${campaign.id}/approve`, {
      method: "POST",
      headers: { "content-type": "application/json" },
    });
    if (!approveResponse.ok) {
      setStatus("Approval failed. Only draft campaigns can be approved.");
      return;
    }

    const sendResponse = await fetch(`${CLIENT_API_BASE}/campaigns/${campaign.id}/send`, {
      method: "POST",
      headers: { "content-type": "application/json" },
    });
    if (!sendResponse.ok) {
      setStatus("Send failed. Check that the worker and Redis are running.");
      return;
    }

    setStatus("Approved and queued. Open the campaign to watch fake channel callbacks.");
  }

  return (
    <section className="panel grid">
      <h2>Manual Campaign</h2>
      <div className="grid two">
        <label>
          Campaign name
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          Audience
          <select value={selectedSegmentId} onChange={(event) => setSelectedSegmentId(event.target.value)}>
            <option value="">Choose saved segment</option>
            {segments.map((segment) => (
              <option value={segment.id} key={segment.id}>{segment.name} ({segment.audience_size})</option>
            ))}
          </select>
          {!segments.length ? (
            <button type="button" className="button secondary" onClick={createDefaultSegment} style={{ marginTop: 8 }}>
              <Save size={18} />Create Default Segment
            </button>
          ) : null}
          {selectedSegment?.audience_size === 0 ? (
            <button type="button" className="button secondary" onClick={seedDemoData} style={{ marginTop: 8 }}>
              <Database size={18} />Seed Demo Data
            </button>
          ) : null}
        </label>
      </div>
      <div className="grid two">
        <label>
          Channel
          <select value={channel} onChange={(event) => setChannel(event.target.value)}>
            <option value="whatsapp">WhatsApp</option>
            <option value="sms">SMS</option>
            <option value="email">Email</option>
            <option value="rcs">RCS</option>
          </select>
        </label>
        <label>
          Goal
          <input value={goal} onChange={(event) => setGoal(event.target.value)} />
        </label>
      </div>
      <label>
        Message
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} />
      </label>
      <div className="actions">
        <button className="button" onClick={createDraft}><CheckCircle size={18} />Create Draft</button>
        {campaign ? (
          <>
            <button className="button" onClick={approveAndSend}><Send size={18} />Approve & Send</button>
            <a className="button secondary" href={`/campaigns/${campaign.id}`}><ExternalLink size={18} />Open Campaign</a>
          </>
        ) : null}
      </div>
      <p className="muted">{status || "Manual drafts still require approval before sending."}</p>
    </section>
  );
}
