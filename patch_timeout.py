import re

# 1. Update dynamic_evaluator.py
with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('timeout=600', 'timeout=1800')

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 2. Update llm_adapter.py
with open('src/services/llm_adapter.py', 'r', encoding='utf-8') as f:
    content2 = f.read()

bad_except = "except urllib.error.URLError as exc:"
good_except = "except (urllib.error.URLError, TimeoutError) as exc:"

content2 = content2.replace(bad_except, good_except)
content2 = content2.replace("timeout = kwargs.get('timeout', 180)", "timeout = kwargs.get('timeout', 1800)")

with open('src/services/llm_adapter.py', 'w', encoding='utf-8') as f:
    f.write(content2)

print("Timeout patched to 1800s.")
