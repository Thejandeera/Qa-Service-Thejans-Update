with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the suggestions block
target_str_to_remove = '''    # 9. Suggestions (Conditional)
    if blended_score < 85.0:
        suggestions = clean_suggestions(query_llm(SUGGESTIONS_PROMPT.format(transcript=clean_transcript), label="suggestions"))
    else:
        suggestions = "Suggestions omitted (score >= 85%)."'''

content = content.replace(target_str_to_remove, "")

# Remove suggestions from the return dict
return_str_old = '''    return {
        "final_score": blended_score,
        "is_auto_fail": is_auto_fail,
        "auto_fail_reason": auto_fail_reason,
        "category_scores": category_scores,
        "scorecard": ratings,
        "summary": summary,
        "suggestions": suggestions
    }'''

return_str_new = '''    return {
        "final_score": blended_score,
        "is_auto_fail": is_auto_fail,
        "auto_fail_reason": auto_fail_reason,
        "category_scores": category_scores,
        "scorecard": ratings,
        "summary": summary
    }'''

content = content.replace(return_str_old, return_str_new)

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done removing suggestions logic")
