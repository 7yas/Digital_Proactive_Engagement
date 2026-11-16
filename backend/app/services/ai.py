import json
import httpx
from app.config import settings


class AIService:
    def __init__(self):
        self.enabled = bool(settings.groq_api_key and settings.ai_provider.lower() == "groq")
        self.mode = "Groq LLM" if self.enabled else "Rules Fallback"

    async def _call(self, system, user):
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.model_name,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception:
            return None


async def infer_with_groq(customer, behavior, signals, engagements, fallback):
    service = AIService()
    if not service.enabled:
        return fallback

    system = (
        "You are the reasoning component of a proactive digital engagement system. "
        "Analyze observed customer behavior conservatively. Never claim a life event, "
        "financial distress, intent, or vulnerability as a fact. Return JSON only with "
        "possible_need, confidence (0 to 1), reason, sensitivity (standard or high), "
        "and evidence (array of short strings). Base the answer only on supplied data."
    )
    payload = {
        "customer": customer,
        "behavior_analysis": behavior,
        "behavioral_signals": signals,
        "recent_engagements": engagements,
    }
    result = await service._call(system, json.dumps(payload, default=str))
    if not isinstance(result, dict):
        return fallback

    try:
        confidence = max(0.0, min(1.0, float(result.get("confidence", fallback["confidence"]))))
        sensitivity = str(result.get("sensitivity", fallback["sensitivity"])).lower()
        if sensitivity not in {"standard", "high"}:
            sensitivity = fallback["sensitivity"]
        evidence = result.get("evidence", fallback.get("evidence", []))
        if not isinstance(evidence, list):
            evidence = fallback.get("evidence", [])
        return {
            "possible_need": str(result.get("possible_need", fallback["possible_need"])),
            "confidence": confidence,
            "reason": str(result.get("reason", fallback["reason"])),
            "sensitivity": sensitivity,
            "evidence": [str(x) for x in evidence[:5]],
        }
    except Exception:
        return fallback


async def message_with_groq(customer, need, action, fallback):
    service = AIService()
    if not service.enabled:
        return fallback

    system = (
        "Generate one short, respectful customer communication. Do not mention inferred "
        "financial stress or any sensitive inference as fact. Do not give financial advice. "
        "Do not pressure the customer. If the action is human review, do not generate a "
        "promotional message. Return JSON with message and tone."
    )
    payload = {"customer": customer, "inferred_need": need, "next_best_action": action}
    result = await service._call(system, json.dumps(payload, default=str))
    if isinstance(result, dict) and result.get("message"):
        return str(result["message"])
    return fallback
