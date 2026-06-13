"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle } from "lucide-react";
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
    fetch(`${CLIENT_API_BASE}/segments`)
      .then((response) => response.ok ? response.json() : [])
      .then((data: Segment[]) => {
        setSegments(data);
        const first = data[0];
        if (first) {
          setSelectedSegmentId(first.id);
          if (first.rules.channel) setChannel(first.rules.channel);
        }
      })
      .catch(() => setSegments([]));
  }, []);

  useEffect(() => {
    if (selectedSegment?.rules.channel) setChannel(selectedSegment.rules.channel);
  }, [selectedSegment]);

  async function createDraft() {
    if (!selectedSegment) {
      setStatus("Save a segment before creating a manual draft.");
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
        {campaign ? <a className="button secondary" href={`/campaigns/${campaign.id}`}>Open Draft</a> : null}
      </div>
      <p className="muted">{status || "Manual drafts still require approval before sending."}</p>
    </section>
  );
}
