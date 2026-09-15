import re

with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

new_func = '''def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import json
    import ast
    # Safely strip out internal monologue for reasoning models
    reply = re.sub(r'<thinking>.*?</thinking>', '', reply, flags=re.DOTALL)

    ratings = []
    extracted_ratings = None
    
    # Attempt to parse JSON block from reply
    start_idx = reply.find('[')
    end_idx = reply.rfind(']')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = reply[start_idx:end_idx+1]
        try:
            extracted_ratings = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # Fallback: strict eval for trailing commas or single quotes
                py_str = json_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                parsed = ast.literal_eval(py_str)
                if isinstance(parsed, list):
                    extracted_ratings = parsed
            except Exception:
                extracted_ratings = None
                
    if extracted_ratings is None:
        extracted_ratings = []
        is_parse_error = True
    else:
        is_parse_error = False

    for cat in categories:
        cat_name = cat.get("name", "Category")
        for item in cat.get("line_items", []):
            name = item.get("name", "Item")
            if is_parse_error:
                rating = "FAIL"
                reason = "PARSE ERROR: Failed to decode JSON from LLM output."
                coaching = "Please check the LLM logs to see why the output was invalid."
            else:
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
            if not matched and len(extracted_ratings) > 0 and not is_parse_error:
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

content = content.replace(old_func, new_func)

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done patching parse_dynamic_ratings")
