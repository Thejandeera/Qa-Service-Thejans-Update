import os
import re
import json
import ast

def patch_dynamic_evaluator():
    with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Rewrite parse_dynamic_ratings to unstructured PASS/FAIL matching
    old_parser_start = "def parse_dynamic_ratings("
    old_parser_end = "return ratings"
    start_idx = content.find(old_parser_start)
    end_idx = content.find(old_parser_end, start_idx) + len(old_parser_end)

    new_parser = '''def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Safely strip out internal monologue for reasoning models
    reply = re.sub(r'<thinking>.*?</thinking>', '', reply, flags=re.DOTALL)
    
    extracted_ratings = []
    for line in reply.splitlines():
        match = re.search(r"^(?:[^:]*:\s*)?\**\b(PASS|FAIL|PASSED|FAILED|YES|NO)\b", line, re.IGNORECASE)
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

    # 2. Insert the coaching logic at the end of evaluate_interaction, just before calculate_category_scores
    target_loc = "category_scores, blended_score = calculate_category_scores(ratings, category_weights, is_auto_fail)"
    
    coaching_logic = '''# Phase 2: Generate Coaching for FAILs
    failed_items = [r for r in ratings if r["rating"] in ["FAIL", "NO"] and "dead air" not in r["name"].lower() and "branding" not in r["category"].lower()]
    if failed_items:
        try:
            with open(os.path.join(os.path.dirname(__file__), "..", "..", "resources", "prompts", "coaching_prompt.txt"), "r") as f:
                c_template = f.read()
            failed_str = "\n".join("- " + r["name"] for r in failed_items)
            c_prompt = c_template.format(channel=channel, transcript_text=clean_transcript, failed_items_str=failed_str)
            
            c_reply = query_llm(c_prompt, label="coaching")
            c_reply = re.sub(r'<thinking>.*?</thinking>', '', c_reply, flags=re.DOTALL)
            
            s_idx = c_reply.find('[')
            e_idx = c_reply.rfind(']')
            coaching_json = []
            if s_idx != -1 and e_idx != -1:
                try:
                    coaching_json = json.loads(c_reply[s_idx:e_idx+1])
                except json.JSONDecodeError:
                    try:
                        py_str = c_reply[s_idx:e_idx+1].replace('true', 'True').replace('false', 'False').replace('null', 'None')
                        coaching_json = ast.literal_eval(py_str)
                    except:
                        pass
            
            if isinstance(coaching_json, list):
                for r in ratings:
                    if r["rating"] in ["FAIL", "NO"]:
                        for cj in coaching_json:
                            if isinstance(cj, dict) and (r["name"].lower() in cj.get("name", "").lower() or cj.get("name", "").lower() in r["name"].lower()):
                                r["reason"] = cj.get("reason", "Evaluated as FAIL")
                                r["coaching"] = cj.get("coaching", "Review agent transcript for missed item.")
                                break
                        # fallback reason if JSON mismatch
                        if r["reason"] == "Standard compliant response":
                            r["reason"] = "Evaluated as FAIL"
                            r["coaching"] = "Review transcript."
        except Exception as e:
            print("Coaching generation failed:", e)

    category_scores, blended_score = calculate_category_scores(ratings, category_weights, is_auto_fail)'''

    content = content.replace(target_loc, coaching_logic)

    # Make sure we import json and ast at the top
    if "import json" not in content:
        content = "import json\nimport ast\n" + content

    with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
        f.write(content)

patch_dynamic_evaluator()
print("Done patching evaluate_interaction to 2-stage.")
