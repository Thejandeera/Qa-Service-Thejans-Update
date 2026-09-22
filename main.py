"""Root launcher for the LLM QA Analysis application."""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
TESTS_DIR = os.path.join(ROOT_DIR, "tests")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 8005))
    
    from api.web_app import app, logger
    logger.info(f"Starting LLM QA Analysis Web Server on http://{host}:{port}...")
    print(f"Starting LLM QA Analysis Web Server on http://{host}:{port}...")
    uvicorn.run(app, host=host, port=port)

