import json
from src.services.llm_adapter import query_llm
from src.services.dynamic_evaluator import build_dynamic_prompt

with open('long_failed_transcript.json', 'r') as f:
    payload = json.load(f)

categories = [{"name": "Technical Knowledge", "line_items": [{"name": "Probing", "description": "Did the agent probe?"}]}]

prefix, suffix = build_dynamic_prompt(json.dumps(payload['transcript']), categories, [], [], "Call")
prompt = prefix + suffix

reply = query_llm(prompt, label="test")
print("LLM REPLY:\n", reply)

try:
    start_idx = reply.find('[')
    end_idx = reply.rfind(']')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = reply[start_idx:end_idx+1]
        extracted = json.loads(json_str)
        print("PARSED JSON SUCCESSFULLY:", len(extracted), "items")
    else:
        print("COULD NOT FIND ARRAY BRACKETS")
except Exception as e:
    print("JSON DECODE ERROR:", e)
    print("RAW JSON STRING:", repr(json_str))
