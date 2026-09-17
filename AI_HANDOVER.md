# AI Handover Guide: Gemma QA Analysis System

Hello! If you are an AI assistant (like Claude) taking over this project, this document is your map. It contains the hard-won context, architectural decisions, and LLM constraints that shape this codebase.

## Project Overview
This is an asynchronous, decoupled QA grading system. It takes in 15-25 minute customer service transcripts via a REST API, parses them, and grades them against 15 criteria using a mix of deterministic Python rules and local LLM inference (Llama 3.1 8B running in Ollama). 

## Core Architecture
- **Gateway (`src/api/web_app.py`)**: A FastAPI server on port 8000. It receives the transcript, pushes it to Celery, and immediately returns a `job_id`.
- **Message Broker (`redis:alpine`)**: Handles the Celery queue. Results are stored here (no persistent DB).
- **Orchestrator Worker (`src/services/orchestrator_worker.py`)**: The main Celery worker. It delegates tasks to the rule engine and the LLM adapter.
- **Rule Engine (`src/services/rule_engine.py`)**: Runs *deterministic* checks purely in Python to save tokens (e.g., verifying if the exact "thank you for calling" script was used, and calculating >30s dead air gaps).
- **LLM Adapter & Evaluator (`src/services/llm_adapter.py` & `dynamic_evaluator.py`)**: Stitches together the dynamic prompt and queries Ollama. **Note:** It queries in chunks. It caches the transcript as a prefix, then sends category criteria (Soft Skills, Technical Knowledge) sequentially to prevent JSON truncation on long outputs.
- **Config-DB (`config-db/main.py`)**: A mock FastAPI database on port 8080 that stores the tenant grading rubrics, descriptions, and point weights.

## The LLM Constraints (CRITICAL CONTEXT)
We are running a small local model (Llama 3.1 8B). Through rigorous testing, we discovered it has severe limitations that forced us into specific prompt engineering strategies. **Do not undo these strategies without upgrading the model.**

1. **The "Poison Word" Trap**: The 8B model cannot handle negative boolean constraints (e.g., "Asking for an account number *alone* is a fail"). It just sees "account number" and panic-fails. 
   * **Solution:** Strict criteria (like *Verified Customer*) must use purely positive language: "Must explicitly ask for a PIN... else FAIL."
2. **The "Lazy Exit" Trap**: The 8B model is heavily biased toward passing bad agents if the instructions are too vague. 
   * **Solution:** For subjective criteria (Empathy, Rapport, Ownership), we use **Hybrid Violation-Based Grading**. The `config-db` descriptions explicitly say: *"Default to PASS. Rate FAIL ONLY if the agent [specific bad behavior]."*. This turns abstract grading into a concrete search-and-destroy mission.
3. **The "Context Fog"**: The 8B model struggles to cross-reference facts stated 10 minutes apart in a 3,000-token transcript (e.g., Active Listening). It is at its ceiling here.

## Directory Structure
- `config-db/`: The mock database holding the rubrics.
- `inputs/`: Folder containing test JSON transcripts. (Outputs from batch tests go into `inputs/Test (results)/`).
- `resources/prompts/`: Contains `dynamic_evaluation_prompt.txt`, the core LLM instruction template.
- `src/`: Core application logic (API, Celery workers, evaluation engine).

## How to Test
We built a local client to automate testing so you don't need Postman.
1. Place your target JSON transcripts in the `inputs/` folder.
2. Edit `batch_test.py` to point to your specific file (or let it run the whole folder).
3. Run `python batch_test.py`. It will POST the file, poll the status endpoint, and save the final scorecard JSON to `inputs/Test (results)/`.

## Common Commands
* Rebuild and restart workers after changing Python code: `docker-compose build orchestrator-worker && docker-compose up -d orchestrator-worker`
* Rebuild config-db after changing rubrics: `docker-compose build config-db && docker-compose up -d config-db`
* Check orchestrator logs (where most errors happen): `docker-compose logs -f orchestrator-worker`
