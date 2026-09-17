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
                    {"name": "Empathy & Acknowledgment", "description": "Default to PASS. Search for violations. Rate FAIL ONLY if the agent was explicitly dismissive, ignored a customer's complaint, or responded to frustration with robotic/irrelevant scripting. If no active violations are found, rate PASS.", "deduction_value": 30},
                    {"name": "Build rapport and observed professionalism", "description": "Default to PASS. Rate FAIL ONLY if the agent interrupted the customer, used condescending language, or escalated the tension.", "deduction_value": 30}
                ]
            },
            {
                "name": "Technical Knowledge",
                "line_items": [
                    {"name": "Paraphrasing", "description": "Must paraphrase the customer's core technical issue to reconfirm understanding.", "deduction_value": 10},
                    {"name": "Verified customer", "description": "Must explicitly ask for a PIN, address, or security question to PASS. else FAIL.", "deduction_value": 20},
                    {"name": "Probing", "description": "Default to PASS. Rate FAIL ONLY if the agent blindly prescribed a fix without asking any diagnostic questions first, or immediately deflected to another department without attempting to isolate the issue.", "deduction_value": 15},
                    {"name": "Set proper expectations", "description": "Rate FAIL if the agent starts any action taking more than a few seconds — reboot, driver change, hold — without saying how long it will take, even if other next steps are communicated well.", "deduction_value": 10},
                    {"name": "Provided the appropriate solution", "description": "Rate PASS if the actions eventually solved the core issue. ONLY rate FAIL if they gave completely incorrect instructions leaving it broken.", "deduction_value": 25},
                    {"name": "Took ownership of the problem", "description": "Default to PASS. Rate FAIL ONLY if the agent blamed another department, refused to help, or attempted to end the call before troubleshooting was finished.", "deduction_value": 10},
                    {"name": "Active listening", "description": "Default to PASS. Rate FAIL ONLY if you catch the agent asking the customer to repeat a specific piece of information that the customer had already clearly stated earlier.", "deduction_value": 10}
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
