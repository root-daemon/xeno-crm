from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .services import customer_rows, preview_segment

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


def build_campaign_plan(db: Session, goal: str, requested_model: str | None = None) -> dict[str, Any]:
    model_id = resolve_model_id(requested_model)
    rows = customer_rows(db)
    tool_calls: list[dict[str, Any]] = [
        {"tool": "get_customer_summary", "result": customer_summary(rows)},
    ]
    insights = retrieve_audience_insights(goal, rows, tool_calls)
    fallback_plan = build_local_plan(db, goal, rows, insights)

    if not settings.openrouter_api_key:
        fallback_plan["model"] = "local-deterministic-fallback"
        fallback_plan["tool_calls"] = tool_calls + fallback_plan["tool_calls"]
        return fallback_plan

    try:
        ai_payload = call_openrouter_plan(goal, rows, insights, model_id)
        plan = normalize_plan(db, goal, ai_payload, fallback_plan, model_id)
        plan["model"] = model_id
        plan["tool_calls"] = tool_calls + [
            {"tool": "openrouter_campaign_planner", "model": model_id, "result": {"status": "validated"}},
            *plan["tool_calls"],
        ]
        plan["raw_model_response"] = ai_payload
        return plan
    except Exception as exc:
        fallback_plan["model"] = f"{model_id}-fallback"
        fallback_plan["tool_calls"] = tool_calls + [
            {"tool": "openrouter_campaign_planner", "model": model_id, "result": {"status": "failed", "error": str(exc)}},
            *fallback_plan["tool_calls"],
        ]
        fallback_plan["validation_errors"] = [str(exc)]
        return fallback_plan


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


def retrieve_audience_insights(goal: str, rows: list[dict[str, Any]], tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # OpenRouter is a chat-completion gateway with no embeddings endpoint, so
    # audience insight retrieval uses a deterministic goal-aware heuristic.
    if not rows:
        return []
    insights = deterministic_insights(goal, rows)
    tool_calls.append({
        "tool": "retrieve_audience_insights",
        "provider": "local",
        "result": {"insights": insights},
    })
    return insights


def call_openrouter_plan(goal: str, rows: list[dict[str, Any]], insights: list[dict[str, Any]], model_id: str) -> dict[str, Any]:
    client = OpenAI(  # type: ignore[operator]
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    response = client.chat.completions.create(
        model=model_id,
        max_tokens=1200,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a CRM campaign planning agent. Return only JSON. "
                    "The plan must require marketer approval and use only channels: whatsapp, sms, email, rcs. "
                    "Segment rules may only use channel, city, loyalty_tier, min_lifetime_value, "
                    "min_last_order_days_ago, max_last_order_days_ago, and tag."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "goal": goal,
                    "customer_summary": customer_summary(rows),
                    "retrieved_insights": insights,
                    "required_shape": {
                        "campaign_name": "short campaign name",
                        "recommended_segment": {"rules": {"channel": "sms"}, "reasoning": "why this segment"},
                        "recommended_channel": "sms",
                        "message_variants": [{"label": "direct", "template": "Hi {{name}}, ..."}],
                        "risk_notes": ["Requires marketer approval before send."],
                    },
                }),
            },
        ],
    )
    text = response.choices[0].message.content
    if not text:
        raise ValueError("OpenRouter response did not include content")
    return json.loads(text)


def normalize_plan(db: Session, goal: str, payload: dict[str, Any], fallback_plan: dict[str, Any], model_id: str) -> dict[str, Any]:
    rules = sanitize_rules(payload.get("recommended_segment", {}).get("rules") or {})
    channel = payload.get("recommended_channel") or rules.get("channel") or fallback_plan["recommended_channel"]
    if channel not in ALLOWED_CHANNELS:
        channel = fallback_plan["recommended_channel"]
    rules["channel"] = channel

    audience = preview_segment(db, rules)
    variants = sanitize_variants(payload.get("message_variants"), fallback_plan["message_variants"])
    risk_notes = payload.get("risk_notes") if isinstance(payload.get("risk_notes"), list) else fallback_plan["risk_notes"]

    return {
        "campaign_name": str(payload.get("campaign_name") or fallback_plan["campaign_name"])[:180],
        "goal": goal,
        "recommended_segment": {
            "rules": rules,
            "reasoning": str(payload.get("recommended_segment", {}).get("reasoning") or fallback_plan["recommended_segment"]["reasoning"]),
        },
        "recommended_channel": channel,
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

