from fastapi import FastAPI, HTTPException
import json
import os

app = FastAPI(title="Mock Tenant Config DB")

MOCK_DB = {
    "tenant-abc": {
        "tenant_id": "tenant-abc",
        "category_weights": {
            "Soft Skills": 0.333,
            "Technical Knowledge": 0.667
        },
        "categories": [
            {
                "name": "Soft Skills",
                "line_items": [
                    {"name": "Branding and Survey Check", "description": "Handled by Rule Engine.", "deduction_value": 15},
                    {"name": "Hold time and Dead Air", "description": "Handled by Rule Engine.", "deduction_value": 15},
                    {"name": "Personalized the call/ticket appropriately", "description": "Handled by Rule Engine.", "deduction_value": 15},
                    {"name": "Empathy & Acknowledgment Statement", "description": "Handled by Rule Engine and Snippet LLM.", "deduction_value": 35},
                    {"name": "Build rapport and observed professionalism", "description": "Read the agent's dialogue. Did the agent build rapport AND maintain professionalism? Look for polite language (rapport) and ensure there is ZERO condescending or rude language (professionalism). If they were polite and professional, rate PASS. If they were rude, condescending, or unprofessional, rate FAIL.", "deduction_value": 20}
                ]
            },
            {
                "name": "Technical Knowledge",
                "line_items": [
                    {"name": "Paraphrasing", "description": "Handled dynamically by Vector Engine.", "deduction_value": 15},
                    {"name": "Verified customer", "description": "Handled deterministically by Rule Engine.", "deduction_value": 25},
                    {"name": "Probing", "description": "Based on the customer's problem provided in the context, did the agent ask diagnostic questions to probe this problem? Output YES or NO.", "deduction_value": 25},
                    {"name": "Took ownership of the problem", "description": "Did the agent take ownership of the ticket without blaming other departments or the customer? Output YES or NO.", "deduction_value": 25},
                    {"name": "Active listening", "description": "Handled by Snippet LLM.", "deduction_value": 10},
                    {"name": "Confirmed the issue is resolved", "description": "Did the agent explicitly confirm that the issue was resolved? Output YES or NO.", "deduction_value": 15}
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
    port = int(os.getenv("CONFIG_PORT", 8006))
    uvicorn.run(app, host="0.0.0.0", port=port)
