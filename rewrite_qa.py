content = '''\"\"\"PART 2: LLM writes a plain summary of the whole call.

One small LLM request -- just the summary, nothing else (keeps tokens low).
\"\"\"

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_TESTS = os.path.join(_ROOT, "tests")
for _path in [_ROOT, _SRC, _TESTS]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.services.llm_adapter import query_llm

def load_summary_prompt():
    prompt_path = os.getenv("PROMPT_SUMMARY_PATH", "resources/prompts/summary_prompt.txt")
    full_path = os.path.join(_ROOT, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

def format_transcript(transcript):
    return "\\n".join(f"{speaker}: {text}" for speaker, text in transcript)

SUMMARY_PROMPT = load_summary_prompt()

def generate_scalable_summary(transcript_text: str, evaluation_context: str = "No critical failures identified.") -> str:
    prompt = f\"\"\"<TRANSCRIPT>
{transcript_text}
</TRANSCRIPT>

<INSTRUCTIONS>
You are a highly efficient summarizer.
Read the transcript above and return ONLY a brief summary of the conversation.
CRITICAL: The summary MUST be exactly between 60 to 70 characters long.
Do not include any intro or outro text, just the summary itself.
</INSTRUCTIONS>
\"\"\"
    return query_llm(prompt, label="topic_extraction", num_predict=50)
'''

with open('src/services/qa_summary.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("qa_summary.py fixed")
