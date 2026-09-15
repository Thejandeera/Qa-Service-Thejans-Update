with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad_regex = r'match = re.search(r"^(?:[^:]*:\s*)?\**\b(PASS|FAIL|PASSED|FAILED|YES|NO)\b", line, re.IGNORECASE)'
good_regex = r'match = re.search(r"\b(PASS|FAIL|PASSED|FAILED|YES|NO)\b\s*[^a-zA-Z0-9]*$", line, re.IGNORECASE)'

content = content.replace(bad_regex, good_regex)

# Add a print statement to dump the LLM reply so we can see it in docker logs
print_hook = "def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:\n    print('=== RAW LLM REPLY ===\\n', reply, '\\n=====================')"
content = content.replace("def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:", print_hook)

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
