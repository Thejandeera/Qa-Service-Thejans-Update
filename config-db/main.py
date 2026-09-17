from fastapi import FastAPI, HTTPException
import json
import os

app = FastAPI(title="Mock Tenant Config DB")

MOCK_DB = {
    "tenant-abc": {
        "tenant_id": "tenant-abc",
        "category_weights": {
            "Soft Skills": 0.40,
            "Technical Knowledge": 0.60
        },
        "categories": [
            {
                "name": "Soft Skills",
                "line_items": [
                    {"name": "Personalized the call", "description": "Read the agent's dialogue. Did the agent explicitly use the caller's name during the conversation? If YES, rate PASS. If NO, rate FAIL.", "deduction_value": 15},
                    {"name": "Empathy & Acknowledgment", "description": "Default to PASS. Search for violations. Rate FAIL ONLY if the agent was explicitly dismissive, ignored a customer's complaint, or responded to frustration with robotic/irrelevant scripting. If no active violations are found, rate PASS.", "deduction_value": 30},
                    {"name": "Build rapport and observed professionalism", "description": "Read the agent's dialogue. Did the agent build rapport AND maintain professionalism? Look for polite language (rapport) and ensure there is ZERO condescending or rude language (professionalism). If they were polite and professional, rate PASS. If they were rude, condescending, or unprofessional, rate FAIL.", "deduction_value": 30}
                ]
            },
            {
                "name": "Technical Knowledge",
                "line_items": [
                    {"name": "Paraphrasing", "description": "Handled dynamically by Vector Engine.", "deduction_value": 15},
                    {"name": "Verified customer", "description": "Handled deterministically by Rule Engine.", "deduction_value": 20},
                    {"name": "Probing", "description": "Based on the customer's problem provided in the context, did the agent ask diagnostic questions to probe this problem? Output YES or NO.", "deduction_value": 15},
                    {"name": "Set proper expectations", "description": "Did the agent set proper expectations (e.g., 'this will take 2 minutes') before taking action? Output YES or NO.", "deduction_value": 10},
                    {"name": "Provided the appropriate solution", "description": "Based ONLY on the agent's actions, did they provide an appropriate solution to fix the customer's specific problem provided in the context? Output YES or NO.", "deduction_value": 15},
                    {"name": "Took ownership of the problem", "description": "Did the agent take ownership of the ticket without blaming other departments or the customer? Output YES or NO.", "deduction_value": 5},
                    {"name": "Active listening", "description": "Did the agent avoid asking the customer for information that they had already provided earlier? Output YES or NO.", "deduction_value": 5}
                ]
            }
        ]
    }
}

@app.get("/api/criteria/{tenant_id}")
def get_criteria(tenant_id: str):
    return MOCK_DB.get(tenant_id, MOCK_DB["tenant-abc"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
