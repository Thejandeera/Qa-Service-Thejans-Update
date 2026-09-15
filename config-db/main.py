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
                    {"name": "Personalized the call", "description": "Used customer name", "deduction_value": 15},
                    {"name": "Empathy & Acknowledgment", "description": "Provided empathy", "deduction_value": 30},
                    {"name": "Build rapport and observed professionalism", "description": "Courteous, no jargon", "deduction_value": 30}
                ]
            },
            {
                "name": "Technical Knowledge",
                "line_items": [
                    {"name": "Paraphrasing", "description": "Paraphrased the issue", "deduction_value": 10},
                    {"name": "Verified customer", "description": "Verified account details securely", "deduction_value": 20},
                    {"name": "Probing", "description": "Asked effective questions", "deduction_value": 15},
                    {"name": "Set proper expectations", "description": "Provided accurate timelines", "deduction_value": 10},
                    {"name": "Provided the appropriate solution", "description": "Solved core issue", "deduction_value": 25},
                    {"name": "Took ownership of the problem", "description": "Exhausted resources before transfer", "deduction_value": 10},
                    {"name": "Active listening", "description": "Avoided asking for repeated info", "deduction_value": 10}
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
