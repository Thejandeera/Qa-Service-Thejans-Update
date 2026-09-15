import re

with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_str = '# Phase 2: Generate Coaching for FAILs'
end_str = 'category_scores, blended_score = calculate_category_scores'

s_idx = content.find(start_str)
e_idx = content.find(end_str)

if s_idx == -1 or e_idx == -1:
    print("Could not find the block")
    exit(1)

new_block = '''# Phase 2: Generate Coaching for FAILs
    failed_items = [r for r in ratings if r["rating"] in ["FAIL", "NO"] and "dead air" not in r["name"].lower()]
    if failed_items:
        batch_size = 3
        for i in range(0, len(failed_items), batch_size):
            chunk = failed_items[i:i + batch_size]
            names_str = "\\n".join(f"- {r['name']}" for r in chunk)
            try:
                c_prompt = f\"\"\"<TRANSCRIPT>\\n{clean_transcript}\\n</TRANSCRIPT>\\n\\n<INSTRUCTIONS>\\nYou are an expert QA Coach evaluating a {channel} interaction.\\nThe agent FAILED the following QA criteria:\\n{names_str}\\n\\nFor each failed item, write a short reason (1 sentence) why they failed, and a brief coaching tip (1-2 sentences) on how to improve.\\nCRITICAL: Output ONLY a valid JSON array of objects. Do not output conversational text.\\n\\nJSON FORMAT:\\n[\\n  {{\\n    \"name\": \"Line Item Name\",\\n    \"reason\": \"...\",\\n    \"coaching\": \"...\"\\n  }}\\n]\\n</INSTRUCTIONS>\"\"\"
                c_reply = query_llm(c_prompt, label="coaching", timeout=300, format="json")
                print(f"==== COACHING REPLY BATCH ====\\n", c_reply, "\\n========================")
                
                cj_list = []
                try:
                    c_reply = c_reply.strip()
                    if c_reply.startswith('{'):
                        cj_list = [json.loads(c_reply)]
                    else:
                        parsed = json.loads(c_reply)
                        cj_list = parsed if isinstance(parsed, list) else [parsed]
                except Exception as e:
                    print("JSON parse error in batch:", e)
                
                for r in chunk:
                    matched = False
                    for cj in cj_list:
                        if isinstance(cj, dict) and cj.get("name") and (r["name"].lower() in cj.get("name", "").lower() or cj.get("name", "").lower() in r["name"].lower()):
                            r["reason"] = cj.get("reason", "Evaluated as FAIL")
                            r["coaching"] = cj.get("coaching", "Review transcript.")
                            matched = True
                            break
                    if not matched:
                        r["reason"] = "Evaluated as FAIL"
                        r["coaching"] = "Review transcript."
            except Exception as e:
                print(f"Coaching generation failed for batch:", e)
                for r in chunk:
                    r["reason"] = "Evaluated as FAIL"
                    r["coaching"] = "Review transcript."
                    
    '''

content = content[:s_idx] + new_block + content[e_idx:]

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Batch loop patched!")
