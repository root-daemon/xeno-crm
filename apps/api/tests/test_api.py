import os
import sys
from types import SimpleNamespace
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
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


def test_agent_uses_anthropic_structured_plan(monkeypatch):
    from app import agent
    from app.config import settings

    class FakeAnthropic:
        def __init__(self, api_key):
            assert api_key == "test-anthropic-key"
            self.messages = self

        def create(self, **kwargs):
            assert kwargs["model"] == settings.anthropic_model
            return SimpleNamespace(content=[
                SimpleNamespace(text="""{
                    "campaign_name": "AI VIP Push",
                    "recommended_segment": {
                        "rules": {"channel": "whatsapp", "min_lifetime_value": 7000},
                        "reasoning": "Prioritize high-value opted-in shoppers."
                    },
                    "recommended_channel": "whatsapp",
                    "message_variants": [{"label": "vip", "template": "Hi {{name}}, your private edit is ready."}],
                    "risk_notes": ["Requires marketer approval before send."]
                }""")
            ])

    monkeypatch.setattr(settings, "anthropic_api_key", "test-anthropic-key")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(agent, "Anthropic", FakeAnthropic)

    response = client.post("/agent/campaign-plan", json={"goal": "Reach premium VIP customers"})
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["model"] == settings.anthropic_model
    assert plan["campaign_name"] == "AI VIP Push"
    assert plan["recommended_segment"]["rules"] == {"channel": "whatsapp", "min_lifetime_value": 7000.0}
    assert plan["expected_audience_size"] >= 3
    assert any(call["tool"] == "anthropic_campaign_planner" for call in plan["tool_calls"])


def test_agent_uses_openai_embeddings_for_insights(monkeypatch):
    from app import agent
    from app.config import settings

    class FakeOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-openai-key"
            self.embeddings = self

        def create(self, **kwargs):
            assert kwargs["model"] == settings.openai_embedding_model
            vectors = [[1.0, 0.0]]
            vectors.extend([[1.0, 0.0] for _ in kwargs["input"][1:]])
            return SimpleNamespace(data=[SimpleNamespace(embedding=vector) for vector in vectors])

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "openai_api_key", "test-openai-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)

    response = client.post("/agent/campaign-plan", json={"goal": "Win back lapsed shoppers"})
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["model"] == "local-deterministic-fallback"
    assert plan["audience_insights"]
    retrieval_call = next(call for call in plan["tool_calls"] if call["tool"] == "retrieve_audience_insights")
    assert retrieval_call["provider"] == "openai"
    assert retrieval_call["model"] == settings.openai_embedding_model


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
