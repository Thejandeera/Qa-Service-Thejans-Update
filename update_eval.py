import re
with open('src/services/dynamic_evaluator.py', 'r') as f:
    content = f.read()

old_sig = "def evaluate_interaction(\n    transcript_text: str,\n    criteria_data: Dict[str, Any],\n    tenant_id: str,\n    channel: str = "Call",\n    times: Optional[List[Optional[int]]] = None,\n    custom_prompt: Optional[str] = None\n) -> Dict[str, Any]:"
new_sig = "from typing import Union\ndef evaluate_interaction(\n    transcript_data: Union[str, List[Dict[str, Any]]],\n    criteria_data: Dict[str, Any],\n    tenant_id: str,\n    channel: str = "Call",\n    times: Optional[List[Optional[int]]] = None,\n    custom_prompt: Optional[str] = None\n) -> Dict[str, Any]:"

old_logic = ""\
