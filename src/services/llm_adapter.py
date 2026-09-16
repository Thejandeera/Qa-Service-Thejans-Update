import os
import json
import urllib.request
import urllib.error

class BaseLLMAdapter:
    def generate(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError

class OllamaAdapter(BaseLLMAdapter):
    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.url = f"{self.host.rstrip('/')}/api/chat"
        self.model = os.getenv("LLM_MODEL", "llama3.1")

    def generate(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get('temperature', 0.1)
        num_predict = kwargs.get('num_predict', 320)
        num_ctx = kwargs.get('num_ctx', 8192)  # Max memory without crashing
        timeout = kwargs.get('timeout', 1800)
        
        payload_dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict, "num_ctx": num_ctx}
        }
        
        if kwargs.get('format') == 'json':
            payload_dict["format"] = "json"

        payload = json.dumps(payload_dict).encode("utf-8")

        req = urllib.request.Request(
            self.url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
                return data.get("message", {}).get("content", "").strip()
        except (urllib.error.URLError, TimeoutError) as exc:
            return f"Error reaching Ollama: {exc}"

def get_llm() -> BaseLLMAdapter:
    # We could check env vars here to return different adapters (e.g., vLLMAdapter)
    return OllamaAdapter()


def query_llm(prompt, **kwargs):
    return get_llm().generate(prompt, **kwargs)

def cache_prompt_prefix(prefix, **kwargs):
    return prefix

def query_llm_with_state(state, suffix, **kwargs):
    prompt = state + suffix
    return get_llm().generate(prompt, **kwargs)
