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
from src.services.dynamic_evaluator import preview_evaluation_prompt, evaluate_interaction

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
    start_time_sec: Optional[int] = 0
    sentiment_score: Optional[float] = 0.0

class EvaluateRequest(BaseModel):
    transcript: Union[List[Turn], str]
    criteria_data: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = "default"
    tenantId: Optional[str] = None
    channel: Optional[str] = "Call"
    agent_name: Optional[str] = "Agent"
    custom_prompt: Optional[str] = None
    customer_name: Optional[str] = None
    caller: Optional[str] = None

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
    tenant_id = req.tenantId or req.tenant_id or "default"
    customer_name = req.customer_name or req.caller
    
    if not criteria_data:
        config_url = os.getenv("CONFIG_API_URL", "http://localhost:8006/api/criteria/")
        try:
            resp = requests.get(f"{config_url}{tenant_id}", timeout=5)
            if resp.status_code == 200:
                criteria_data = resp.json()
            else:
                criteria_data = {}
        except Exception as e:
            print(f"Warning: Could not fetch config for {tenant_id}: {e}")
            criteria_data = {}

    transcript_payload = [t.dict() for t in req.transcript] if isinstance(req.transcript, list) else req.transcript

    # Execute evaluation directly in-process
    result = evaluate_interaction(
        transcript_data=transcript_payload,
        criteria_data=criteria_data,
        tenant_id=tenant_id,
        channel=req.channel or "Call",
        custom_prompt=req.custom_prompt,
        caller=customer_name
    )

    eval_id = str(uuid.uuid4())
    result["evaluation_id"] = eval_id

    return {
        "status": "completed",
        "result": result
    }

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
    port = int(os.getenv("SERVER_PORT", "8005"))
    uvicorn.run(app, host=host, port=port)

