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
                    {"name": "Personalized the call", "description": "Rate PASS ONLY if the agent explicitly addressed the caller by their verified name at least once. Rate FAIL if they never used the name.", "deduction_value": 15},
                    {"name": "Empathy & Acknowledgment", "description": "Must acknowledge customer frustration or urgency empathetically rather than being blunt or robotic.", "deduction_value": 30},
                    {"name": "Build rapport and observed professionalism", "description": "Agent must be courteous, respectful, adapt to technical pacing, and avoid interrupting.", "deduction_value": 30}
                ]
            },
            {
                "name": "Technical Knowledge",
                "line_items": [
                    {"name": "Paraphrasing", "description": "Must paraphrase the customer's core technical issue to reconfirm understanding.", "deduction_value": 10},
                    {"name": "Verified customer", "description": "Rate PASS ONLY if the agent explicitly validated secure account details (e.g., an account PIN, full address, or security question). Asking for an account number alone triggers an automatic FAIL.", "deduction_value": 20},
                    {"name": "Probing", "description": "Agent must ask logical, clarifying diagnostic questions to isolate root cause before prescribing steps.", "deduction_value": 15},
                    {"name": "Set proper expectations", "description": "Rate FAIL if the agent starts any action taking more than a few seconds — reboot, driver change, hold — without saying how long it will take, even if other next steps are communicated well.", "deduction_value": 10},
                    {"name": "Provided the appropriate solution", "description": "Rate PASS if the actions eventually solved the core issue. ONLY rate FAIL if they gave completely incorrect instructions leaving it broken.", "deduction_value": 25},
                    {"name": "Took ownership of the problem", "description": "Exhaust all available resources and perform active troubleshooting without blaming others.", "deduction_value": 10},
                    {"name": "Active listening", "description": "Avoid asking the customer for information they already provided earlier. Repeated requests for identical information triggers a FAIL.", "deduction_value": 10}
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
