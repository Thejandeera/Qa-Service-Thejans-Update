import os
from celery import Celery

from src.services.dynamic_evaluator import evaluate_interaction

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery('orchestrator', broker=REDIS_URL, backend=REDIS_URL)

@app.task(name='orchestrate_evaluation')
def orchestrate_evaluation(transcript_text, criteria_data, tenant_id, channel, custom_prompt=None, caller=None, sentiment_scores=None):
    return evaluate_interaction(transcript_text, criteria_data, tenant_id, channel, custom_prompt=custom_prompt, caller=caller, sentiment_scores=sentiment_scores)

