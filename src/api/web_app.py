import os
import sys
import json
import uuid
import datetime

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
for _path in [_ROOT, _SRC]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Union, Dict, Any
from celery import Celery
from celery.result import AsyncResult

from src.services.dynamic_evaluator import preview_evaluation_prompt

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery('orchestrator', broker=REDIS_URL, backend=REDIS_URL)

app = FastAPI(title="Stateless QA Service API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import requests

class Turn(BaseModel):
    speaker: str
    text: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_time_sec: Optional[int] = 0
    end_time_sec: Optional[int] = 0

class EvaluateRequest(BaseModel):
    transcript: Union[List[Turn], str]
    criteria_data: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = "default"
    channel: Optional[str] = "Call"
    agent_name: Optional[str] = "Agent"
    custom_prompt: Optional[str] = None
    customer_name: Optional[str] = None
    sentiment_scores: Optional[List[float]] = None

@app.get("/api/samples")
def list_sample_inputs():
    inputs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "inputs")
    samples = []
    if os.path.exists(inputs_dir):
        for fname in sorted(os.listdir(inputs_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(inputs_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["filename"] = fname
                        samples.append(data)
                except Exception as e:
                    print(f"Error loading sample {fname}: {e}")
    return samples

@app.post("/api/evaluate")
def evaluate_tenant_transcript(req: EvaluateRequest):
    criteria_data = req.criteria_data
    
    if not criteria_data:
        config_url = os.getenv("CONFIG_API_URL", "http://config-db:8080/api/criteria/")
        try:
            resp = requests.get(f"{config_url}{req.tenant_id}", timeout=5)
            if resp.status_code == 200:
                criteria_data = resp.json()
            else:
                criteria_data = {}
        except Exception as e:
            print(f"Warning: Could not fetch config for {req.tenant_id}: {e}")
            criteria_data = {}

    transcript_payload = [t.dict() for t in req.transcript] if isinstance(req.transcript, list) else req.transcript

    # Dispatch async task
    task = celery_app.send_task(
        'orchestrate_evaluation',
        args=[transcript_payload, criteria_data, req.tenant_id, req.channel or "Call"],
        kwargs={
            "custom_prompt": req.custom_prompt,
            "caller": req.customer_name,
            "sentiment_scores": req.sentiment_scores
        }
    )

    return {
        "job_id": task.id,
        "status": "processing",
        "created_at": datetime.datetime.utcnow().isoformat()
    }

@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    task_result = AsyncResult(job_id, app=celery_app)
    if task_result.state == 'PENDING':
        return {"status": "processing"}
    elif task_result.state == 'SUCCESS':
        result = task_result.result
        result["evaluation_id"] = job_id
        return {"status": "completed", "result": result}
    elif task_result.state == 'FAILURE':
        return {"status": "failed", "error": str(task_result.info)}
    else:
        return {"status": task_result.state}

@app.post("/api/preview-prompt")
def preview_tenant_prompt(req: EvaluateRequest):
    criteria_data = req.criteria_data or {}
    preview = preview_evaluation_prompt(
        transcript_text=req.transcript,
        criteria_data=criteria_data,
        tenant_id="default",
        channel=req.channel or "Call"
    )
    return preview

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

