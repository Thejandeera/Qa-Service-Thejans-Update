from typing import List, Tuple, Optional, Dict, Any
import difflib

def similar(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def evaluate_branding(turns: List[Tuple[str, str]]) -> Dict[str, Any]:
    agent_lines = [txt for spk, txt in turns if spk.lower() == "agent"]
    
    if not agent_lines:
        return {
            "category": "Soft Skills",
            "name": "Branding and Survey Check",
            "rating": "FAIL",
            "score": 0,
            "coaching": "No agent lines found in the transcript."
        }
        
    first_4 = " ".join(agent_lines[:4]).lower()
    last_4 = " ".join(agent_lines[-4:]).lower()
    
    greeting_match = False
    closing_match = False
    
    if "thank you for calling s-net" in first_4:
        greeting_match = True
        
    if "thank you for choosing s-net" in last_4:
        closing_match = True

    if greeting_match and closing_match:
        return {
            "category": "Soft Skills",
            "name": "Branding and Survey Check",
            "rating": "PASS",
            "score": 100,
            "coaching": ""
        }
    else:
        missed = []
        if not greeting_match: missed.append("Greeting")
        if not closing_match: missed.append("Closing")
        return {
            "category": "Soft Skills",
            "name": "Branding and Survey Check",
            "rating": "FAIL",
            "score": 0,
            "deduction_value": 10,
            "coaching": f"Agent missed verbatim scripts for: {', '.join(missed)}"
        }

def evaluate_hold_and_dead_air(turns: List[Tuple[str, str]], parsed_times: List[Tuple[int, int]]) -> Dict[str, Any]:
    if not parsed_times or len(parsed_times) != len(turns) or all(not isinstance(t, tuple) for t in parsed_times):
        return {
            "category": "Soft Skills",
            "name": "Hold time and Dead Air",
            "rating": "PASS",
            "score": 100,
            "coaching": ""
        }
        
    dead_air_count = 0
    max_gap = 0
    
    for i in range(1, len(parsed_times)):
        prev_end = parsed_times[i-1][1]
        curr_start = parsed_times[i][0]
        
        if prev_end is not None and curr_start is not None:
            gap = curr_start - prev_end
            if gap > max_gap:
                max_gap = gap
            if gap > 30:
                dead_air_count += 1
                
    if dead_air_count >= 2:
        return {
            "category": "Soft Skills",
            "name": "Hold time and Dead Air",
            "rating": "FAIL",
            "score": 0,
            "deduction_value": 15,
            "coaching": f"Dead Air Breach: Agent had {dead_air_count} occurrences of >30s dead air (max gap {max_gap}s)."
        }
        
    return {
        "category": "Soft Skills",
        "name": "Hold time and Dead Air",
        "rating": "PASS",
        "score": 100,
        "coaching": ""
    }

def evaluate_empathy(turns: List[Tuple[str, str]]) -> Dict[str, Any]:
    frustration_words = ["broken", "issue", "problem", "frustrat", "angry", "unacceptable", "cancel", "outage"]
    empathy_words = ["sorry", "apologize", "understand", "frustrating", "tough", "empathize"]
    acknowledgment_words = ["right", "got it", "makes sense", "i see", "absolutely", "certainly"]
    
    combined_nice_words = empathy_words + acknowledgment_words

    frustration_instances = 0
    empathy_responses = 0
    global_nice_word_count = 0

    for i, (speaker, text) in enumerate(turns):
        lower_text = text.lower()
        if speaker.lower() == "agent":
            # Tier 1 Global Count: Count occurrences of empathy/acknowledgment words
            for word in combined_nice_words:
                global_nice_word_count += lower_text.count(word)

        elif speaker.lower() == "customer":
            # Tier 2 tracking: Check if customer expressed frustration
            if any(word in lower_text for word in frustration_words):
                frustration_instances += 1
                
                # Check next 1-2 agent turns for empathy/acknowledgment
                agent_responded_well = False
                for j in range(i+1, min(i+3, len(turns))):
                    next_spk, next_txt = turns[j]
                    if next_spk.lower() == "agent":
                        if any(eword in next_txt.lower() for eword in combined_nice_words):
                            agent_responded_well = True
                            break
                if agent_responded_well:
                    empathy_responses += 1

    # Tier 1: Fast-Pass if they used enough nice words globally (>= 4 times)
    if global_nice_word_count >= 4:
        return {
            "category": "Soft Skills",
            "name": "Empathy & Acknowledgment",
            "rating": "PASS",
            "score": 100,
            "coaching": ""
        }

    # Tier 3: No frustration detected and they didn't hit the global fast-pass
    if frustration_instances == 0:
        return {
            "category": "Soft Skills",
            "name": "Empathy & Acknowledgment",
            "rating": "PASS",
            "score": 100,
            "coaching": ""
        }
    
    # Tier 2: 75% Reaction Check (Since global count was < 4)
    ratio = empathy_responses / frustration_instances
    if ratio >= 0.75:
        return {
            "category": "Soft Skills",
            "name": "Empathy & Acknowledgment",
            "rating": "PASS",
            "score": 100,
            "coaching": ""
        }
    else:
        return {
            "category": "Soft Skills",
            "name": "Empathy & Acknowledgment",
            "rating": "FAIL",
            "score": 0,
            "deduction_value": 30,
            "coaching": f"Agent used <4 empathy/acknowledgment words overall, and only responded nicely to {empathy_responses} out of {frustration_instances} customer frustrations ({(ratio*100):.0f}%). Target is 75%."
        }

def evaluate_verified_customer(turns: List[Tuple[str, str]], parsed_times: List[Tuple[int, int]]) -> Dict[str, Any]:
    """
    Scans the first 4 minutes (240 seconds) for verification keywords.
    NOTE: These keywords and timeframes should be moved to a tenant-configurable dictionary in the future.
    """
    verification_keywords = ["pin", "address", "security question"]
    agent_verified = False
    
    for i, (speaker, text) in enumerate(turns):
        if speaker.lower() == "agent":
            # Check if this turn is within the first 4 minutes (240 seconds)
            start_time = parsed_times[i][0] if i < len(parsed_times) and parsed_times[i] and parsed_times[i][0] is not None else 0
            if start_time <= 240:
                lower_text = text.lower()
                if any(kw in lower_text for kw in verification_keywords):
                    agent_verified = True
                    break
                    
    if agent_verified:
        return {
            "category": "Technical Knowledge",
            "name": "Verified customer",
            "rating": "PASS",
            "score": 100,
            "coaching": ""
        }
    else:
        return {
            "category": "Technical Knowledge",
            "name": "Verified customer",
            "rating": "FAIL",
            "score": 0,
            "deduction_value": 20,
            "coaching": "Agent failed to ask for a PIN, address, or security question within the first 4 minutes of the call."
        }
