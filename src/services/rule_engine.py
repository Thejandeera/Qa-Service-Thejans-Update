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
