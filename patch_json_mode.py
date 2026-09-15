with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad = 'c_reply = query_llm(c_prompt, label="coaching", timeout=1800)'
good = 'c_reply = query_llm(c_prompt, label="coaching", timeout=1800, format="json")'

content = content.replace(bad, good)

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated query_llm with format=json")
