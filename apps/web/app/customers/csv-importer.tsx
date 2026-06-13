"use client";

import { useState } from "react";
import { Upload } from "lucide-react";
import { CLIENT_API_BASE } from "../../lib/api";

type Row = Record<string, string>;

const customerRequired = ["name", "phone", "email", "city"];
const orderRequired = ["customer_id", "total", "channel", "days_ago"];

export function CsvImporter() {
  const [kind, setKind] = useState<"customers" | "orders">("customers");
  const [rows, setRows] = useState<Row[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [status, setStatus] = useState("");

  async function readFile(file: File) {
    const text = await file.text();
    const parsed = parseCsv(text);
    setRows(parsed);
    setErrors(validateRows(parsed, kind));
    setStatus(`${parsed.length} rows parsed.`);
  }

  async function upload() {
    const nextErrors = validateRows(rows, kind);
    setErrors(nextErrors);
    if (nextErrors.length) return;
    const payload = rows.map((row) => kind === "customers" ? customerPayload(row) : orderPayload(row));
    const response = await fetch(`${CLIENT_API_BASE}/ingest/${kind}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      setStatus(`Upload failed with ${response.status}`);
      return;
    }
    setStatus(`Uploaded ${rows.length} ${kind}. Refresh to see updated profiles.`);
  }

  return (
    <section className="panel grid">
      <h2><Upload size={17} /> CSV Import</h2>
      <div className="toolbar">
        <label>
          Import type
          <select value={kind} onChange={(event) => {
            const next = event.target.value as "customers" | "orders";
            setKind(next);
            setErrors(validateRows(rows, next));
          }}>
            <option value="customers">Customers</option>
            <option value="orders">Orders</option>
          </select>
        </label>
        <label>
          CSV file
          <input type="file" accept=".csv,text/csv" onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void readFile(file);
          }} />
        </label>
        <button className="button" disabled={!rows.length || !!errors.length} onClick={upload}>Upload</button>
      </div>
      <p className="muted">{status || `Required columns: ${(kind === "customers" ? customerRequired : orderRequired).join(", ")}`}</p>
      {errors.length ? <div className="row">{errors.slice(0, 5).map((error) => <p key={error}>{error}</p>)}</div> : null}
      {rows.length ? (
        <div className="table">
          <div className="table-row header">
            {Object.keys(rows[0]).slice(0, 5).map((key) => <span key={key}>{key}</span>)}
          </div>
          {rows.slice(0, 5).map((row, index) => (
            <div className="table-row" key={`${index}-${Object.values(row).join("-")}`}>
              {Object.keys(rows[0]).slice(0, 5).map((key) => <span key={key}>{row[key]}</span>)}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function parseCsv(text: string): Row[] {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  const headers = splitCsvLine(lines[0] ?? "").map((item) => item.trim());
  return lines.slice(1).map((line) => {
    const values = splitCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
  });
}

function splitCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let quoted = false;
  for (const char of line) {
    if (char === "\"") quoted = !quoted;
    else if (char === "," && !quoted) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

function validateRows(rows: Row[], kind: "customers" | "orders") {
  const required = kind === "customers" ? customerRequired : orderRequired;
  const errors: string[] = [];
  rows.forEach((row, index) => {
    for (const field of required) {
      if (!row[field]) errors.push(`Row ${index + 2}: missing ${field}`);
    }
  });
  return errors;
}

function customerPayload(row: Row) {
  return {
    id: row.id || undefined,
    name: row.name,
    phone: row.phone,
    email: row.email,
    city: row.city,
    gender: row.gender || "unknown",
    loyalty_tier: row.loyalty_tier || "bronze",
    tags: row.tags ? row.tags.split("|").map((item) => item.trim()).filter(Boolean) : [],
    whatsapp_opt_in: bool(row.whatsapp_opt_in, true),
    sms_opt_in: bool(row.sms_opt_in, true),
    email_opt_in: bool(row.email_opt_in, true),
    rcs_opt_in: bool(row.rcs_opt_in, false),
    global_opt_out: bool(row.global_opt_out, false),
    last_active_days_ago: Number(row.last_active_days_ago || 0),
  };
}

function orderPayload(row: Row) {
  return {
    id: row.id || undefined,
    customer_id: row.customer_id,
    total: Number(row.total),
    items: row.items ? row.items.split("|").map((item) => item.trim()).filter(Boolean) : [],
    channel: row.channel,
    days_ago: Number(row.days_ago),
    attributed_communication_id: row.attributed_communication_id || undefined,
    attributed_campaign_id: row.attributed_campaign_id || undefined,
  };
}

function bool(value: string | undefined, fallback: boolean) {
  if (value === undefined || value === "") return fallback;
  return ["true", "1", "yes", "y"].includes(value.toLowerCase());
}
