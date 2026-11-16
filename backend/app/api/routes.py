import os
from pydantic import BaseModel
from typing import List, Dict, Any
from app.services.customer_chat import answer_customer
from collections import Counter
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.entities import Customer, Signal, Engagement, Escalation, AuditLog, Transaction, AIDecision
from app.services.pipeline_service import run_pipeline
from app.rules.engine import derive_signals, channel_scores

router = APIRouter(prefix="/api")


def cdict(c):
    return {
        k: getattr(c, k)
        for k in [
            "customer_id", "age", "city", "occupation", "customer_segment",
            "monthly_income_inr", "preferred_channel", "preferred_contact_hour",
            "app_usage_frequency", "marketing_opt_out", "cooldown_active",
            "existing_products", "approx_account_balance_inr", "record_type",
        ]
    }


def sdict(s):
    return {
        k: getattr(s, k)
        for k in [
            "signal_id", "customer_id", "snapshot_date", "spending_change_pct",
            "savings_contribution_change_pct", "app_login_change_pct",
            "unusual_withdrawal_flag", "detected_signal_summary", "inferred_life_event",
            "inference_confidence", "sensitivity_level", "label_status", "data_status",
        ]
    }


def edict(e):
    return {
        k: getattr(e, k)
        for k in [
            "engagement_id", "customer_id", "created_at", "trigger_type",
            "recommended_next_best_action", "selected_channel", "scheduled_hour",
            "delivery_status", "suppression_reason", "opened", "clicked", "converted",
            "human_escalation_required", "data_status",
        ]
    }


def tdict(t):
    return {
        k: getattr(t, k)
        for k in [
            "transaction_id", "customer_id", "transaction_datetime", "merchant_category",
            "merchant_label", "amount_inr", "transaction_type", "channel", "is_recurring",
        ]
    }


def decision_dict(d):
    return {
        "id": d.id,
        "customer_id": d.customer_id,
        "final_status": d.final_status,
        "priority": d.priority,
        "confidence": d.confidence,
        "action": d.action,
        "channel": d.channel,
        "message": d.message,
        "created_at": d.created_at,
    }


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/customers")
def customers(
    search: str = "",
    risk: str = "",
    segment: str = "",
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(Customer)
    if search:
        term = f"%{search}%"
        q = q.filter(
            (Customer.customer_id.ilike(term))
            | (Customer.city.ilike(term))
            | (Customer.occupation.ilike(term))
            | (Customer.customer_segment.ilike(term))
        )
    if segment:
        q = q.filter(Customer.customer_segment == segment)

    rows = q.limit(min(max(limit, 1), 5000)).all()
    result = []
    for customer in rows:
        signal = (
            db.query(Signal)
            .filter_by(customer_id=customer.customer_id)
            .order_by(Signal.snapshot_date.desc())
            .first()
        )
        derived = derive_signals(sdict(signal)) if signal else []
        high = any(x["severity"] == "High" for x in derived)
        medium = any(x["severity"] == "Medium" for x in derived)
        priority = "High" if high else "Medium" if medium else "Low"
        if risk and priority.lower() != risk.lower():
            continue
        result.append(
            {
                **cdict(customer),
                "risk_level": priority,
                "derived_signals": derived,
                "latest_signal": sdict(signal) if signal else None,
            }
        )
    return result


@router.get("/customers/{customer_id}")
def customer(customer_id: str, db: Session = Depends(get_db)):
    customer_row = db.query(Customer).filter_by(customer_id=customer_id).first()
    if not customer_row:
        raise HTTPException(404, "Customer not found")

    signals = (
        db.query(Signal)
        .filter_by(customer_id=customer_id)
        .order_by(Signal.snapshot_date.desc())
        .all()
    )
    transactions = (
        db.query(Transaction)
        .filter_by(customer_id=customer_id)
        .order_by(Transaction.transaction_datetime.desc())
        .limit(100)
        .all()
    )
    engagements = (
        db.query(Engagement)
        .filter_by(customer_id=customer_id)
        .order_by(Engagement.created_at.desc())
        .limit(50)
        .all()
    )
    decisions = (
        db.query(AIDecision)
        .filter_by(customer_id=customer_id)
        .order_by(AIDecision.created_at.desc())
        .limit(20)
        .all()
    )

    latest_signal = sdict(signals[0]) if signals else None
    return {
        "customer": cdict(customer_row),
        "signals": [sdict(x) for x in signals],
        "derived_signals": derive_signals(latest_signal) if latest_signal else [],
        "transactions": [tdict(x) for x in transactions],
        "engagements": [edict(x) for x in engagements],
        "decisions": [decision_dict(x) for x in decisions],
        "channel_scores": channel_scores(cdict(customer_row), [edict(x) for x in engagements]),
    }


@router.get("/signals")
def signals(db: Session = Depends(get_db)):
    rows = db.query(Signal).order_by(Signal.snapshot_date.desc()).limit(500).all()
    return [
        {**sdict(row), "derived_signals": derive_signals(sdict(row))}
        for row in rows
    ]


async def run_for_customer(customer_id: str, db: Session):
    customer_row = db.query(Customer).filter_by(customer_id=customer_id).first()
    if not customer_row:
        raise HTTPException(404, "Customer not found")

    signals_rows = (
        db.query(Signal)
        .filter_by(customer_id=customer_id)
        .order_by(Signal.snapshot_date.desc())
        .limit(5)
        .all()
    )
    transaction_rows = (
        db.query(Transaction)
        .filter_by(customer_id=customer_id)
        .order_by(Transaction.transaction_datetime.desc())
        .limit(100)
        .all()
    )
    engagement_rows = (
        db.query(Engagement)
        .filter_by(customer_id=customer_id)
        .order_by(Engagement.created_at.desc())
        .limit(50)
        .all()
    )

    return await run_pipeline(
        db,
        cdict(customer_row),
        [sdict(x) for x in signals_rows],
        [tdict(x) for x in transaction_rows],
        [edict(x) for x in engagement_rows],
    )


@router.post("/analyze/{customer_id}")
async def analyze(customer_id: str, db: Session = Depends(get_db)):
    return await run_for_customer(customer_id, db)


@router.post("/run-pipeline/{customer_id}")
async def pipeline(customer_id: str, db: Session = Depends(get_db)):
    return await run_for_customer(customer_id, db)


@router.get("/decisions")
def decisions(db: Session = Depends(get_db)):
    rows = db.query(AIDecision).order_by(AIDecision.created_at.desc()).limit(200).all()
    return [decision_dict(row) for row in rows]


@router.get("/engagements")
def engagements(db: Session = Depends(get_db)):
    rows = db.query(Engagement).order_by(Engagement.created_at.desc()).limit(500).all()
    return [edict(row) for row in rows]


@router.get("/escalations")
def escalations(db: Session = Depends(get_db)):
    rows = db.query(Escalation).order_by(Escalation.id.desc()).limit(200).all()
    return [
        {
            k: getattr(row, k)
            for k in ["case_id", "customer_id", "priority", "reason", "confidence", "assigned_to", "status", "created_at"]
        }
        for row in rows
    ]


@router.get("/audit-logs")
def audit(db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(500).all()
    return [
        {
            k: getattr(row, k)
            for k in ["timestamp", "customer_id", "signal", "agent", "decision", "confidence", "channel", "suppression_reason", "escalation", "final_action"]
        }
        for row in rows
    ]


@router.get("/analytics")
def analytics(db: Session = Depends(get_db)):
    customers_rows = db.query(Customer).all()
    signal_rows = db.query(Signal).all()
    engagement_rows = db.query(Engagement).all()
    decisions_rows = db.query(AIDecision).all()

    signal_distribution = Counter()
    risk_distribution = Counter()
    segment_distribution = Counter()
    decision_status_distribution = Counter()

    for row in signal_rows:
        for item in derive_signals(sdict(row)):
            signal_distribution[item["type"]] += 1

    signal_by_customer = {row.customer_id: row for row in signal_rows}
    for row in customers_rows:
        derived = derive_signals(sdict(signal_by_customer[row.customer_id])) if row.customer_id in signal_by_customer else []
        risk = "High" if any(x["severity"] == "High" for x in derived) else "Medium" if any(x["severity"] == "Medium" for x in derived) else "Low"
        risk_distribution[risk] += 1
        segment_distribution[row.customer_segment] += 1

    for row in decisions_rows:
        decision_status_distribution[row.final_status] += 1

    channels = []
    for channel in ["Mobile App Push", "Email", "SMS", "WhatsApp"]:
        sent = sum(1 for row in engagement_rows if row.selected_channel == channel)
        opened = sum(1 for row in engagement_rows if row.selected_channel == channel and row.opened)
        clicked = sum(1 for row in engagement_rows if row.selected_channel == channel and row.clicked)
        converted = sum(1 for row in engagement_rows if row.selected_channel == channel and row.converted)
        channels.append(
            {
                "channel": channel,
                "sent": sent,
                "opened": opened,
                "clicked": clicked,
                "converted": converted,
                "rate": round(opened / sent * 100, 1) if sent else 0,
            }
        )

    sent = len(engagement_rows)
    opened = sum(bool(row.opened) for row in engagement_rows)
    confidence_values = [float(row.confidence) for row in decisions_rows if row.confidence is not None]

    return {
        "total_customers": len(customers_rows),
        "active_signals": len(signal_rows),
        "total_engagements": len(engagement_rows),
        "escalations": db.query(Escalation).count(),
        "engagement_rate": round(opened / sent * 100, 1) if sent else 0,
        "avg_confidence": round(sum(confidence_values) / len(confidence_values) * 100, 1) if confidence_values else 0,
        "signal_distribution": dict(signal_distribution),
        "risk_distribution": dict(risk_distribution),
        "segment_distribution": dict(segment_distribution),
        "decision_status_distribution": dict(decision_status_distribution),
        "channels": channels,
        "decisions": len(decisions_rows),
    }


@router.get("/dataset-info")
def dataset_info(db: Session = Depends(get_db)):
    return {
        "source": "data/PS22_dataset.xlsx",
        "record_type": "SYNTHETIC",
        "tables": {
            "Customers": db.query(Customer).count(),
            "Transactions": db.query(Transaction).count(),
            "Behavioral_Signals": db.query(Signal).count(),
            "Engagement_History": db.query(Engagement).count(),
        },
        "database": "SQLite",
        "loaded_from_workbook": True,
    }


@router.get("/ai-status")
def ai_status():
    from app.config import settings
    configured = bool(settings.groq_api_key and settings.ai_provider.lower() == "groq")
    return {
        "provider": "Groq",
        "model": settings.model_name,
        "mode": "Groq LLM" if configured else "Rules Fallback",
        "configured": configured,
    }
class ChatRequest(BaseModel):
    message: str
    conversation: List[Dict[str, Any]] = []

@router.post("/customers/{customer_id}/chat")
async def customer_chat(
    customer_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    customer_row = (
        db.query(Customer)
        .filter_by(customer_id=customer_id)
        .first()
    )

    if not customer_row:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    result = await answer_customer(
        customer_id=customer_id,
        message=request.message,
        conversation=request.conversation,
    )

    return result
@router.get("/mcp-status")
async def mcp_status():
    """Check the actual connection to the MCP server."""

    import os
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    server_url = os.getenv(
        "MCP_SERVER_URL",
        "http://127.0.0.1:8001/mcp"
    )

    try:
        async with streamablehttp_client(server_url) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()

                return {
                    "connected": True,
                    "transport": "Streamable HTTP",
                    "server": "PS-22 Customer Intelligence MCP Server",
                    "tools": [
                        tool.name for tool in result.tools
                    ],
                }

    except Exception as exc:
        return {
            "connected": False,
            "transport": "Streamable HTTP",
            "error": type(exc).__name__,
            "message": str(exc),
        }


@router.get("/performance")
def performance_metrics():
    """Show application-level LLM and MCP performance measurements."""

    from app.services.customer_chat import CHAT_PERFORMANCE

    requests = CHAT_PERFORMANCE["requests"]

    return {
        "mcp_chat": {
            **CHAT_PERFORMANCE,
            "average_latency_ms": round(
                CHAT_PERFORMANCE["latency_ms_total"] / requests,
                2,
            ) if requests else 0,
        },
        "optimization_features": [
            "Reusable asynchronous HTTP connection pool",
            "Limited conversation history",
            "Bounded LLM output tokens",
            "Customer-specific MCP tool access",
            "MCP session reuse within each chatbot turn",
            "Tool execution and token usage tracking",
        ],
    }