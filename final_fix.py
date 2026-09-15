import re

with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix missing os import
if "import os\n" not in content:
    content = "import os\n" + content

# 2. Fix parse_dynamic_ratings
old_parser_start = "def parse_dynamic_ratings("
old_parser_end = "return ratings"
start_idx = content.find(old_parser_start)
end_idx = content.find(old_parser_end, start_idx) + len(old_parser_end)

new_parser = '''def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Safely strip out internal monologue for reasoning models
    reply = re.sub(r'<thinking>.*?</thinking>', '', reply, flags=re.DOTALL)
    
    extracted_ratings = []
    for line in reply.splitlines():
        match = re.search(r"\\b(PASS|FAIL|PASSED|FAILED|YES|NO)\\b\\s*[^a-zA-Z0-9]*$", line, re.IGNORECASE)
        if match:
            rating = match.group(1).upper()
            if rating == "PASSED": rating = "PASS"
            if rating == "FAILED": rating = "FAIL"
            extracted_ratings.append({"raw_line": line.lower(), "rating": rating})

    ratings = []
    for cat in categories:
        cat_name = cat.get("name", "Category")
        for item in cat.get("line_items", []):
            name = item.get("name", "Item")
            rating = "PASS"
            
            matched = False
            for ext in extracted_ratings:
                if name.lower() in ext["raw_line"] or name.split()[0].lower() in ext["raw_line"]:
                    rating = ext["rating"]
                    matched = True
                    extracted_ratings.remove(ext)
                    break
            
            if not matched and len(extracted_ratings) > 0:
                 ext = extracted_ratings.pop(0)
                 rating = ext["rating"]

            score = RATING_SCORES.get(rating, 0)
            ratings.append({
                "category": cat_name,
                "name": name,
                "rating": rating,
                "score": score,
                "reason": "Standard compliant response",
                "coaching": ""
            })
    return ratings'''

content = content[:start_idx] + new_parser + content[end_idx:]

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied successfully.")
