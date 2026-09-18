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

def evaluate_paraphrasing_and_summary(full_transcript: str, agent_transcript: str) -> tuple[dict, str, str]:
    prompt_a = f"""
    <TRANSCRIPT>
    {full_transcript}
    </TRANSCRIPT>
    You are an auditor. Read the full transcript.
    Reply with a valid JSON object matching exactly this structure:
    {{
        "customer_problem": "<In one short sentence, describe the exact problem the customer reported>",
        "overall_summary": "<Summarize the entire call in 60 characters>"
    }}
    Do not output any conversational text.
    """
    
    prompt_b = f"""
    <TRANSCRIPT>
    {agent_transcript}
    </TRANSCRIPT>
    You are an auditor. Read ONLY the agent's side of the transcript.
    Based ONLY on what the agent said, try to deduce what the customer's problem was.
    Reply with a valid JSON object matching exactly this structure:
    {{
        "customer_problem": "<In one short sentence, describe the exact problem the customer reported based ONLY on the agent's context>"
    }}
    Do not output any conversational text.
    """
    
    import json
    import re
    
    # Prompt A Call
    resp_a = query_llm(prompt_a, label="paraphrasing_truth", format="json")
    try:
        data_a = json.loads(resp_a)
    except:
        match = re.search(r'\{.*\}', resp_a, re.DOTALL)
        data_a = json.loads(match.group(0)) if match else {"customer_problem": "Unknown", "overall_summary": "Summary not generated"}
    
    # Prompt B Call
    resp_b = query_llm(prompt_b, label="paraphrasing_agent", format="json")
    try:
        data_b = json.loads(resp_b)
    except:
        match = re.search(r'\{.*\}', resp_b, re.DOTALL)
        data_b = json.loads(match.group(0)) if match else {"customer_problem": "Unknown"}
        
    truth_prob = data_a.get("customer_problem", "")
    agent_prob = data_b.get("customer_problem", "")
    
    embed_truth = get_embedding(truth_prob)
    embed_agent = get_embedding(agent_prob)
    
    sim = cosine_similarity(embed_truth, embed_agent)
    
    if sim >= 0.52:
        rating = "PASS"
        coaching = ""
    else:
        rating = "FAIL"
        coaching = f"Vector similarity check failed ({sim:.2f} < 0.52). Agent likely failed to explicitly paraphrase or state the problem. True problem: '{truth_prob}'. Agent context problem: '{agent_prob}'."
        
    paraphrasing_result = {
        "category": "Technical Knowledge",
        "name": "Paraphrasing",
        "rating": rating,
        "score": 100 if rating == "PASS" else 0,
        "deduction_value": 15,
        "coaching": coaching
    }
    
    return paraphrasing_result, data_a.get("overall_summary", "Summary not generated"), truth_prob

def evaluate_interaction(
    transcript_data: Union[str, List[Dict[str, Any]]],
    criteria_data: Dict[str, Any],
    tenant_id: str,
    channel: str = "Call",
    times: Optional[List[Optional[int]]] = None,
    custom_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """Execute dynamic QA evaluation for a customer interaction."""
    # 1. Parse turns and remove timestamps for LLM efficiency
    turns = []
    parsed_times = []
    clean_lines = []
    
    if isinstance(transcript_data, list):
        for turn in transcript_data:
            spk = turn.get("speaker", "Unknown")
            txt = turn.get("text", "")
            
            st_str = turn.get("start_time")
            en_str = turn.get("end_time")
            st_sec = turn.get("start_time_sec")
            en_sec = turn.get("end_time_sec")
            
            start_t = leading_time_seconds(st_str) if st_str else (st_sec or 0)
            end_t = leading_time_seconds(en_str) if en_str else (en_sec or 0)
            
            turns.append((spk, txt))
            parsed_times.append((start_t, end_t))
            clean_lines.append(f"{spk}: {txt}")
        clean_transcript = "\n".join(clean_lines)
    else:
        for line in transcript_data.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            t = leading_time_seconds(line)
            line = re.sub(r"^[\[\(]\s*\d{1,2}:\d{2}(?::\d{2})?\s*[\]\)]\s*", "", line)
            clean_lines.append(line)
            if ":" in line:
                spk, txt = line.split(":", 1)
                turns.append((spk.strip(), txt.strip()))
                parsed_times.append((t or 0, (t or 0) + 10))

        clean_transcript = "\n".join(clean_lines)

        if not turns:
            turns = [("Agent", transcript_data)]
            parsed_times = [(0, 10)]
            clean_transcript = transcript_data

    # 2. Extract Topics using Lightweight LLM (LLM3:1b) (REMOVED TO PREVENT CACHE THRASHING)
    # from src.services.qa_summary import generate_scalable_summary
    # topic_keywords = generate_scalable_summary(clean_transcript)

    matched_policies = []
    
    # 4. Deterministic Python Rule Engine (Branding, SLAs & Empathy)
    from src.services.rule_engine import evaluate_branding, evaluate_hold_and_dead_air, evaluate_empathy, evaluate_verified_customer
    rule_ratings = [
        evaluate_branding(turns),
        evaluate_hold_and_dead_air(turns, parsed_times),
        evaluate_empathy(turns),
        evaluate_verified_customer(turns, parsed_times)
    ]
    harsh_lines = []

    # 5. Extract Criteria Line Items and Weights
    categories = criteria_data.get("categories", [])
    category_weights = criteria_data.get("category_weights", {})
    auto_fail_rules = criteria_data.get("auto_fail_rules", [])

    if not categories:
        categories = [
            {
                "name": "Soft Skills",
                "weight_percentage": 33.3,
                "line_items": [
                    {"name": "Personalized the call/ticket appropriately", "description": "Rate PASS ONLY if the agent explicitly used the customer's specific name (e.g., 'John') during the conversation. Rate FAIL if the agent never referred to the customer by their name."},
                    {"name": "Empathy & Acknowledgment Statement", "description": "Evaluate if the agent provided empathy statements when appropriate and acknowledged the customer's questions or statements (e.g., through paraphrasing). The agent must not be blunt."},
                    {"name": "Build rapport and observed professionalism", "description": "Evaluate if the agent was courteous, respectful, adjusted to the customer's technical pacing, did not interrupt, and avoided jargon or unprofessional sounds."}
                ]
            },
            {
                "name": "Technical Knowledge",
                "weight_percentage": 66.7,
                "line_items": [
                    {"name": "Paraphrasing", "description": "Evaluate if the agent paraphrased the issue at the onset of the call or as soon as the customer stated their request to reconfirm understanding."},
                    {"name": "Verified customer", "description": "Rate PASS ONLY if the agent explicitly verified secure account details (e.g. a PIN, full address, or security question). Rate FAIL if they only asked for an account number or failed to verify identity."},
                    {"name": "Probing", "description": "Evaluate if the agent used proper and effective probing questions to identify the concern, especially if the customer was unable to express the issue clearly."},
                    {"name": "Set proper expectations", "description": "Evaluate if the agent provided accurate expectations about the resolution, addressed possible related issues that might arise, and provided updates as soon as available."},
                    {"name": "Provided the appropriate solution", "description": "Rate PASS if the agent's actions eventually solved the core issue (e.g., the customer confirmed the service is working). ONLY rate FAIL if the agent gave completely wrong instructions that left the issue unresolved at the end of the call."},
                    {"name": "Took ownership of the problem", "description": "Evaluate if the agent exhausted all resources to provide a resolution, offered meaningful troubleshooting (not just transferring without attempting to assist), and took ownership of the ticket without blaming other departments."},
                    {"name": "Active listening", "description": "Evaluate if the agent avoided asking the customer for information that the customer had already provided earlier in the call (e.g., name, company, error message). If they ask for repeated info two or more times, rate as FAIL."},
                    {"name": "Confirmed the issue is resolved", "description": "Evaluate if the agent gained verbal confirmation that the issue is resolved, asked the customer to test, provided a wrap-up summary of the resolution, and offered further assistance."}
                ]
            },
            {
                "name": "Auto Fail Category",
                "weight_percentage": 0.0,
                "line_items": [
                    {"name": "Escalation", "description": "ONLY rate FAIL if the customer explicitly asked for a supervisor/manager OR threatened to cancel AND the agent refused or failed to transfer them. Do NOT fail this simply because the customer was frustrated or the call was long. Otherwise, rate PASS."},
                    {"name": "Non-First Call Resolution", "description": "Rate PASS if the customer's technical issue was fully resolved by the end of this call. ONLY rate FAIL if the customer had to hang up with the issue still broken, was incorrectly resolved, or was told to call back later."}
                ]
            }
        ]
        category_weights = {"Soft Skills": 0.333, "Technical Knowledge": 0.667, "Auto Fail Category": 0.0}

    # 6. LLM Evaluation (Grouped Map-Reduce with Micro-Batching)
    if custom_prompt:
        llm_reply = query_llm(custom_prompt, label="dynamic_scorecard")
    else:
        llm_reply_parts = []
        
        # Flatten and filter handled line items
        all_items = []
        for cat in categories:
            for item in cat.get("line_items", []):
                lower_name = item.get("name", "").lower()
                if "empathy" in lower_name or "paraphrasing" in lower_name or "verified customer" in lower_name:
                    continue
                all_items.append((cat["name"], item))
                
        # Build an Agent-Only version of the transcript for Soft Skills and Paraphrasing
        agent_only_lines = [f"Agent: {txt}" for spk, txt in turns if spk.lower() == "agent"]
        agent_only_transcript = "\n".join(agent_only_lines)

        # Prompt 4: Generate Paraphrasing score and Call Summary via Vector Similarity Engine
        paraphrasing_rating, call_summary, truth_prob = evaluate_paraphrasing_and_summary(clean_transcript, agent_only_transcript)
        rule_ratings.append(paraphrasing_rating)

        # Cascade Batching Logic
        batch_1_soft = []
        batch_2_probe = []
        batch_3_solution = []
        batch_4_vibe = []
        
        for cat, item in all_items:
            lower_name = item["name"].lower()
            if "soft skills" in cat.lower():
                batch_1_soft.append((cat, item))
            elif "probing" in lower_name or "expectations" in lower_name:
                batch_2_probe.append((cat, item))
            elif "solution" in lower_name:
                batch_3_solution.append((cat, item))
            else:
                # Ownership, Active listening, Escalation, Non-FCR
                batch_4_vibe.append((cat, item))
                
        # Cascade Shortcut: Auto-Pass Probing if Paraphrasing Passed
        if paraphrasing_rating["rating"] == "PASS":
            new_batch_2 = []
            for cat, item in batch_2_probe:
                if "probing" in item["name"].lower():
                    rule_ratings.append({
                        "category": cat,
                        "name": item["name"],
                        "rating": "PASS",
                        "score": 100,
                        "deduction_value": item.get("deduction_value", 15),
                        "coaching": ""
                    })
                else:
                    new_batch_2.append((cat, item))
            batch_2_probe = new_batch_2

        item_batches = [b for b in [batch_1_soft, batch_2_probe, batch_3_solution, batch_4_vibe] if b]
                
        def create_category_chunk(batch_items):
            grouped = {}
            for cat_name, item in batch_items:
                if cat_name not in grouped:
                    grouped[cat_name] = {"name": cat_name, "line_items": []}
                grouped[cat_name]["line_items"].append(item)
            return list(grouped.values())

        chunks = [create_category_chunk(batch) for batch in item_batches]
        
        for idx, chunk in enumerate(chunks):
            if not chunk: continue
            
            # Map chunk back to the batch logic to determine the right transcript
            # Soft Skills (0), Probing (1), Solution (2) use Agent-Only. Vibe (3) uses Full.
            # However, if batch_2 or batch_1 is empty, indices shift. Let's dynamically check content.
            chunk_str = str(chunk).lower()
            if "soft skills" in chunk_str or "probing" in chunk_str or "expectations" in chunk_str or "solution" in chunk_str:
                current_transcript = agent_only_transcript
            else:
                current_transcript = clean_transcript
                
            # Inject ground truth problem into context for Probing and Solution batches
            context_injection = f"\nGROUND TRUTH PROBLEM: {truth_prob}\n" if ("probing" in chunk_str or "expectations" in chunk_str or "solution" in chunk_str) else ""

            prefix, chunk_suffix = build_dynamic_prompt(
                transcript_text=current_transcript,
                categories=chunk,
                auto_fail_rules=auto_fail_rules,
                matched_policies=matched_policies,
                channel=channel,
                harsh_lines=harsh_lines,
                summary_str=(call_summary + context_injection) if call_summary else context_injection
            )
            
            # The "state" is just the prefix string. Ollama handles the caching internally.
            label = f"scorecard_batch_{idx+1}"
            reply = query_llm_with_state(prefix, chunk_suffix, label=label, format="json")
            llm_reply_parts.append(reply)
            
        llm_reply = "\n\n".join(llm_reply_parts)

    ratings = parse_dynamic_ratings(llm_reply, categories)
    # Pre-flight token estimate
    approx_tokens = len(clean_transcript) / 4
    if approx_tokens > 25000:
        raise ValueError(f"Transcript is too large ({approx_tokens} estimated tokens). Maximum allowed is 25000 tokens.")

    # 4. Inject Rule Engine Fixed Outcomes and filter out LLM dupes/NOT_RATED
    rule_rating_names = {r["name"].lower() for r in rule_ratings}
    filtered_ratings = [r for r in ratings if r["name"].lower() not in rule_rating_names]
    ratings = rule_ratings + filtered_ratings
    
    intense_moments = []
    harsh_agent_lines = harsh_lines

    # 6. Check Auto-Fail Triggers
    is_auto_fail, auto_fail_reason = check_auto_fail(clean_transcript, harsh_agent_lines, auto_fail_rules, ratings)

    # 7. Mathematical Scoring Engine
    # Phase 2: Generate Coaching for FAILs
    # Phase 2: Generate Coaching for FAILs
    failed_items = [r for r in ratings if r["rating"] in ["FAIL", "NO"] and "dead air" not in r["name"].lower() and "branding" not in r["name"].lower()]
    if failed_items:
        failed_names_and_desc = "\n".join([f"- {r['name']}: {r.get('description', '')}" for r in failed_items])
        try:
            c_prompt = f"""<TRANSCRIPT>\n{clean_transcript}\n</TRANSCRIPT>\n\n<INSTRUCTIONS>\nYou are an expert QA Coach evaluating a {channel} interaction.\nThe agent FAILED the following QA criteria:\n{failed_names_and_desc}\n\nWrite a brief coaching tip (EXPLICITLY 1 to 2 sentences MAX) on how the agent can improve on EACH specific criterion.\nCRITICAL: Output ONLY a valid JSON object mapping the exact criterion name to its coaching tip. Do not output reasons, arrays, or conversational text.\n\nJSON FORMAT:\n{{\n  "Criterion Name 1": "Coaching tip...",\n  "Criterion Name 2": "Coaching tip..."\n}}\n</INSTRUCTIONS>"""
            c_reply = query_llm(c_prompt, label="coaching_batched", timeout=300, format="json")
            
            cj = {}
            try:
                c_reply = c_reply.strip()
                parsed = json.loads(c_reply)
                if isinstance(parsed, dict):
                    cj = parsed
            except Exception as e:
                print("JSON parse error:", e)
            
            for r in failed_items:
                r["coaching"] = cj.get(r['name'], "Review transcript.")
        except Exception as e:
            print("Batched coaching generation failed:", e)
            for r in failed_items:
                r["coaching"] = "Review transcript."
                
    category_scores, blended_score = calculate_category_scores(ratings, category_weights, is_auto_fail)

    # Check for unrated items due to LLM failure/truncation
    for r in ratings:
        if r.get("rating") == "NOT_RATED":
            raise ValueError(f"Parsing failed for criterion: {r['name']}. Transcript may have been truncated or LLM failed to answer.")

    # 8. Final Payload Prep (Use self-generated summary from Prompt 4)
    final_summary = call_summary if call_summary else "Summary could not be generated."

    # Clean scorecard for client (remove internal score calculation field and reason)
    clean_scorecard = [
        {
            "category": r["category"],
            "name": r["name"],
            "rating": r["rating"],
            "coaching": r.get("coaching", "")
        }
        for r in ratings
    ]

    return {
        "final_score": blended_score,
        "is_auto_fail": is_auto_fail,
        "auto_fail_reason": auto_fail_reason,
        "category_scores": category_scores,
        "scorecard": clean_scorecard,
        "summary": final_summary
    }

def parse_llm_intensity(reply: str) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
    """Parse intense moments and harsh lines from the LLM scorecard reply."""
    intense_moments = []
    harsh_lines = []
    
    current_section = None
    for line in reply.splitlines():
        clean_line = line.strip()
        upper_line = clean_line.upper()
        
        if "INTENSE MOMENTS" in upper_line:
            current_section = "intense"
            continue
        elif "HARSH AGENT LINES" in upper_line:
            current_section = "harsh"
            continue
        elif "SCORECARD" in upper_line or "PASS" in upper_line or "FAIL" in upper_line:
            if "SCORECARD" in upper_line:
                current_section = None
        
        if not clean_line or clean_line.lower() == "none" or clean_line == "- none" or clean_line == "-":
            continue
            
        if current_section == "intense" and len(clean_line) > 5:
            intense_moments.append({"turn": "?", "speaker": "?", "text": clean_line.lstrip("-* "), "sentiment": -1.0, "intense": True})
        elif current_section == "harsh" and len(clean_line) > 5:
            harsh_lines.append({"turn": "?", "speaker": "Agent", "text": clean_line.lstrip("-* "), "sentiment": -1.0, "intense": True})
            
    return intense_moments, harsh_lines

def build_dynamic_prompt(
    transcript_text: str,
    categories: List[Dict[str, Any]],
    auto_fail_rules: List[Dict[str, Any]],
    matched_policies: List[Dict[str, Any]],
    channel: str,
    harsh_lines: List[Dict[str, Any]] = None,
    summary_str: str = ""
) -> str:
    """Construct dynamic LLM prompt tailored to tenant criteria with sanitized formatting."""
    if harsh_lines is None:
        harsh_lines = []
        
    # 1. Evaluation Line Items
    items_list = []
    for cat in categories:
        cat_name = re.sub(r"<\s*br\s*/?\s*>", " ", cat.get("name", "Category"), flags=re.IGNORECASE).strip()
        for item in cat.get("line_items", []):
            name = re.sub(r"<\s*br\s*/?\s*>", " ", item.get("name", "Item"), flags=re.IGNORECASE).strip()
            name = re.sub(r"\s+", " ", name)
            desc = re.sub(r"<\s*br\s*/?\s*>", " ", item.get("description", ""), flags=re.IGNORECASE).strip()
            desc = re.sub(r"\s+", " ", desc)
            spiels = item.get("verbatim_spiels", [])
            clean_spiels = [re.sub(r"<\s*br\s*/?\s*>", " ", s, flags=re.IGNORECASE).strip() for s in spiels]
            spiel_txt = f" [Required Spiels: {', '.join(clean_spiels)}]" if clean_spiels else ""
            items_list.append(f"- [{cat_name}] {name}: {desc}{spiel_txt}")

    criteria_str = "\n".join(items_list)
    
    # 2. Auto-Fail Zero-Tolerance Rules Section
    auto_fail_list = []
    for r in auto_fail_rules:
        r_name = re.sub(r"<\s*br\s*/?\s*>", " ", r.get("name", "Auto-Fail"), flags=re.IGNORECASE).strip()
        r_desc = re.sub(r"<\s*br\s*/?\s*>", " ", r.get("description", r.get("trigger", "Immediate 0 score")), flags=re.IGNORECASE).strip()
        auto_fail_list.append(f"• {r_name}: {r_desc}")
    auto_fail_str = "\n".join(auto_fail_list) if auto_fail_list else "• Discourtesy / Rudeness: Immediate 0 score on profanity or policy abandonment."

    clean_title = lambda p: re.sub(r'<\s*br\s*/?\s*>', ' ', p['title'], flags=re.IGNORECASE)
    clean_content = lambda p: re.sub(r'<\s*br\s*/?\s*>', ' ', p['content'][:300], flags=re.IGNORECASE)
    policies_str = "\n".join(
        f"• {clean_title(p)}: {clean_content(p)}" 
        for p in matched_policies
    ) or "• No specific policy override found."
    
    harsh_lines_str = "\n".join(
        f"Agent: \"{h['text']}\"" for h in harsh_lines
    ) if harsh_lines else "None detected."
    
    summary_injection = f"\nCALL SUMMARY:\n{summary_str}\n" if summary_str else ""

    import os
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    prompt_path = os.getenv("PROMPT_DYNAMIC_EVALUATION_PATH", "resources/prompts/dynamic_evaluation_prompt.txt")
    full_path = os.path.join(_ROOT, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        template = f.read()
        
    full_prompt = template.format(
        channel=channel,
        auto_fail_str=auto_fail_str,
        policies_str=policies_str,
        criteria_str=criteria_str,
        harsh_lines_str=harsh_lines_str,
        transcript_text=transcript_text,
        summary_str=summary_injection
    )
    
    # Split prompt into prefix (transcript) and suffix (criteria)
    # This allows us to load the massive transcript KV Cache only once
    split_str = "EVALUATION LINE ITEMS TO RATE (Evaluate ONLY these items):"
    parts = full_prompt.split(split_str)
    prefix = parts[0]
    suffix = split_str + parts[1]
    
    return prefix, suffix


def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Safely strip out internal monologue for reasoning models
    reply = re.sub(r'<thinking>.*?</thinking>', '', reply, flags=re.DOTALL)
    
    extracted_ratings = []
    
    # 1. Try extracting from JSON format
    items = re.finditer(r'"item_name"\s*:\s*"([^"]+)"\s*,\s*"rating"\s*:\s*"([^"]+)"', reply, re.IGNORECASE)
    for match in items:
        extracted_ratings.append({
            "raw_name": match.group(1).lower(),
            "rating": match.group(2).upper()
        })
        
    lines = reply.splitlines()
    
    ratings = []
    for cat in categories:
        cat_name = cat.get("name", "Category")
        for item in cat.get("line_items", []):
            name = item.get("name", "Item")
            deduction_value = item.get("deduction_value", 10)
            rating = "NOT_RATED"
            
            name_words = set(re.findall(r'\w+', name.lower()))
            
            # First check JSON extracted items
            for ext in extracted_ratings:
                ext_words = set(re.findall(r'\w+', ext["raw_name"]))
                if name.lower() in ext["raw_name"] or len(name_words.intersection(ext_words)) >= min(2, len(name_words)):
                    rating = ext["rating"]
                    break
                    
            # If still NOT_RATED, fallback to line-based scan (for non-JSON text)
            if rating == "NOT_RATED":
                for line in lines:
                    line_lower = line.lower()
                    ext_words = set(re.findall(r'\w+', line_lower))
                    
                    if name.lower() in line_lower or len(name_words.intersection(ext_words)) >= min(2, len(name_words)):
                        if re.search(r'\b(pass|passed|yes)\b', line_lower):
                            rating = "PASS"
                            break
                        elif re.search(r'\b(fail|failed|no)\b', line_lower):
                            rating = "FAIL"
                            break
                        
            score = RATING_SCORES.get(rating, 0)
            ratings.append({
                "category": cat_name,
                "name": name,
                "description": item.get("description", ""),
                "rating": rating,
                "score": score,
                "deduction_value": deduction_value,
                "coaching": ""
            })
    return ratings


def check_auto_fail(
    transcript: str,
    harsh_lines: List[Dict[str, Any]],
    auto_fail_rules: List[Dict[str, Any]],
    ratings: List[Dict[str, Any]]
) -> (bool, Optional[str]):
    """Check for instant zero auto-fail breaches."""
    lower_tx = transcript.lower()

    # Profanity / extreme discourtesy check
    profanities = ["fuck", "shut up", "idiot", "get lost", "stupid", "hang up"]
    for word in profanities:
        if word in lower_tx:
            return True, f"Auto-Fail Triggered: Profanity/Discourtesy detected ('{word}')"

    # Extreme harsh agent lines
    if len(harsh_lines) >= 3:
        return True, "Auto-Fail Triggered: Multiple highly hostile/harsh agent statements detected"
        
    # Check LLM scorecard for Auto Fail category failures
    for r in ratings:
        if "AUTO FAIL" in r["category"].upper() and r["rating"] in ["NO", "FAIL"]:
            return True, f"Auto-Fail Triggered by Scorecard: {r['name']}"

    return False, None


def calculate_category_scores(
    ratings: List[Dict[str, Any]],
    category_weights: Dict[str, float],
    is_auto_fail: bool
) -> (Dict[str, float], float):
    """Calculate weighted category scores and blended final score."""
    if is_auto_fail:
        return {cat: 0.0 for cat in category_weights}, 0.0

    grouped = {}
    for r in ratings:
        cat = r.get("category", "General Handling")
        grouped.setdefault(cat, []).append(r)

    cat_scores = {}
    for cat, items in grouped.items():
        score = 100.0
        for item in items:
            if item.get("rating") in ["FAIL", "NO"]:
                deduction = item.get("deduction_value", 10)
                score -= deduction
        
        if score < 0:
            score = 0.0
            
        cat_scores[cat] = float(score)

    total_weight = sum(category_weights.values()) or 1.0
    blended = sum(cat_scores.get(cat, 100.0) * (category_weights.get(cat, 1.0) / total_weight) for cat in category_weights)
    
    if not category_weights:
        blended = sum(cat_scores.values()) / len(cat_scores) if cat_scores else 100.0

    return cat_scores, round(blended, 1)
