import re

with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_func_start = "def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:"
old_func_end = "return ratings"

start_idx = content.find(old_func_start)
end_idx = content.find(old_func_end, start_idx) + len(old_func_end)

new_func = '''def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import json
    # Safely strip out internal monologue for reasoning models
    reply = re.sub(r'<thinking>.*?</thinking>', '', reply, flags=re.DOTALL)

    ratings = []
    
    # Attempt to parse JSON block from reply
    try:
        start_idx = reply.find('[')
        end_idx = reply.rfind(']')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = reply[start_idx:end_idx+1]
            extracted_ratings = json.loads(json_str)
        else:
            extracted_ratings = []
    except json.JSONDecodeError:
        extracted_ratings = []

    for cat in categories:
        cat_name = cat.get("name", "Category")
        for item in cat.get("line_items", []):
            name = item.get("name", "Item")
            rating = "PASS"
            reason = "Standard compliant response"
            coaching = ""

            matched = False
            for ext in extracted_ratings:
                ext_name = ext.get("name", "").lower()
                if name.lower() in ext_name or ext_name in name.lower() or name.split()[0].lower() in ext_name:
                    rating = ext.get("rating", "PASS").upper()
                    if rating == "PASSED": rating = "PASS"
                    if rating == "FAILED": rating = "FAIL"
                    reason = ext.get("reason", "Evaluated as " + rating)
                    coaching = ext.get("coaching", "")
                    matched = True
                    extracted_ratings.remove(ext)
                    break
            
            # Fallback if strict name match fails
            if not matched and len(extracted_ratings) > 0:
                 ext = extracted_ratings.pop(0)
                 rating = ext.get("rating", "PASS").upper()
                 if rating == "PASSED": rating = "PASS"
                 if rating == "FAILED": rating = "FAIL"
                 reason = ext.get("reason", "Evaluated as " + rating)
                 coaching = ext.get("coaching", "")

            score = RATING_SCORES.get(rating, 0)
            ratings.append({
                "category": cat_name,
                "name": name,
                "rating": rating,
                "score": score,
                "reason": reason,
                "coaching": coaching
            })
    return ratings'''

content = content[:start_idx] + new_func + content[end_idx:]

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done replacing parse_dynamic_ratings")
