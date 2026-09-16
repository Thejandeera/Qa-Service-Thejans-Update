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
                    {"name": "Personalized the call", "description": "Rate PASS ONLY if the agent explicitly used the customer's name at least once during the call. Rate FAIL if the agent completely avoided using the customer's name.", "deduction_value": 15},
                    {"name": "Empathy & Acknowledgment", "description": "Rate PASS ONLY if the agent explicitly acknowledged the customer's frustration or inconvenience with an empathetic statement. Rate FAIL if the agent ignored the customer's emotions and moved straight to troubleshooting.", "deduction_value": 30},
                    {"name": "Build rapport and observed professionalism", "description": "Rate PASS ONLY if the agent remained perfectly courteous, did not use overly complex technical jargon without explaining it, and maintained a helpful tone. Rate FAIL if the agent was dismissive, sarcastic, or used excessive jargon.", "deduction_value": 30}
                ]
            },
            {
                "name": "Technical Knowledge",
                "line_items": [
                    {"name": "Paraphrasing", "description": "Rate PASS ONLY if the agent explicitly repeated the customer's core issue back to them to confirm understanding early in the call. Rate FAIL if the agent did not paraphrase the issue.", "deduction_value": 10},
                    {"name": "Verified customer", "description": "Rate PASS ONLY if the agent explicitly verified secure account details (e.g., asking for a PIN, address, or last 4 of SSN). Rate FAIL if the agent only asked for a phone number or account number.", "deduction_value": 20},
                    {"name": "Probing", "description": "Rate PASS ONLY if the agent asked multiple effective diagnostic questions to isolate the root cause. Rate FAIL if the agent jumped to a solution without asking probing questions.", "deduction_value": 15},
                    {"name": "Set proper expectations", "description": "Rate PASS ONLY if the agent explicitly provided an accurate timeline or clear expectation of what would happen next (e.g., 'This will take 3 minutes to reboot'). Rate FAIL if the agent left the customer waiting blindly.", "deduction_value": 10},
                    {"name": "Provided the appropriate solution", "description": "Rate PASS ONLY if the agent successfully identified and communicated the correct resolution to the customer's core issue. Rate FAIL if the agent provided a wrong solution or gave up.", "deduction_value": 25},
                    {"name": "Took ownership of the problem", "description": "Rate PASS ONLY if the agent exhausted their own resources before transferring the call or escalating. Rate FAIL if the agent immediately transferred or blamed another department.", "deduction_value": 10},
                    {"name": "Active listening", "description": "Rate PASS ONLY if the agent remembered details the customer already stated. Rate FAIL if the agent asked the customer to repeat information they had already provided (e.g., asking for an account number twice).", "deduction_value": 10}
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
