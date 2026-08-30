import asyncio
import httpx
from scripts.evaluations import EvaluationContext
from scripts.evaluations.llm import LLMEvaluator
import scripts.evaluations.llm as module

def test_500_reintenta_y_acaba_inconcluso(monkeypatch):
    attempts = 0
    def handler(request):
        nonlocal attempts; attempts += 1
        return httpx.Response(500, request=request)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await LLMEvaluator("¿Útil?").evaluate(EvaluationContext(response="x", client=client))
    monkeypatch.setattr(module, "_RETRY_BACKOFF_SECONDS", 0)
    result = asyncio.run(run())
    assert attempts == 3 and result.inconclusive and result.status == "INCONCLUSIVE"

def test_veredicto_no_interpretable_no_reintenta():
    attempts = 0
    def handler(request):
        nonlocal attempts; attempts += 1
        return httpx.Response(200, json={"message": {"content": "quizá"}}, request=request)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await LLMEvaluator("¿Útil?").evaluate(EvaluationContext(response="x", client=client))
    result = asyncio.run(run())
    assert attempts == 1 and result.inconclusive
