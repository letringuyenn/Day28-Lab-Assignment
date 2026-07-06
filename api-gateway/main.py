# api-gateway/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
import httpx, os, time

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)  # Integration 9: Prometheus

VLLM_URL = os.environ["VLLM_URL"]
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")


class ChatRequest(BaseModel):
    query: str
    embedding: list[float] = [0.0] * 384


@app.post("/api/v1/chat")
async def chat(body: ChatRequest):
    query = body.query
    start = time.time()

    # 1. Vector search — Qdrant down/timeout: tiếp tục không context thay vì chặn cả request
    context = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            search_resp = await client.post(f"{QDRANT_URL}/collections/documents/points/search", json={
                "vector": body.embedding,
                "limit": 3
            })
            search_resp.raise_for_status()
            context = search_resp.json().get("result", [])
    except httpx.HTTPError:
        pass

    # 2. LLM inference — Kaggle vLLM mất kết nối: trả 503 rõ ràng thay vì crash/500 mơ hồ
    prompt = f"Context: {context}\n\nQuery: {query}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            llm_resp = await client.post(f"{VLLM_URL}/v1/chat/completions", json={
                "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
                "messages": [{"role": "user", "content": prompt}]
            })
            llm_resp.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise HTTPException(
            status_code=503,
            detail="vLLM serving (Kaggle) không phản hồi — kiểm tra tunnel/kernel còn active không",
        ) from exc

    latency = (time.time() - start) * 1000
    result = llm_resp.json()

    return {
        "answer": result["choices"][0]["message"]["content"],
        "latency_ms": round(latency, 2),
        "model": result["model"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}
