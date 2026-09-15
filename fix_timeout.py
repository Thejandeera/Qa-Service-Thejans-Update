with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad = 'c_reply = query_llm(c_prompt, label="coaching")'
good = 'c_reply = query_llm(c_prompt, label="coaching", timeout=600)'

content = content.replace(bad, good)

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
