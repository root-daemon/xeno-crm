"use client";

import { useEffect, useState } from "react";
import { CheckCircle, XCircle } from "lucide-react";
import { AI_MODELS, DEFAULT_MODEL_ID, SETTINGS_KEY, providerLabel, type ModelProvider } from "../../lib/ai-models";

type KeyStatus = { openrouter: boolean };

const PROVIDERS: ModelProvider[] = ["openrouter"];

export default function SettingsPage() {
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL_ID);
  const [saved, setSaved] = useState(false);
  const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(SETTINGS_KEY);
    if (stored) setSelectedModel(stored);

    fetch("/api/ai-status")
      .then((r) => r.json())
      .then(setKeyStatus)
      .catch(() => {});
  }, []);

  function save() {
    localStorage.setItem(SETTINGS_KEY, selectedModel);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const selectedMeta = AI_MODELS.find((m) => m.id === selectedModel)!;

  return (
    <>
      <div className="topline">
        <div>
          <h1>AI Settings</h1>
          <p className="muted">Choose which AI model powers the campaign planning agent.</p>
        </div>
      </div>

      <div className="grid two" style={{ alignItems: "start" }}>
        <section className="panel grid">
          <h2 style={{ marginBottom: 4 }}>Model Selection</h2>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
            The selected model is used when you generate a campaign plan from the AI Agent page.
          </p>

          {PROVIDERS.map((provider) => (
            <div key={provider}>
              <p style={{ fontWeight: 700, fontSize: 13, marginBottom: 8, color: "var(--muted)" }}>
                {providerLabel(provider)}
              </p>
              <div className="grid" style={{ gap: 6 }}>
                {AI_MODELS.filter((m) => m.provider === provider).map((model) => (
                  <label
                    key={model.id}
                    className="row"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      cursor: "pointer",
                      border: selectedModel === model.id ? "2px solid var(--accent)" : "1px solid var(--line)",
                      padding: "12px 14px",
                    }}
                  >
                    <input
                      type="radio"
                      name="model"
                      value={model.id}
                      checked={selectedModel === model.id}
                      onChange={() => setSelectedModel(model.id)}
                      style={{ width: "auto", accentColor: "var(--accent)" }}
                    />
                    <div>
                      <div style={{ fontWeight: 600 }}>{model.label}</div>
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>{model.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          ))}

          <button className="button" onClick={save} style={{ marginTop: 8 }}>
            {saved ? "Saved!" : "Save preference"}
          </button>
          {saved && (
            <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
              Active model set to <strong>{selectedMeta.label}</strong>.
            </p>
          )}
        </section>

        <section className="panel grid" style={{ alignSelf: "start" }}>
          <h2 style={{ marginBottom: 4 }}>API Key Status</h2>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
            Keys are configured as server-side environment variables. Set them in your <code>.env</code> file or deployment dashboard.
          </p>

          {keyStatus === null ? (
            <p className="muted">Checking…</p>
          ) : (
            <div className="grid" style={{ gap: 10 }}>
              <KeyRow
                label="OPENROUTER_API_KEY"
                configured={keyStatus.openrouter}
                note="Single gateway for all models (Claude, GPT, Gemini, Llama)"
              />
            </div>
          )}

          <div className="row" style={{ marginTop: 4, fontSize: 13 }}>
            <strong style={{ display: "block", marginBottom: 4 }}>Currently active</strong>
            <p className="muted" style={{ margin: 0 }}>
              {selectedMeta.label} ({selectedMeta.provider})
            </p>
            {keyStatus && !keyStatus[selectedMeta.provider] && (
              <p style={{ color: "var(--warning)", margin: "6px 0 0", fontSize: 12 }}>
                API key for this provider is not configured. The agent will fail until you add the key.
              </p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

function KeyRow({ label, configured, note }: { label: string; configured: boolean; note: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
      {configured ? (
        <CheckCircle size={18} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 2 }} />
      ) : (
        <XCircle size={18} style={{ color: "var(--danger)", flexShrink: 0, marginTop: 2 }} />
      )}
      <div>
        <code style={{ fontSize: 12 }}>{label}</code>
        <div style={{ fontSize: 12, color: "var(--muted)" }}>{note}</div>
      </div>
    </div>
  );
}
