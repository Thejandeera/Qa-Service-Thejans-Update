import os
import json
import ast
"""Dynamic Multi-Tenant QA Evaluator Module.

Combines Python rule engines and LLM reasoning 
against dynamic company criteria schemas.
"""

import re
from typing import Dict, Any, List, Optional
from src.services.llm_adapter import query_llm, cache_prompt_prefix, query_llm_with_state, get_embedding
from src.services.response_time import (
    leading_time_seconds, response_delays, response_time_score,
)

RATING_SCORES = {"PASS": 100,  "FAIL": 0, "YES": 100, "NO": 0}


def preview_evaluation_prompt(
    transcript_text: str,
    criteria_data: Dict[str, Any],
    tenant_id: str,
    channel: str = "Call"
) -> Dict[str, Any]:
    """Construct and preview the exact LLM prompt without executing evaluation."""
    # 1. Parse turns and clean timestamps
    turns = []
    clean_lines = []
    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\[\(]\s*\d{1,2}:\d{2}(?::\d{2})?\s*[\]\)]\s*", "", line)
        clean_lines.append(line)
        if ":" in line:
            spk, txt = line.split(":", 1)
            turns.append((spk.strip(), txt.strip()))

    clean_transcript = "\n".join(clean_lines)

    if not turns:
        turns = [("Agent", transcript_text)]
        clean_transcript = transcript_text

    # 2. Vector RAG Policy Search via LLM Summary (REMOVED TO MATCH EVALUATE_INTERACTION)
    # summary = generate_scalable_summary(clean_transcript)
    matched_policies = []

    # 3. Extract Criteria Line Items and Weights
    categories = criteria_data.get("categories", [])
    category_weights = criteria_data.get("category_weights", {})
    auto_fail_rules = criteria_data.get("auto_fail_rules", [])

    if not categories:
        categories = [
            {
                "name": "General Handling",
                "weight_percentage": 100.0,
                "line_items": [
                    {"name": "Professionalism & Tone", "description": "Polite, respectful, no discourtesy."},
                    {"name": "Accuracy & Knowledge", "description": "Provided correct solution according to policy."},
                    {"name": "Ownership & Resolution", "description": "Took ownership and resolved the issue."}
                ]
            }
        ]
        category_weights = {"General Handling": 1.0}

    # 4. Build Dynamic Scorecard Prompt
    prefix, suffix = build_dynamic_prompt(
        transcript_text=clean_transcript,
        categories=categories,
        auto_fail_rules=auto_fail_rules,
        matched_policies=matched_policies,
        channel=channel
    )
    scorecard_prompt = prefix + suffix

    return {
        "prompt": scorecard_prompt,
        "matched_policies": matched_policies,
        "categories_count": len(categories),
        "line_items_count": sum(len(c.get("line_items", [])) for c in categories),
        "channel": channel,
        "tenant_id": tenant_id
    }

from typing import Union

def cosine_similarity(v1, v2):
    import math
    if not v1 or not v2: return 0.0
    dot = sum(a*b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a*a for a in v1))
    norm_b = math.sqrt(sum(b*b for b in v2))
    if norm_a == 0 or norm_b == 0: return 0.0
    return dot / (norm_a * norm_b)

import json, re, math
from typing import Union, List, Dict, Any, Optional

def cosine_similarity(v1, v2):
    if not v1 or not v2: return 0.0
    dot = sum(a*b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a*a for a in v1))
    norm_b = math.sqrt(sum(b*b for b in v2))
    if norm_a == 0 or norm_b == 0: return 0.0
    return dot / (norm_a * norm_b)

def evaluate_interaction(
    transcript_data: Union[str, List[Dict[str, Any]]],
    criteria_data: Dict[str, Any],
    tenant_id: str,
    channel: str = "Call",
    times: Optional[List[Optional[int]]] = None,
    custom_prompt: Optional[str] = None
) -> Dict[str, Any]:
    from src.services.rule_engine import (
        evaluate_branding, evaluate_hold_and_dead_air, evaluate_empathy, 
        evaluate_verified_customer, evaluate_personalized_call,
        extract_active_listening_snippets, extract_empathy_snippets
    )
    from src.services.llm_adapter import query_llm, query_llm_with_state, get_embedding
    
    turns = []
    parsed_times = []
    clean_lines = []
    agent_lines = []
    customer_lines = []
    customer_name = criteria_data.get("customer_name", "")
    sentiment_scores = criteria_data.get("sentiment_scores", [])
    
    if isinstance(transcript_data, list):
        for turn in transcript_data:
            spk = turn.get("speaker", "Unknown")
            txt = turn.get("text", "")
            st_sec = turn.get("start_time_sec", 0)
            turns.append((spk, txt))
            parsed_times.append((st_sec, st_sec+10))
            clean_lines.append(f"{spk}: {txt}")
            if spk.lower() == "agent": agent_lines.append(txt)
            elif spk.lower() == "customer": customer_lines.append(txt)
    else:
        for line in transcript_data.strip().splitlines():
            line = line.strip()
            if not line: continue
            line = re.sub(r"^[\[\(]\s*\d{1,2}:\d{2}(?::\d{2})?\s*[\]\)]\s*", "", line)
            clean_lines.append(line)
            if ":" in line:
                spk, txt = line.split(":", 1)
                turns.append((spk.strip(), txt.strip()))
                parsed_times.append((0, 10))
                if spk.strip().lower() == "agent": agent_lines.append(txt.strip())
                elif spk.strip().lower() == "customer": customer_lines.append(txt.strip())

    clean_transcript = "\n".join(clean_lines)
    agent_only_transcript = "\n".join([f"Agent: {x}" for x in agent_lines])
    
    # Phase 1: Deterministic Engine & Slicing
    rule_ratings = [
        evaluate_branding(turns),
        evaluate_hold_and_dead_air(turns, parsed_times),
        evaluate_verified_customer(turns, parsed_times),
        evaluate_personalized_call(turns, customer_name)
    ]
    
    empathy_snippet = extract_empathy_snippets(turns, sentiment_scores)
    al_snippet = extract_active_listening_snippets(turns)
    
    emp_rating = evaluate_empathy(turns)
    if emp_rating["rating"] == "FAIL" and empathy_snippet:
        p_emp = f"<SNIPPET>\n{empathy_snippet}\n</SNIPPET>\nRead this snippet. Was the agent empathetic to the customer's frustration, or were they rude/dismissive? Reply ONLY with PASS (if empathetic) or FAIL (if rude)."
        r_emp = query_llm(p_emp, label="verify_empathy", format=None)
        if "PASS" in r_emp.upper():
            emp_rating["rating"] = "PASS"
            emp_rating["coaching"] = ""
    rule_ratings.append(emp_rating)

    # Phase 2: Vector Paraphrasing & Context Extraction
    first_10_cust = " ".join(customer_lines[:10])
    first_10_agent = " ".join(agent_lines[:10])
    sim = cosine_similarity(get_embedding(first_10_cust), get_embedding(first_10_agent))
    para_rating = "PASS" if sim >= 0.30 else "FAIL"
    rule_ratings.append({
        "category": "Technical Knowledge", "name": "Paraphrasing", 
        "rating": para_rating, "score": 100 if para_rating=="PASS" else 0,
        "deduction_value": 15, "coaching": "Failed to paraphrase core issue." if para_rating=="FAIL" else ""
    })
    
    # Active Listening pre-check
    al_rating = "PASS"
    if al_snippet:
        p_al = f"<SNIPPET>\n{al_snippet}\n</SNIPPET>\nDid the agent unnecessarily repeat themselves because they weren't listening? Reply ONLY with PASS (no) or FAIL (yes)."
        r_al = query_llm(p_al, label="verify_al", format=None)
        if "FAIL" in r_al.upper(): al_rating = "FAIL"
    rule_ratings.append({
        "category": "Technical Knowledge", "name": "Active listening",
        "rating": al_rating, "score": 100 if al_rating=="PASS" else 0,
        "deduction_value": 10, "coaching": "Repeated questions unnecessarily." if al_rating=="FAIL" else ""
    })

    # Phases 3-5: LLM Micro Batches
    categories = criteria_data.get("categories", [])
    auto_fail_rules = criteria_data.get("auto_fail_rules", [])
    handled = [r["name"].lower() for r in rule_ratings]
    
    all_items = []
    for cat in categories:
        for item in cat.get("line_items", []):
            lname = item["name"].lower()
            if lname not in handled and "expectations" not in lname and "solution" not in lname and "non-first" not in lname:
                all_items.append((cat["name"], item))
                
    b1_agent, b2_end, b3_full = [], [], []
    for cat, item in all_items:
        lname = item["name"].lower()
        if "resolved" in lname or "resolution" in lname: b2_end.append((cat, item))
        elif "escalation" in lname or "hostility" in lname: b3_full.append((cat, item))
        else: b1_agent.append((cat, item))
        
    def run_batch(items, tx, ctx=""):
        if not items: return []
        chunk = []
        cat_map = {}
        for c, i in items:
            if c not in cat_map:
                cat_map[c] = {"name": c, "line_items": []}
                chunk.append(cat_map[c])
            cat_map[c]["line_items"].append(i)
        prefix, suffix = build_dynamic_prompt(tx, chunk, [], [], channel, [], ctx)
        reply = query_llm_with_state(prefix, suffix, label="batch", format="json")
        return parse_dynamic_ratings(reply, chunk)

    llm_ratings = []
    prob_ctx = f"\nCUSTOMER PROBLEM CONTEXT:\n{first_10_cust}\n"
    llm_ratings.extend(run_batch(b1_agent, agent_only_transcript, prob_ctx))
    
    end_tx = "\n".join(clean_lines[int(len(clean_lines)*0.7):])
    llm_ratings.extend(run_batch(b2_end, end_tx))
    llm_ratings.extend(run_batch(b3_full, clean_transcript))
    
    ratings = rule_ratings + llm_ratings
    is_auto_fail, reason = check_auto_fail(clean_transcript, [], auto_fail_rules, ratings)
    
    # Phase 6: Batched Coaching
    failed_items = [r for r in ratings if r["rating"] in ["FAIL", "NO"] and "dead air" not in r["name"].lower() and "branding" not in r["name"].lower()]
    if failed_items:
        desc = "\n".join([f"- {r['name']}: {r.get('description', '')}" for r in failed_items])
        try:
            c_prompt = f"<INSTRUCTIONS>\nYou are an expert QA Coach.\nThe agent FAILED the following criteria:\n{desc}\nWrite a brief coaching tip (1 sentence MAX) on how they can improve on EACH criterion.\nCRITICAL: Output ONLY a valid JSON object mapping the exact criterion name to its tip.\n</INSTRUCTIONS>"
            c_reply = query_llm(c_prompt, label="coaching_batched", format="json")
            cj = json.loads(c_reply.strip())
            for r in failed_items: r["coaching"] = cj.get(r["name"], "Review transcript.")
        except:
            pass
            
    cat_scores, b_score = calculate_category_scores(ratings, criteria_data.get("category_weights", {}), is_auto_fail)
    
    clean_scorecard = [{"category": r["category"], "name": r["name"], "rating": r["rating"], "coaching": r.get("coaching", "")} for r in ratings]
    return {"final_score": b_score, "scorecard": clean_scorecard, "is_auto_fail": is_auto_fail, "auto_fail_reason": reason}
