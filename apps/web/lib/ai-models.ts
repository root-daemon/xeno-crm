export type ModelProvider = "openrouter";

export type AIModel = {
  id: string;
  label: string;
  provider: ModelProvider;
  description: string;
};

// All models are served through a single OpenRouter key. IDs are OpenRouter
// slugs. ":free" variants cost $0 (rate-limited); the others are pay-as-you-go
// pass-through pricing and only bill when explicitly selected.
export const AI_MODELS: AIModel[] = [
  {
    id: "google/gemini-2.5-flash",
    label: "Gemini 2.5 Flash",
    provider: "openrouter",
    description: "Google · reliable · ~$0.0005/plan",
  },
  {
    id: "google/gemini-2.0-flash-001",
    label: "Gemini 2.0 Flash",
    provider: "openrouter",
    description: "Google · cheapest reliable option",
  },
  {
    id: "qwen/qwen3-next-80b-a3b-instruct:free",
    label: "Qwen3 Next 80B (free)",
    provider: "openrouter",
    description: "Qwen · free · may rate-limit; falls back automatically",
  },
  {
    id: "anthropic/claude-3.5-haiku",
    label: "Claude 3.5 Haiku",
    provider: "openrouter",
    description: "Anthropic · premium · ~$0.005/plan",
  },
];

// Default to a reliable, effectively-free model (~$0.0005/plan). Free ":free"
// slugs share an upstream pool that frequently 429s, so they are offered as
// options but not the default. Any failure falls back to a deterministic plan.
export const DEFAULT_MODEL_ID = "google/gemini-2.5-flash";

export const SETTINGS_KEY = "xeno-ai-model";

export function providerLabel(_provider: ModelProvider): string {
  return "OpenRouter";
}
