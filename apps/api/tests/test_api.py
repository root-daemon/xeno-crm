import json
import os
import sys
from types import SimpleNamespace
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
# Force the deterministic planner so tests never make a live OpenRouter call.
# (env vars take precedence over the .env file in pydantic-settings.)
os.environ["OPENROUTER_API_KEY"] = ""
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client.post("/seed")


def test_segment_preview_lapsed_sms():
    response = client.post("/segments/preview", json={"rules": {"channel": "sms", "min_last_order_days_ago": 60}})
    assert response.status_code == 200
    ids = sorted(customer["id"] for customer in response.json()["audience"])
    assert "cus_009" in ids
    assert "cus_012" in ids
    assert all(customer_id.startswith("cus_") for customer_id in ids)


def test_seed_creates_saved_segments_for_manual_campaigns():
    response = client.get("/segments")
    assert response.status_code == 200
    segments = response.json()
    names = {segment["name"] for segment in segments}
    assert "Inactive SMS Shoppers" in names
    assert "VIP WhatsApp Shoppers" in names
    assert any(segment["rules"] == {"channel": "sms", "min_last_order_days_ago": 60} for segment in segments)


def test_segments_can_be_saved_and_listed():
    created = client.post("/segments", json={
        "name": "Lapsed SMS Buyers",
        "rules": {"channel": "sms", "min_last_order_days_ago": 60},
    })
    assert created.status_code == 200
    payload = created.json()
    assert payload["id"].startswith("seg_")
    assert payload["name"] == "Lapsed SMS Buyers"
    assert payload["rules"] == {"channel": "sms", "min_last_order_days_ago": 60}
    assert payload["audience_size"] >= 2

    segments = client.get("/segments")
    assert segments.status_code == 200
    assert any(segment["id"] == payload["id"] for segment in segments.json())


def test_customer_detail_includes_profile_summary_and_history():
    response = client.get("/customers/cus_001")
    assert response.status_code == 200
    customer = response.json()
    assert customer["email"] == "aarav@example.com"
    assert customer["order_count"] == 2
    assert customer["lifetime_value"] == 7400
    assert customer["last_order_days_ago"] == 12
    assert len(customer["purchase_history"]) == 2
    assert "Aarav Mehta" in customer["ai_summary"]

    orders = client.get("/customers/cus_001/orders")
    assert orders.status_code == 200
    assert [order["id"] for order in orders.json()] == ["ord_001", "ord_011"]


def test_agent_plan_is_structured():
    response = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers after 60 days"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_run_id"]
    assert payload["plan"]["requires_approval"] is True
    assert payload["plan"]["recommended_channel"] == "sms"


class _FakeToolCall:
    def __init__(self, name, arguments, call_id="call_1"):
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


def _submit_plan_response(plan: dict):
    """A model turn that immediately commits the plan via the submit tool."""
    message = SimpleNamespace(content=None, tool_calls=[_FakeToolCall("submit_campaign_plan", json.dumps(plan))])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_agent_uses_openrouter_tool_plan(monkeypatch):
    from app import agent
    from app.config import settings

    plan = {
        "campaign_name": "AI VIP Push",
        "recommended_channel": "whatsapp",
        "recommended_segment": {
            "rules": {"channel": "whatsapp", "min_lifetime_value": 7000},
            "reasoning": "Prioritize high-value opted-in shoppers.",
        },
        "message_variants": [{"label": "vip", "template": "Hi {{name}}, your private edit is ready."}],
        "risk_notes": ["Requires marketer approval before send."],
    }

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            assert api_key == "test-openrouter-key"
            assert base_url == settings.openrouter_base_url
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            assert kwargs["model"] == settings.openrouter_model
            assert kwargs["tools"], "agent must expose tools for the model to call"
            return _submit_plan_response(plan)

    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)

    response = client.post("/agent/campaign-plan", json={"goal": "Reach premium VIP customers"})
    assert response.status_code == 200
    payload = response.json()["plan"]
    assert payload["model"] == settings.openrouter_model
    assert payload["campaign_name"] == "AI VIP Push"
    assert payload["recommended_segment"]["rules"] == {"channel": "whatsapp", "min_lifetime_value": 7000.0}
    assert payload["expected_audience_size"] >= 3
    # The persisted trace is the model's real tool call, not a synthesized one.
    assert any(call["tool"] == "submit_campaign_plan" for call in payload["tool_calls"])


def test_agent_explores_with_tools_before_submitting(monkeypatch):
    """The model can call read-only tools across turns, then submit."""
    from app import agent
    from app.config import settings

    plan = {
        "campaign_name": "Lapsed SMS Comeback",
        "recommended_channel": "sms",
        "recommended_segment": {
            "rules": {"channel": "sms", "min_last_order_days_ago": 60},
            "reasoning": "Target lapsed shoppers reachable on SMS.",
        },
        "message_variants": [{"label": "direct", "template": "Hi {{name}}, here is 20% off."}],
        "risk_notes": ["Requires marketer approval before send."],
    }
    turns = [
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=None,
            tool_calls=[_FakeToolCall("preview_segment", json.dumps({"rules": {"channel": "sms", "min_last_order_days_ago": 60}})),
                        _FakeToolCall("get_customer_summary", "{}", call_id="call_2")],
        ))]),
        _submit_plan_response(plan),
    ]

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=self)
            self._calls = 0

        def create(self, **kwargs):
            turn = turns[self._calls]
            self._calls += 1
            return turn

    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)

    response = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"})
    assert response.status_code == 200
    payload = response.json()["plan"]
    tools_called = [call["tool"] for call in payload["tool_calls"]]
    assert tools_called == ["preview_segment", "get_customer_summary", "submit_campaign_plan"]
    assert payload["tool_calls"][0]["result"]["audience_size"] >= 1
    assert payload["agent_steps"] == 2


def test_agent_accepts_allowed_model_selection(monkeypatch):
    from app import agent
    from app.config import settings

    selected_model = "anthropic/claude-3.5-haiku"

    plan = {
        "campaign_name": "Selected Model Push",
        "recommended_channel": "whatsapp",
        "recommended_segment": {
            "rules": {"channel": "whatsapp", "min_lifetime_value": 7000},
            "reasoning": "Prioritize high-value opted-in shoppers.",
        },
        "message_variants": [{"label": "vip", "template": "Hi {{name}}, your edit is ready."}],
        "risk_notes": ["Requires marketer approval before send."],
    }

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            assert kwargs["model"] == selected_model
            return _submit_plan_response(plan)

    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)

    response = client.post("/agent/campaign-plan", json={"goal": "Reach premium VIP customers", "model": selected_model})
    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["model"] == selected_model
    assert payload["agent_run_id"]


def test_agent_falls_back_when_no_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", None)

    response = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"})
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["model"] == "local-deterministic-fallback"
    assert plan["audience_insights"]
    retrieval_call = next(call for call in plan["tool_calls"] if call["tool"] == "retrieve_audience_insights")
    assert retrieval_call["provider"] == "local"


def test_campaign_requires_approval_before_send():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()
    response = client.post(f"/campaigns/{campaign['id']}/send")
    assert response.status_code == 409


def test_send_delegates_fanout_to_worker_queue(monkeypatch):
    from app import main

    enqueue_calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"queued": True, "job_id": "campaign.send.demo"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            enqueue_calls.append({"url": url, "json": json})
            return FakeResponse()

    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()
    client.post(f"/campaigns/{campaign['id']}/approve")

    response = client.post(f"/campaigns/{campaign['id']}/send")
    assert response.status_code == 200
    body = response.json()
    assert body["queued"] is True
    assert body["audience_size"] > 0
    assert body["job_id"] == "campaign.send.demo"

    # The API delegates fan-out to BullMQ via a single worker enqueue call.
    assert len(enqueue_calls) == 1
    assert enqueue_calls[0]["url"].endswith("/enqueue/campaign-send")
    assert enqueue_calls[0]["json"] == {"campaign_id": campaign["id"]}

    # Campaign is marked queued; the worker creates communications off the request path.
    assert client.get(f"/campaigns/{campaign['id']}").json()["status"] == "queued"


def test_send_requires_worker_and_reports_failure(monkeypatch):
    from app import main

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            raise main.httpx.ConnectError("worker unreachable")

    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()
    client.post(f"/campaigns/{campaign['id']}/approve")

    response = client.post(f"/campaigns/{campaign['id']}/send")
    assert response.status_code == 502
    assert "enqueue" in response.json()["detail"]


def test_ai_segment_endpoint_returns_validated_rules(monkeypatch):
    from app import agent
    from app.config import settings

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            content = json.dumps({
                "rules": {"channel": "sms", "min_last_order_days_ago": 60, "bogus": "drop-me"},
                "reasoning": "Lapsed SMS-reachable shoppers.",
            })
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)

    response = client.post("/agent/segment", json={"prompt": "shoppers who lapsed after 60 days on sms"})
    assert response.status_code == 200
    payload = response.json()
    # Unknown keys are sanitized away; the audience is recomputed server-side.
    assert payload["rules"] == {"channel": "sms", "min_last_order_days_ago": 60}
    assert payload["audience_size"] >= 1
    assert payload["model"] == settings.openrouter_model
    assert payload["reasoning"]


def test_ai_segment_endpoint_falls_back_without_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", None)

    response = client.post("/agent/segment", json={"prompt": "loyal customers who stopped buying recently"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "local-deterministic-fallback"
    assert payload["rules"]


def test_receipts_are_idempotent_and_order_safe():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    communication = models.Communication(
        id="msg_test",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={},
        message="Hi",
        status="sent",
    )
    db.add(communication)
    db.commit()
    db.close()

    read = {"event_id": "evt_read", "communication_id": "msg_test", "campaign_id": campaign["id"], "customer_id": "cus_009", "status": "read"}
    opened = {"event_id": "evt_opened", "communication_id": "msg_test", "campaign_id": campaign["id"], "customer_id": "cus_009", "status": "opened"}
    assert client.post("/receipts", json=read).json()["accepted"] is True
    assert client.post("/receipts", json=read).json()["accepted"] is False
    assert client.post("/receipts", json=opened).json()["status"] == "read"


def test_provider_style_receipts_are_accepted_and_counted():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    communication = models.Communication(
        id="msg_provider_style",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={},
        message="Hi",
        status="queued",
    )
    db.add(communication)
    db.commit()
    db.close()

    receipt = {
        "providerMessageId": "msg_provider_style",
        "campaign_id": campaign["id"],
        "customer_id": "cus_009",
        "status": "accepted",
        "timestamp": "2026-06-13T10:30:00Z",
    }
    assert client.post("/api/receipts", json=receipt).json()["accepted"] is True

    performance = client.get(f"/campaigns/{campaign['id']}/performance")
    assert performance.json()["counts"]["accepted"] == 1


def test_campaign_analysis_aggregates_receipt_failure_metadata():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    communication = models.Communication(
        id="msg_failure_analysis",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={"name": "Arjun Batra"},
        message="Hi",
        status="sent",
    )
    db.add(communication)
    db.commit()
    db.close()

    receipt = {
        "event_id": "evt_failure_analysis",
        "communication_id": "msg_failure_analysis",
        "campaign_id": campaign["id"],
        "customer_id": "cus_009",
        "status": "failed",
        "metadata": {"reason": "invalid_recipient", "stage": "recipient_validation", "retryable": False},
    }
    assert client.post("/receipts", json=receipt).json()["accepted"] is True

    analysis = client.get(f"/campaigns/{campaign['id']}/analysis")
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["charts"]["failure_reasons"][0]["key"] == "invalid_recipient"
    assert payload["failure_examples"][0]["label"] == "Invalid recipient"
    assert payload["summary"]["next_actions"]


def test_personalize_message_falls_back_without_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", None)
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": "Hi {{name}}, your {{tier}} offer is ready in {{city}}.",
        "approved_plan": plan["plan"],
    }).json()

    response = client.post("/agent/personalize-message", json={
        "campaign_id": campaign["id"],
        "customer_id": "cus_009",
        "template": "Hi {{name}}, your {{tier}} offer is ready in {{city}}.",
        "goal": campaign["goal"],
        "channel": campaign["channel"],
        "variant_label": "direct",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"] is True
    assert "Arjun" in payload["message"]
    assert "{{" not in payload["message"]


def test_personalize_message_uses_model(monkeypatch):
    from app import agent
    from app.config import settings

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "message": "Hi Arjun, your coffee comeback edit is ready."
            })))])

    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": "Hi {{name}}",
        "approved_plan": plan["plan"],
    }).json()

    response = client.post("/agent/personalize-message", json={
        "campaign_id": campaign["id"],
        "customer_id": "cus_009",
        "template": "Hi {{name}}",
        "goal": campaign["goal"],
        "channel": campaign["channel"],
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Hi Arjun, your coffee comeback edit is ready."
    assert response.json()["fallback"] is False


def test_refine_plan_returns_complete_approval_gated_plan(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", None)
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()["plan"]
    response = client.post("/agent/campaign-plan/refine", json={
        "prior_plan": plan,
        "instruction": "Make it punchier and prefer SMS fallback",
    })
    assert response.status_code == 200
    refined = response.json()["plan"]
    assert refined["requires_approval"] is True
    assert refined["recommended_channel"]
    assert refined["message_variants"]
    assert refined["channel_priority"]


def test_conversion_receipt_creates_attributed_order_revenue():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    db.add(models.Communication(
        id="msg_attribution",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={},
        message="Hi",
        status="clicked",
    ))
    db.commit()
    db.close()

    receipt = {
        "event_id": "evt_attr_conversion",
        "communication_id": "msg_attribution",
        "campaign_id": campaign["id"],
        "customer_id": "cus_009",
        "status": "converted",
        "metadata": {"order_value": 3499, "order_id": "ord_attr_test"},
    }
    assert client.post("/receipts", json=receipt).json()["accepted"] is True
    performance = client.get(f"/campaigns/{campaign['id']}/performance").json()
    assert performance["attribution"]["orders"] == 1
    assert performance["revenue"] == 3499


def test_campaign_performance_counts_converted_as_purchased():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    communication = models.Communication(
        id="msg_purchase",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={},
        message="Hi",
        status="converted",
        attributed_revenue=2499,
    )
    db.add(communication)
    db.commit()
    db.close()

    performance = client.get(f"/campaigns/{campaign['id']}/performance")
    assert performance.status_code == 200
    assert performance.json()["counts"]["converted"] == 1
    assert performance.json()["counts"]["purchased"] == 1


def test_seeded_draft_campaign_insights_include_audience_notes():
    response = client.get("/campaigns/cmp_seed_005/insights")
    assert response.status_code == 200
    insights = response.json()["insights"]
    assert any("Delhi is the largest reachable city" in insight for insight in insights)
    assert any("Inactivity split" in insight for insight in insights)


def test_seeded_campaign_analysis_includes_failure_charts():
    response = client.get("/campaigns/cmp_seed_001/analysis")
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["charts"]["funnel"]
    assert analysis["charts"]["failure_reasons"]
    assert analysis["charts"]["failure_by_city"]
    assert analysis["failure_examples"]


def test_invalid_segment_rules_are_rejected():
    response = client.post("/segments/preview", json={"rules": {"channel": "push", "min_last_order_days_ago": 10}})
    assert response.status_code == 422


def test_receipt_rejects_mismatched_customer_and_completes_campaign():
    plan = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"}).json()
    campaign = client.post("/campaigns", json={
        "agent_run_id": plan["agent_run_id"],
        "name": plan["plan"]["campaign_name"],
        "goal": plan["plan"]["goal"],
        "channel": plan["plan"]["recommended_channel"],
        "segment_rules": plan["plan"]["recommended_segment"]["rules"],
        "message_template": plan["plan"]["message_variants"][0]["template"],
        "approved_plan": plan["plan"],
    }).json()

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    db_campaign = db.get(models.Campaign, campaign["id"])
    db_campaign.status = models.CampaignStatus.sending.value
    communication = models.Communication(
        id="msg_complete",
        campaign_id=campaign["id"],
        customer_id="cus_009",
        channel="sms",
        recipient={},
        message="Hi",
        status="sent",
    )
    db.add(communication)
    db.commit()
    db.close()

    mismatch = {
        "event_id": "evt_bad_customer",
        "communication_id": "msg_complete",
        "campaign_id": campaign["id"],
        "customer_id": "cus_012",
        "status": "read",
    }
    assert client.post("/receipts", json=mismatch).json()["reason"] == "customer_mismatch"

    receipt = {
        "event_id": "evt_complete",
        "communication_id": "msg_complete",
        "campaign_id": campaign["id"],
        "customer_id": "cus_009",
        "status": "read",
    }
    assert client.post("/receipts", json=receipt).json()["accepted"] is True
    assert client.get(f"/campaigns/{campaign['id']}").json()["status"] == "completed"
