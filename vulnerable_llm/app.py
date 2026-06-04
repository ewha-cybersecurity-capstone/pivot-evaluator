import httpx
from fastapi import FastAPI, HTTPException
from typing import Any, Dict
import uuid
import time

from schemas import GenerateRequest, GenerateResponse
from config import settings
from client import OllamaClient
from vuln import build_vulnerable_messages
from logging_utils import append_jsonl


app = FastAPI(title="Vulnerable LLM API", version="0.1.0")

ollama = OllamaClient(
    base_url=settings.OLLAMA_BASE_URL,
    timeout_sec=settings.OLLAMA_TIMEOUT_SEC,
)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "time": int(time.time()),
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "ollama_model": settings.OLLAMA_MODEL,
        "default_temperature": settings.DEFAULT_TEMPERATURE,
        "default_max_tokens": settings.DEFAULT_MAX_TOKENS,
        "log_dir": settings.LOG_DIR,
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    temperature = settings.DEFAULT_TEMPERATURE

    max_tokens = settings.DEFAULT_MAX_TOKENS
    if req.params and req.params.max_tokens is not None:
        try:
            requested = int(req.params.max_tokens)
            requested = max(1, requested)
            max_tokens = min(requested, settings.MAX_MAX_TOKENS)
        except Exception:
            max_tokens = settings.DEFAULT_MAX_TOKENS

    messages = build_vulnerable_messages(prompt=prompt, context=req.context)

    try:
        text, meta = await ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama HTTP error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {type(e).__name__}: {e}")

    request_id = str(uuid.uuid4())

    record = {
        "seed_id": req.seed_id,
        "bucket_id": req.bucket_id,
        "mutated_prompt": prompt, 
        "model_output": text,     
        "triggers": req.triggers,   
    }

    append_jsonl(settings.LOG_DIR, "vuln_results.jsonl", record)

    return GenerateResponse(
        response=text,
        meta={
            "request_id": request_id,
            **meta,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )