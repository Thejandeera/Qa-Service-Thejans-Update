import re

with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start of the Phase 2 block
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
        for r in failed_items:
            try:
                c_prompt = f\"\"\"<TRANSCRIPT>\\n{clean_transcript}\\n</TRANSCRIPT>\\n\\n<INSTRUCTIONS>\\nYou are an expert QA Coach evaluating a {channel} interaction.\\nThe agent FAILED the following QA criteria: '{r['name']}'\\n\\nWrite a short reason (1 sentence) why they failed, and a brief coaching tip (1-2 sentences) on how to improve.\\nCRITICAL: Output ONLY a valid JSON object. Do not output arrays or conversational text.\\n\\nJSON FORMAT:\\n{{\\n  \"reason\": \"...\",\\n  \"coaching\": \"...\"\\n}}\\n</INSTRUCTIONS>\"\"\"
                c_reply = query_llm(c_prompt, label="coaching", timeout=300, format="json")
                print(f"==== COACHING REPLY ({r['name']}) ====\\n", c_reply, "\\n========================")
                
                cj = json.loads(c_reply)
                r["reason"] = cj.get("reason", "Evaluated as FAIL")
                r["coaching"] = cj.get("coaching", "Review transcript.")
            except Exception as e:
                print(f"Coaching generation failed for {r['name']}:", e)
                r["reason"] = "Evaluated as FAIL"
                r["coaching"] = "Review transcript."
                
    '''

content = content[:s_idx] + new_block + content[e_idx:]

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Loop patched!")
