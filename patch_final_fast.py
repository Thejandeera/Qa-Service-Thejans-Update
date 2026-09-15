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
        batch_size = 1
        for i in range(0, len(failed_items), batch_size):
            chunk = failed_items[i:i + batch_size]
            r = chunk[0]
            try:
                c_prompt = f\"\"\"<TRANSCRIPT>\\n{clean_transcript}\\n</TRANSCRIPT>\\n\\n<INSTRUCTIONS>\\nYou are an expert QA Coach evaluating a {channel} interaction.\\nThe agent FAILED the following QA criteria: '{r['name']}'\\n\\nWrite a brief coaching tip (EXPLICITLY 1 to 2 sentences MAX) on how the agent can improve.\\nCRITICAL: Output ONLY a valid JSON object. Do not output reasons, arrays, or conversational text.\\n\\nJSON FORMAT:\\n{{\\n  \"coaching\": \"...\"\\n}}\\n</INSTRUCTIONS>\"\"\"
                c_reply = query_llm(c_prompt, label="coaching", timeout=300, format="json")
                print(f"==== COACHING REPLY ({r['name']}) ====\\n", c_reply, "\\n========================")
                
                cj = {}
                try:
                    c_reply = c_reply.strip()
                    parsed = json.loads(c_reply)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        cj = parsed[0]
                    elif isinstance(parsed, dict):
                        cj = parsed
                except Exception as e:
                    print("JSON parse error:", e)
                
                r["reason"] = "See coaching for details."
                r["coaching"] = cj.get("coaching", "Review transcript.")
            except Exception as e:
                print(f"Coaching generation failed for {r['name']}:", e)
                r["reason"] = "Evaluated as FAIL"
                r["coaching"] = "Review transcript."
                
    '''

content = content[:s_idx] + new_block + content[e_idx:]

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Final fast loop patched!")
