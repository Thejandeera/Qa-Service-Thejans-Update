from fastapi import FastAPI, HTTPException
import json
import os

app = FastAPI(title="Mock Tenant Config DB")

# In-memory "database"
MOCK_DB = {
    "tenant-abc": {
        "tenant_id": "tenant-abc",
        "category_weights": {
            "Soft Skills": 0.30,
            "Technical Knowledge": 0.70
        },
        "categories": [
            {
                "name": "Soft Skills",
                "line_items": [
                    {"name": "Empathy & Acknowledgment", "description": "Provided empathy", "deduction_value": 15},
                    {"name": "Personalized the call", "description": "Used customer name", "deduction_value": 5}
                ]
            },
            {
                "name": "Technical Knowledge",
                "line_items": [
                    {"name": "Provided the appropriate solution", "description": "Solved core issue", "deduction_value": 40},
                    {"name": "Active listening", "description": "Avoided asking for repeated info", "deduction_value": 10}
                ]
            }
        ]
    }
}

@app.get("/api/criteria/{tenant_id}")
def get_criteria(tenant_id: str):
    if tenant_id in MOCK_DB:
        return MOCK_DB[tenant_id]
    
    # Return a default if not found
    return MOCK_DB.get("tenant-abc")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
