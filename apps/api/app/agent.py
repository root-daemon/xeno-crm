from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .services import customer_rows, preview_segment


def build_campaign_plan(db: Session, goal: str) -> dict[str, Any]:
    rows = customer_rows(db)
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
    provider_mode = "anthropic" if settings.anthropic_api_key else "local-deterministic-fallback"

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
        "expected_audience_size": len(audience),
        "requires_approval": True,
        "model": provider_mode,
        "tool_calls": [
            {"tool": "get_customer_summary", "result": {"customers": len(rows)}},
            {"tool": "preview_segment", "args": rules, "result": {"audience_size": len(audience)}},
            {"tool": "draft_message_variants", "result": {"variants": 2}},
        ],
    }
