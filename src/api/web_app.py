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

import logging
import time
from logging.handlers import TimedRotatingFileHandler
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Union, Dict, Any
from src.services.dynamic_evaluator import preview_evaluation_prompt, evaluate_interaction

LOGS_DIR = os.path.join(_ROOT, "Logs")
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "app.log")

class DailyRotatingFileHandler(TimedRotatingFileHandler):
    """Daily rotating file handler that names backups with date: app_YYYY-MM-DD.log"""
    def __init__(self, filename, **kwargs):
        super().__init__(filename, when="midnight", interval=1, backupCount=kwargs.pop("backupCount", 30), encoding="utf-8", **kwargs)
        self.suffix = "%Y-%m-%d"
        self.namer = lambda name: name.replace("app.log.", "app_") + ".log"

# Configure uvicorn loggers and file handler
uvicorn.config.LOGGING_CONFIG["formatters"]["file_fmt"] = {
    "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S"
}
uvicorn.config.LOGGING_CONFIG["handlers"]["file"] = {
    "()": DailyRotatingFileHandler,
    "filename": LOG_FILE,
    "formatter": "file_fmt"
}
if "file" not in uvicorn.config.LOGGING_CONFIG["loggers"]["uvicorn"]["handlers"]:
    uvicorn.config.LOGGING_CONFIG["loggers"]["uvicorn"]["handlers"].append("file")
if "file" not in uvicorn.config.LOGGING_CONFIG["loggers"]["uvicorn.access"]["handlers"]:
    uvicorn.config.LOGGING_CONFIG["loggers"]["uvicorn.access"]["handlers"].append("file")

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
_app_handler = DailyRotatingFileHandler(LOG_FILE)
_app_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_app_handler)

app = FastAPI(title="Stateless QA Service API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    origin = request.headers.get("origin") or request.headers.get("host") or "unknown"
    client_ip = request.client.host if request.client else "unknown"
    
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else "<empty>"
    
    logger.info(f"[INCOMING REQUEST] [{req_id}] {request.method} {request.url.path} | Origin: {origin} | Client: {client_ip} | Body: {body_str}")
    
    try:
        response = await call_next(request)
        res_body_bytes = b""
        async for chunk in response.body_iterator:
            res_body_bytes += chunk
        res_body_str = res_body_bytes.decode("utf-8", errors="replace") if res_body_bytes else "<empty>"
        duration = f"{(time.time() - start_time) * 1000:.2f}ms"
        logger.info(f"[OUTGOING RESPONSE] [{req_id}] {request.method} {request.url.path} | Status: {response.status_code} | Duration: {duration} | Body: {res_body_str}")
        return Response(
            content=res_body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    except Exception as exc:
        duration = f"{(time.time() - start_time) * 1000:.2f}ms"
        logger.error(f"[REQUEST FAILED] [{req_id}] {request.method} {request.url.path} | Duration: {duration} | Error: {exc}", exc_info=True)
        raise

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
    logger.info(f"Starting LLM QA Analysis Web Server on http://{host}:{port}...")
    print(f"Starting LLM QA Analysis Web Server on http://{host}:{port}...")
    uvicorn.run(app, host=host, port=port)


