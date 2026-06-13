from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .services import customer_detail, customer_rows, preview_segment

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency is installed in normal runtime
    OpenAI = None  # type: ignore

ALLOWED_CHANNELS = {"whatsapp", "sms", "email", "rcs"}
DEFAULT_MODEL_ID = "google/gemini-2.5-flash"
ALLOWED_MODEL_IDS = {
    "google/gemini-2.5-flash",
    "google/gemini-2.0-flash-001",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "anthropic/claude-3.5-haiku",
}
ALLOWED_RULE_KEYS = {
    "channel",
    "city",
    "loyalty_tier",
    "min_lifetime_value",
    "min_last_order_days_ago",
    "max_last_order_days_ago",
    "tag",
}


def resolve_model_id(requested_model: str | None = None) -> str:
    if requested_model in ALLOWED_MODEL_IDS:
        return requested_model
    if settings.openrouter_model in ALLOWED_MODEL_IDS:
        return settings.openrouter_model
    return DEFAULT_MODEL_ID


# Rules schema reused by the agent's segment tools and the AI segment builder.
_RULES_SCHEMA = {
    "type": "object",
    "properties": {
        "channel": {"type": "string", "enum": sorted(ALLOWED_CHANNELS)},
        "city": {"type": "string"},
        "loyalty_tier": {"type": "string"},
        "min_lifetime_value": {"type": "number"},
        "min_last_order_days_ago": {"type": "integer"},
        "max_last_order_days_ago": {"type": "integer"},
        "tag": {"type": "string"},
    },
    "additionalProperties": False,
}

AGENT_SYSTEM_PROMPT = (
    "You are a CRM campaign planning agent for a D2C brand. "
    "Plan a single outbound campaign that a human marketer must approve before send. "
    "Work in steps: first inspect the audience with the read-only tools "
    "(get_customer_summary, preview_segment, get_audience_insights), then commit your "
    "decision by calling submit_campaign_plan exactly once. "
    "Only use channels whatsapp, sms, email, rcs. Segment rules may only use channel, city, "
    "loyalty_tier, min_lifetime_value, min_last_order_days_ago, max_last_order_days_ago, tag. "
    "Use preview_segment to confirm your segment reaches a non-empty audience before submitting. "
    "Personalize message templates with {{name}}, {{city}}, or {{tier}} placeholders."
)

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_customer_summary",
            "description": "Aggregate stats across all shoppers: counts by city, loyalty tier, channel opt-ins, lapsed and high-value totals.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_segment",
            "description": "Count and sample the shoppers matched by a set of segment rules. Use this to validate audience size before submitting.",
            "parameters": {
                "type": "object",
                "properties": {"rules": _RULES_SCHEMA},
                "required": ["rules"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audience_insights",
            "description": "Retrieve the most relevant shopper profiles for a campaign goal, as short natural-language documents.",
            "parameters": {
                "type": "object",
                "properties": {"goal": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_campaign_plan",
            "description": "Commit the final, approval-gated campaign plan. Call exactly once when you are confident in the audience, channel, and message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_name": {"type": "string"},
                    "recommended_channel": {"type": "string", "enum": sorted(ALLOWED_CHANNELS)},
                    "channel_priority": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(ALLOWED_CHANNELS)},
                    },
                    "recommended_segment": {
                        "type": "object",
                        "properties": {
                            "rules": _RULES_SCHEMA,
                            "reasoning": {"type": "string"},
                        },
                        "required": ["rules", "reasoning"],
                        "additionalProperties": False,
                    },
                    "message_variants": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "template": {"type": "string"},
                            },
                            "required": ["template"],
                        },
                    },
                    "risk_notes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["campaign_name", "recommended_channel", "recommended_segment", "message_variants"],
                "additionalProperties": False,
            },
        },
    },
]

MAX_AGENT_STEPS = 6


def build_campaign_plan(db: Session, goal: str, requested_model: str | None = None) -> dict[str, Any]:
    model_id = resolve_model_id(requested_model)
    rows = customer_rows(db)
    insights = deterministic_insights(goal, rows)
    fallback_plan = build_local_plan(db, goal, rows, insights)

    if not settings.openrouter_api_key or OpenAI is None:
        return _finalize_fallback(fallback_plan, rows, insights, model_id=None)

    try:
        return run_agent_loop(db, goal, rows, model_id, fallback_plan)
    except Exception as exc:
        plan = _finalize_fallback(fallback_plan, rows, insights, model_id=model_id)
        plan["validation_errors"] = [str(exc)]
        plan["tool_calls"] = [
            {"tool": "openrouter_agent", "model": model_id, "result": {"status": "failed", "error": str(exc)}},
            *plan["tool_calls"],
        ]
        return plan


def refine_campaign_plan(
    db: Session,
    prior_plan: dict[str, Any],
    instruction: str,
    requested_model: str | None = None,
) -> dict[str, Any]:
    base_goal = str(prior_plan.get("goal") or prior_plan.get("campaign_name") or "Refine this CRM campaign")
    refined_goal = (
        f"{base_goal}\n\nExisting approved-shape plan JSON:\n"
        f"{json.dumps(prior_plan, default=str)[:5000]}\n\n"
        f"Marketer refinement instruction: {instruction}\n\n"
        "Return a complete replacement plan, not a patch."
    )
    return build_campaign_plan(db, refined_goal, requested_model)


def personalize_message(
    db: Session,
    campaign_id: str,
    customer_id: str,
    template: str,
    goal: str,
    channel: str,
    variant_label: str | None = None,
    requested_model: str | None = None,
) -> dict[str, Any]:
    customer = customer_detail(db, customer_id)
    if not customer:
        raise ValueError(f"unknown customer_id: {customer_id}")
    fallback = local_personalized_message(template, customer, goal, channel, variant_label)
    model_id = resolve_model_id(requested_model)

    if not settings.openrouter_api_key or OpenAI is None:
        return {"message": fallback, "model": "local-deterministic-fallback", "fallback": True}

    try:
        message = call_openrouter_personalization(customer, template, goal, channel, variant_label, model_id)
        return {"message": sanitize_message(message, fallback), "model": model_id, "fallback": False}
    except Exception as exc:
        return {
            "message": fallback,
            "model": f"{model_id}-fallback",
            "fallback": True,
            "error": str(exc),
        }


def local_personalized_message(
    template: str,
    customer: dict[str, Any],
    goal: str,
    channel: str,
    variant_label: str | None = None,
) -> str:
    message = (
        template.replace("{{name}}", str(customer["name"]).split(" ")[0])
        .replace("{{city}}", str(customer["city"]))
        .replace("{{tier}}", str(customer["loyalty_tier"]))
    )
    tags = ", ".join(customer.get("tags") or [])
    if tags and len(message) < 220:
        message = f"{message} Picked around your {tags.split(', ')[0]} interest."
    last_order = customer.get("last_order_days_ago")
    if last_order is not None and int(last_order) >= 45 and len(message) < 240:
        message = f"{message} It has been {last_order} days since your last order."
    if variant_label and len(message) < 260:
        message = f"{message} [{variant_label}]"
    return sanitize_message(message, template)


def call_openrouter_personalization(
    customer: dict[str, Any],
    template: str,
    goal: str,
    channel: str,
    variant_label: str | None,
    model_id: str,
) -> str:
    client = OpenAI(  # type: ignore[operator]
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    response = client.chat.completions.create(
        model=model_id,
        max_tokens=180,
        temperature=0.35,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Write one concise CRM outbound message for exactly one shopper. "
                    "Return only JSON: {\"message\":\"...\"}. Do not invent discounts, "
                    "links, personal data, or claims not present in the input. Keep placeholders resolved."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "goal": goal,
                    "channel": channel,
                    "variant_label": variant_label,
                    "base_template": template,
                    "customer": {
                        "name": customer["name"],
                        "city": customer["city"],
                        "loyalty_tier": customer["loyalty_tier"],
                        "tags": customer.get("tags", []),
                        "lifetime_value": customer.get("lifetime_value", 0),
                        "last_order_days_ago": customer.get("last_order_days_ago"),
                        "purchase_history": order_rows_for_prompt(customer),
                    },
                }),
            },
        ],
    )
    text = response.choices[0].message.content
    if not text:
        raise ValueError("personalization response did not include content")
    payload = json.loads(text)
    if not isinstance(payload, dict) or not payload.get("message"):
        raise ValueError("personalization response missing message")
    return str(payload["message"])


def order_rows_for_prompt(customer: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "total": item.get("total"),
            "items": item.get("items", []),
            "channel": item.get("channel"),
            "days_ago": item.get("days_ago"),
        }
        for item in (customer.get("purchase_history") or [])[:5]
    ]


def sanitize_message(message: str, fallback: str) -> str:
    cleaned = " ".join(str(message or "").split())
    if not cleaned:
        return " ".join(str(fallback).split())[:320]
    return cleaned[:320]


def _finalize_fallback(
    fallback_plan: dict[str, Any],
    rows: list[dict[str, Any]],
    insights: list[dict[str, Any]],
    model_id: str | None,
) -> dict[str, Any]:
    """Attach deterministic tool-trace + model label to the local plan."""
    base_calls = [
        {"tool": "get_customer_summary", "result": customer_summary(rows)},
        {"tool": "retrieve_audience_insights", "provider": "local", "result": {"insights": insights}},
    ]
    fallback_plan["tool_calls"] = base_calls + fallback_plan["tool_calls"]
    fallback_plan["model"] = f"{model_id}-fallback" if model_id else "local-deterministic-fallback"
    return fallback_plan


def run_agent_loop(
    db: Session,
    goal: str,
    rows: list[dict[str, Any]],
    model_id: str,
    fallback_plan: dict[str, Any],
) -> dict[str, Any]:
    client = OpenAI(  # type: ignore[operator]
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Campaign goal: {goal}\n\n"
                "Inspect the audience with the tools, then call submit_campaign_plan with the final plan."
            ),
        },
    ]

    recorded_tool_calls: list[dict[str, Any]] = []
    submitted: dict[str, Any] | None = None
    steps_used = 0

    for step in range(MAX_AGENT_STEPS):
        steps_used = step + 1
        force_submit = step == MAX_AGENT_STEPS - 1
        response = client.chat.completions.create(
            model=model_id,
            max_tokens=1200,
            temperature=0.2,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice=(
                {"type": "function", "function": {"name": "submit_campaign_plan"}}
                if force_submit
                else "auto"
            ),
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            # Model replied with prose instead of a tool call — nudge it to commit.
            messages.append({"role": "assistant", "content": message.content or ""})
            messages.append({"role": "user", "content": "Call submit_campaign_plan now with the final plan."})
            continue

        messages.append({
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in tool_calls
            ],
        })

        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch_tool(db, goal, rows, name, args)
            recorded_tool_calls.append({"tool": name, "args": args, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })
            if name == "submit_campaign_plan":
                submitted = args

        if submitted is not None:
            break

    if submitted is None:
        raise ValueError("agent did not submit a campaign plan within step budget")

    plan = normalize_plan(db, goal, submitted, fallback_plan, model_id)
    plan["model"] = model_id
    plan["tool_calls"] = recorded_tool_calls
    plan["agent_steps"] = steps_used
    return plan


def dispatch_tool(
    db: Session,
    goal: str,
    rows: list[dict[str, Any]],
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    if name == "get_customer_summary":
        return customer_summary(rows)
    if name == "preview_segment":
        rules = sanitize_rules(args.get("rules") or {})
        audience = preview_segment(db, rules)
        return {
            "rules": rules,
            "audience_size": len(audience),
            "sample": [
                {
                    "name": row["name"],
                    "city": row["city"],
                    "loyalty_tier": row["loyalty_tier"],
                    "lifetime_value": row["lifetime_value"],
                    "last_order_days_ago": row["last_order_days_ago"],
                }
                for row in audience[:5]
            ],
        }
    if name == "get_audience_insights":
        return {"insights": deterministic_insights(str(args.get("goal") or goal), rows)}
    if name == "submit_campaign_plan":
        return {"status": "received"}
    return {"error": f"unknown tool {name}"}


def generate_segment(db: Session, prompt: str, requested_model: str | None = None) -> dict[str, Any]:
    """Translate a natural-language audience description into validated segment rules."""
    model_id = resolve_model_id(requested_model)
    rows = customer_rows(db)
    fallback_rules = local_segment_rules(prompt)

    if not settings.openrouter_api_key or OpenAI is None:
        rules = fallback_rules
        reasoning = "Mapped your description to rules with a local heuristic (no AI key configured)."
        source = "local-deterministic-fallback"
    else:
        try:
            rules, reasoning = call_openrouter_segment(prompt, rows, model_id)
            source = model_id
        except Exception as exc:
            rules = fallback_rules
            reasoning = f"AI segment call failed ({exc}); used local heuristic instead."
            source = f"{model_id}-fallback"

    rules = sanitize_rules(rules)
    audience = preview_segment(db, rules)
    return {
        "rules": rules,
        "reasoning": reasoning,
        "audience_size": len(audience),
        "audience": audience[:25],
        "model": source,
    }


def call_openrouter_segment(prompt: str, rows: list[dict[str, Any]], model_id: str) -> tuple[dict[str, Any], str]:
    client = OpenAI(  # type: ignore[operator]
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    response = client.chat.completions.create(
        model=model_id,
        max_tokens=500,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You translate a marketer's audience description into CRM segment rules. "
                    "Return only JSON of shape {\"rules\": {...}, \"reasoning\": \"...\"}. "
                    "Rules may only use channel (whatsapp|sms|email|rcs), city, loyalty_tier, "
                    "min_lifetime_value, min_last_order_days_ago, max_last_order_days_ago, tag. "
                    "Omit any rule you are unsure about."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "description": prompt,
                    "customer_summary": customer_summary(rows),
                }),
            },
        ],
    )
    text = response.choices[0].message.content
    if not text:
        raise ValueError("OpenRouter segment response did not include content")
    payload = json.loads(text)
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, dict):
        raise ValueError("OpenRouter segment response missing rules object")
    reasoning = str(payload.get("reasoning") or "AI-generated segment from your description.")
    return rules, reasoning


def local_segment_rules(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    rules: dict[str, Any] = {}
    if any(word in lower for word in ["loyal", "high value", "vip"]):
        rules["min_lifetime_value"] = 5000
    if any(word in lower for word in ["inactive", "stopped", "lapsed", "recently"]):
        rules["min_last_order_days_ago"] = 30 if "recently" in lower else 60
    if "coffee" in lower:
        rules["tag"] = "coffee"
    elif "festive" in lower:
        rules["tag"] = "festive"
    elif "premium" in lower:
        rules["tag"] = "premium"
    if "email" in lower:
        rules["channel"] = "email"
    elif "whatsapp" in lower:
        rules["channel"] = "whatsapp"
    elif "rcs" in lower:
        rules["channel"] = "rcs"
    else:
        rules["channel"] = "sms"
    return rules


def build_local_plan(db: Session, goal: str, rows: list[dict[str, Any]], insights: list[dict[str, Any]]) -> dict[str, Any]:
    lower_goal = goal.lower()
    is_winback = any(word in lower_goal for word in ["win", "lapsed", "inactive", "churn", "60 days"])
    is_premium = any(word in lower_goal for word in ["premium", "vip", "best", "high value"])
    is_festive = any(word in lower_goal for word in ["festive", "wedding", "diwali", "season"])

    if is_winback:
        rules = {"channel": "sms", "min_last_order_days_ago": 60}
        name = "Lapsed Shopper Comeback"
        offer = "20% comeback reward"
    elif is_premium:
        rules = {"channel": "whatsapp", "min_lifetime_value": 7000}
        name = "VIP Early Access Drop"
        offer = "private early access"
    elif is_festive:
        rules = {"channel": "whatsapp", "tag": "festive"}
        name = "Festive Shopper Activation"
        offer = "festive styling edit"
    else:
        rules = {"channel": "whatsapp", "max_last_order_days_ago": 45}
        name = "Recent Buyer Repeat Push"
        offer = "new arrivals edit"

    audience = preview_segment(db, rules)
    message = f"Hi {{{{name}}}}, we picked a {offer} for you based on your last purchase. Use code XENO10 today."
    return {
        "campaign_name": name,
        "goal": goal,
        "recommended_segment": {
            "rules": rules,
            "reasoning": f"Matched {len(audience)} shoppers from {len(rows)} profiles using behavioral and opt-in filters.",
        },
        "recommended_channel": rules["channel"],
        "channel_priority": [rules["channel"], *[channel for channel in ["whatsapp", "sms", "email", "rcs"] if channel != rules["channel"]]],
        "message_variants": [
            {"label": "direct", "template": message},
            {"label": "softer", "template": f"Hi {{{{name}}}}, your {offer} is waiting. Explore a personalized edit picked for you."},
        ],
        "risk_notes": [
            "Requires marketer approval before send.",
            "Only opted-in shoppers are included in the segment.",
        ],
        "audience_insights": insights,
        "expected_audience_size": len(audience),
        "requires_approval": True,
        "model": "local-deterministic-fallback",
        "tool_calls": [
            {"tool": "preview_segment", "args": rules, "result": {"audience_size": len(audience)}},
            {"tool": "draft_message_variants", "result": {"variants": 2}},
        ],
    }


def normalize_plan(db: Session, goal: str, payload: dict[str, Any], fallback_plan: dict[str, Any], model_id: str) -> dict[str, Any]:
    rules = sanitize_rules(payload.get("recommended_segment", {}).get("rules") or {})
    channel = payload.get("recommended_channel") or rules.get("channel") or fallback_plan["recommended_channel"]
    if channel not in ALLOWED_CHANNELS:
        channel = fallback_plan["recommended_channel"]
    rules["channel"] = channel

    audience = preview_segment(db, rules)
    variants = sanitize_variants(payload.get("message_variants"), fallback_plan["message_variants"])
    risk_notes = payload.get("risk_notes") if isinstance(payload.get("risk_notes"), list) else fallback_plan["risk_notes"]
    channel_priority = sanitize_channel_priority(payload.get("channel_priority"), channel)

    return {
        "campaign_name": str(payload.get("campaign_name") or fallback_plan["campaign_name"])[:180],
        "goal": goal,
        "recommended_segment": {
            "rules": rules,
            "reasoning": str(payload.get("recommended_segment", {}).get("reasoning") or fallback_plan["recommended_segment"]["reasoning"]),
        },
        "recommended_channel": channel,
        "channel_priority": channel_priority,
        "message_variants": variants,
        "risk_notes": [str(note) for note in risk_notes][:5],
        "audience_insights": fallback_plan.get("audience_insights", []),
        "expected_audience_size": len(audience),
        "requires_approval": True,
        "model": model_id,
        "tool_calls": [
            {"tool": "preview_segment", "args": rules, "result": {"audience_size": len(audience)}},
            {"tool": "draft_message_variants", "result": {"variants": len(variants)}},
        ],
    }


def sanitize_rules(rules: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in rules.items():
        if key not in ALLOWED_RULE_KEYS or value in (None, ""):
            continue
        if key == "channel":
            if value in ALLOWED_CHANNELS:
                cleaned[key] = value
        elif key in {"min_last_order_days_ago", "max_last_order_days_ago"}:
            cleaned[key] = max(0, int(value))
        elif key == "min_lifetime_value":
            cleaned[key] = max(0, float(value))
        else:
            cleaned[key] = str(value)
    return cleaned


def sanitize_variants(raw_variants: Any, fallback_variants: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(raw_variants, list):
        return fallback_variants

    variants = []
    for item in raw_variants:
        if not isinstance(item, dict) or not item.get("template"):
            continue
        variants.append({
            "label": str(item.get("label") or f"variant-{len(variants) + 1}")[:40],
            "template": str(item["template"]),
        })
        if len(variants) == 3:
            break
    return variants or fallback_variants


def sanitize_channel_priority(raw_priority: Any, primary: str) -> list[str]:
    priority = [primary]
    if isinstance(raw_priority, list):
        for item in raw_priority:
            if item in ALLOWED_CHANNELS and item not in priority:
                priority.append(item)
    for item in ["whatsapp", "sms", "email", "rcs"]:
        if item not in priority:
            priority.append(item)
    return priority


def customer_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "customers": len(rows),
        "cities": count_by(rows, "city"),
        "loyalty_tiers": count_by(rows, "loyalty_tier"),
        "opt_ins": {
            "whatsapp": sum(1 for row in rows if row["whatsapp_opt_in"]),
            "sms": sum(1 for row in rows if row["sms_opt_in"]),
            "email": sum(1 for row in rows if row["email_opt_in"]),
            "rcs": sum(1 for row in rows if row["rcs_opt_in"]),
        },
        "lapsed_60_days": sum(1 for row in rows if (row["last_order_days_ago"] or 0) >= 60),
        "high_value_7000": sum(1 for row in rows if row["lifetime_value"] >= 7000),
    }


def deterministic_insights(goal: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lower_goal = goal.lower()
    if any(word in lower_goal for word in ["win", "lapsed", "inactive", "churn", "60 days"]):
        candidates = [row for row in rows if (row["last_order_days_ago"] or 0) >= 60]
    elif any(word in lower_goal for word in ["premium", "vip", "best", "high value"]):
        candidates = [row for row in rows if row["lifetime_value"] >= 7000]
    else:
        candidates = sorted(rows, key=lambda row: row["lifetime_value"], reverse=True)[:3]

    return [
        {
            "customer_id": row["id"],
            "text": customer_document(row),
            "score": 1.0,
        }
        for row in candidates[:3]
    ]


def customer_document(row: dict[str, Any]) -> str:
    tags = ", ".join(row["tags"]) if row["tags"] else "no tags"
    return (
        f"{row['name']} in {row['city']} is {row['loyalty_tier']} tier with LTV {row['lifetime_value']:.0f}, "
        f"last order {row['last_order_days_ago']} days ago, tags {tags}, "
        f"opt-ins whatsapp={row['whatsapp_opt_in']} sms={row['sms_opt_in']} email={row['email_opt_in']} rcs={row['rcs_opt_in']}."
    )


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row[key])
        counts[value] = counts.get(value, 0) + 1
    return counts
