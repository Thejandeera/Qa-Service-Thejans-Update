# Gemma QA Analysis System

An enterprise-grade, 100% locally-hosted, microservices-driven Quality Assurance (QA) evaluation engine for customer support transcripts. 

The system leverages **Llama 3.1 (8B)** via **Ollama** for semantic reasoning, soft-skills evaluation, technical assessment, and dynamic coaching generation, coupled with a deterministic **Python Rule Engine** for exact mathematical Service Level Agreement (SLA) calculations (Dead Air, Hold Times, and Verbatim Branding scripts).

---

## Table of Contents
1. [System Architecture Overview](#1-system-architecture-overview)
2. [Prerequisites & Requirements](#2-prerequisites--requirements)
3. [Quickstart Setup Guide](#3-quickstart-setup-guide)
4. [Ollama LLM Model Setup](#4-ollama-llm-model-setup)
5. [API Specification & Data Contracts](#5-api-specification--data-contracts)
6. [The 15 QA Evaluation Criteria](#6-the-15-qa-evaluation-criteria)
7. [Mathematical Scoring & Circuit Breakers](#7-mathematical-scoring--circuit-breakers)
8. [Test Payloads & Postman Guide](#8-test-payloads--postman-guide)
9. [Development & Codebase Synchronization](#9-development--codebase-synchronization)

---

## 1. System Architecture Overview

The system runs completely detached from third-party cloud APIs to guarantee privacy and security. It is built as a set of decoupled containers orchestrated via Docker Compose and Celery:

```
                  ┌─────────────────────────────────────────┐
                  │          Client / Postman               │
                  └───────┬─────────────────────────▲───────┘
                          │ 1. POST /api/evaluate   │ 6. GET /api/status/{job_id}
                          ▼                         │
                  ┌─────────────────────────────────┴───────┐
                  │      API Gateway (FastAPI :8000)        │
                  └───────┬─────────────────────────────────┘
                          │ 2. Enqueue Job ('orchestrate_evaluation')
                          ▼
                  ┌─────────────────────────────────────────┐
                  │            Redis Broker (:6379)         │
                  └───────┬─────────────────────────────────┘
                          │ 3. Dequeue Job
                          ▼
                  ┌─────────────────────────────────────────┐
                  │    Orchestrator Worker (Celery Brain)   │
                  └───────┬─────────────────────────┬───────┘
                          │                         │
     4a. Timestamp Gaps & │                         │ 4b. Clean Transcript &
         Verbatim Checks  │                         │     Targeted Criteria
                          ▼                         ▼
            ┌──────────────────────────┐     ┌──────────────────────────┐
            │   Python Rule Engine     │     │    Ollama LLM Service    │
            │  (Branding & Dead Air)   │     │  (:11434 / llama3.1:8b)  │
            └─────────────┬────────────┘     └──────────────┬───────────┘
                          │                                 │
                          │   5. Blended Scoring, Auto-Fail │
                          │      Checks & Coaching Feedback │
                          └────────────────►◄───────────────┘
```

### Microservices Breakdown
* **`gateway` (FastAPI, Port 8000):** Non-blocking HTTP entry point. Validates requests via Pydantic, dispatches asynchronous tasks to Redis, and queries task completion statuses.
* **`redis` (Redis Alpine, Port 6379):** High-throughput message broker and Celery result backend.
* **`config-db`:** Provides criteria logic and configuration (e.g., hybrid evidence-based grading rules) for the orchestrator.
* **`ollama` (Ollama Engine, Port 11434):** Hosts and executes local quantized models (`llama3.1:latest`).
* **`orchestrator-worker` (Celery Worker):** Coordinates the end-to-end evaluation pipeline: splits timing data, calls the rule engine synchronously, chunks LLM evaluation categories, triggers coaching inference on failures, and computes blended scores.

---

## 2. Prerequisites & Requirements

* **Operating System:** Windows 10/11 (with WSL2 enabled), macOS, or Linux.
* **Docker Engine & Docker Compose:** Docker Desktop with Linux containers enabled.
* **Hardware Allocation:**
  * **RAM:** Minimum 16 GB system memory (at least 8 GB allocated to Docker).
  * **Disk Space:** At least 15 GB free disk space (to store the base Docker images and the 4.7 GB Llama 3.1 model weights).
  * **CPU/GPU:** Multi-core modern processor (AVX2 support). NVIDIA GPU with CUDA passthrough is optional but significantly accelerates inference.

---

## 3. Quickstart Setup Guide

### 1. Clone the repository and checkout `version-3`:
```bash
git clone https://github.com/nimjj/QA-system.git
cd QA-system
git checkout version-3
```

### 2. Launch the container cluster:
```bash
docker-compose up --build -d
```
Verify that all services are healthy and running:
```bash
docker ps
```
You should see 5 active containers:
* `gemma-qa-analysis-gateway-1`
* `gemma-qa-analysis-orchestrator-worker-1`
* `gemma-qa-analysis-config-db-1`
* `gemma-qa-analysis-redis-1`
* `gemma-qa-analysis-ollama-1`

---

## 4. Ollama LLM Model Setup

Because the LLM runs locally, model weights must be pulled once into the persistent `ollama_data` Docker volume.

### Pull Llama 3.1:
Run the following command directly inside the container:
```bash
docker exec -it gemma-qa-analysis-ollama-1 ollama run llama3.1
```
* **Download Size:** ~4.7 GB.
* **Download Duration:** Approximately 5–15 minutes depending on connection speed.
* Once the prompt appears (`>>>`), type `/bye` and hit **Enter** to exit. The model weights are permanently cached.

---

## 5. API Specification & Data Contracts

### 1. Ingest Transcript for Evaluation
* **Endpoint:** `POST /api/evaluate`
* **Content-Type:** `application/json`

#### Request Payload Model (`EvaluateRequest`):
```json
{
  "channel": "Call",
  "agent_name": "Alex",
  "custom_prompt": null,
  "transcript": [
    {
      "speaker": "agent",
      "start_time": "[00:00]",
      "end_time": "[00:05]",
      "text": "Thank you for calling S-Net. My name is Alex. May I have your account number and PIN to verify your account?"
    },
    {
      "speaker": "customer",
      "start_time": "[00:06]",
      "end_time": "[00:15]",
      "text": "Hi, my name is John Smith. My account number is 883-992-110 and my PIN is 1234. My internet is completely down."
    }
  ]
}
```

#### Turn Object Schema:
| Field | Type | Default | Description |
|---|---|---|---|
| `speaker` | `string` | **Required** | The entity speaking (`"agent"` or `"customer"`). |
| `text` | `string` | **Required** | The verbatim dialog utterance. |
| `start_time` | `string` | `null` | String timestamp (e.g., `"[00:00]"`, `"[15:30]"`, `"01:05:20"`). |
| `end_time` | `string` | `null` | String timestamp matching start format. |
| `start_time_sec` | `integer` | `0` | Optional integer offset in seconds (used if string timestamp is absent). |
| `end_time_sec` | `integer` | `0` | Optional integer offset in seconds. |

#### Synchronous Response:
```json
{
  "job_id": "c52b4b99-30c7-40fd-b41b-37f60b3c9919",
  "status": "processing",
  "created_at": "2026-09-10T15:00:50.006123"
}
```

---

### 2. Poll Evaluation Status & Results
* **Endpoint:** `GET /api/status/{job_id}`

#### Response (While Processing):
```json
{
  "status": "processing"
}
```

#### Response (Upon Completion):
```json
{
  "status": "completed",
  "result": {
    "final_score": 100.0,
    "is_auto_fail": false,
    "auto_fail_reason": null,
    "category_scores": {
      "Soft Skills": 100.0,
      "Technical Knowledge": 100.0,
      "Auto Fail Category": 100.0
    },
    "scorecard": [
      {
        "category": "Soft Skills",
        "name": "Branding and Survey Check",
        "rating": "PASS",
        "coaching": ""
      },
      {
        "category": "Soft Skills",
        "name": "Hold time and Dead Air",
        "rating": "PASS",
        "coaching": ""
      },
      {
        "category": "Soft Skills",
        "name": "Personalized the call/ticket appropriately",
        "rating": "PASS",
        "coaching": ""
      },
      {
        "category": "Technical Knowledge",
        "name": "Verified customer",
        "rating": "FAIL",
        "coaching": "Verify the customer's account information and confirm their identity using two points of ID before proceeding."
      }
    ],
    "summary": "Customer internet restored following profile reconfiguration.",
    "evaluation_id": "c52b4b99-30c7-40fd-b41b-37f60b3c9919"
  }
}
```

---

## 6. The 15 QA Evaluation Criteria

The system evaluates agents across 15 rigorous criteria categorized into three operational sections:

### Category 1: Soft Skills (Weight: 33.3%)
1. **Branding and Survey Check (Rule Engine):**
   * *Rule:* Must contain `"thank you for calling s-net"` in the first 4 agent utterances AND `"thank you for choosing s-net"` in the last 4 agent utterances.
2. **Hold time and Dead Air (Rule Engine):**
   * *Rule:* Any turn transition gap exceeding **20 seconds** is flagged as Dead Air. Up to **2 exceptions** are tolerated (e.g., communicated holds). If **3 or more** gaps occur, the item receives a strict FAIL.
3. **Personalized the call/ticket appropriately (LLM):**
   * *Rule:* Rate PASS ONLY if the agent explicitly addresses the customer by their verified name (e.g., "John") during the conversation. Rate FAIL if the agent never refers to the customer by name.
4. **Empathy & Acknowledgment Statement (LLM):**
   * *Rule:* Default to PASS. Rate FAIL ONLY if the agent is blunt or dismissive instead of providing empathy statements acknowledging frustration or stress.
5. **Build rapport and observed professionalism (LLM):**
   * *Rule:* Default to PASS. Rate FAIL ONLY if the agent is discourteous, interrupts, or uses unprofessional sounds or slang.

### Category 2: Technical Knowledge (Weight: 66.7%)
6. **Paraphrasing (LLM):**
   * *Rule:* Must paraphrase and reconfirm the core issue at the onset of the call to align expectations.
7. **Verified customer (LLM):**
   * *Rule:* Rate PASS ONLY if the agent explicitly validates secure account credentials (e.g., account PIN, billing address, security questions). Requesting an account number alone triggers an automatic FAIL.
8. **Probing (LLM):**
   * *Rule:* Default to PASS. Rate FAIL ONLY if the agent prescribes steps without using effective, open-ended probing questions to identify the root cause.
9. **Set proper expectations (LLM):**
   * *Rule:* Explicitly communicates expected wait times, troubleshooting duration, and updates before taking actions or initiating holds.
10. **Provided the appropriate solution (LLM):**
    * *Rule:* Rate PASS if the agent's actions eventually solved the customer's technical issue (verified by customer confirmation). Rate FAIL only if instructions were invalid or left the customer broken.
11. **Took ownership of the problem (LLM):**
    * *Rule:* Default to PASS. Rate FAIL ONLY if the agent deflects blame onto other departments (e.g., sales, IT, or field techs) instead of taking personal responsibility.
12. **Active listening (LLM):**
    * *Rule:* Avoids asking the caller for information already provided. Asking for repeated information 2 or more times triggers a FAIL.
13. **Confirmed the issue is resolved (LLM):**
    * *Rule:* Secures explicit verbal confirmation that the service is functional, invites the user to test, and summarizes the fix.

### Category 3: Auto-Fail Circuit Breakers (Weight: 0.0% / Instant Override)
14. **Escalation (LLM):**
    * *Rule:* ONLY rate FAIL if the customer explicitly demands a supervisor/manager OR threatens cancellation, and the agent refuses or neglects to transfer. Frustration alone must NOT trigger a failure.
15. **Non-First Call Resolution (LLM):**
    * *Rule:* Rate PASS if the issue was resolved on this call. Rate FAIL if the customer was instructed to call back later, was hung up on, or ended the call unresolved.

---

## 7. Mathematical Scoring & Circuit Breakers

### 1. Item Scoring
* `PASS` = 100 points
* `FAIL` / `NO` = 0 points

### 2. Category Scoring Formula
Each category score is the arithmetic mean of its constituent line items:
$$\text{Category Score} = \frac{\sum \text{Item Scores}}{\text{Total Items in Category}}$$

*Example:* If **Soft Skills** has 5 line items and 1 item fails:
$$\text{Soft Skills Score} = \frac{100 + 100 + 100 + 100 + 0}{5} = 80.0\%$$

### 3. Weighted Final Blended Score
$$\text{Final Score} = (\text{Soft Skills} \times 0.333) + (\text{Technical Knowledge} \times 0.667) + (\text{Auto Fail} \times 0.000)$$

### 4. Circuit Breakers (Zero-Tolerance Overrides)
The `final_score` and all category scores are immediately overwritten to **`0.0`** if any of the following occur:
1. **Profanity or Hostility:** Detects forbidden derogatory language in the transcript text.
2. **Extreme Hostility:** 3 or more hostile agent statements detected.
3. **Auto-Fail Category Breach:** Either **Escalation** or **Non-First Call Resolution** receives a `FAIL`.

---

## 8. Test Payloads & Postman Guide

Three pre-calibrated test payloads spanning **30 minutes of call duration** are checked into the repository under `tests/payloads/`:

| Payload File | Target Score | Auto-Fail | Key Scenarios Tested |
|---|---|---|---|
| **`perfect_call_payload.json`** | **`100.0`** | `false` | 45 turns. Flawless verification with PIN, two communicated diagnostic holds (2 gaps within the 2-exception dead air limit), verbatim branding greetings/closings, full ownership. |
| **`mediocre_call_payload.json`** | **`25.0`** | `false` | Solves internet outage but fails soft skills and customer verification. Triggers **23 occurrences of Dead Air** (>20s). Avoids auto-fails. |
| **`catastrophic_call_payload.json`** | **`0.0`** | `true` | Agent refuses supervisor requests, ignores cancellation threats, leaves 4 uncommunicated gaps (>5 min each), misses branding, and tells customer to "call back tomorrow." |

### Executing Tests in Postman:
1. Create a `POST` request to `http://localhost:8000/api/evaluate`.
2. Select **Body** > **binary**.
3. Click **Select file** and choose `tests/payloads/perfect_call_payload.json` (or paste raw JSON under **Body** > **raw**).
4. Send request and note the returned `job_id`.
5. Create a `GET` request to `http://localhost:8000/api/status/{job_id}` and poll until `"status": "completed"`.

---

## 9. Development & Codebase Synchronization

Because the Celery workers and FastAPI run inside isolated Docker containers without live volume mount overrides on production containers, **any code or prompt modifications requires a container rebuild**:

```bash
docker-compose up -d --build gateway orchestrator-worker config-db
```

### Checking Worker Logs:
To observe real-time evaluation logs and coaching generation:
```bash
docker logs -f gemma-qa-analysis-orchestrator-worker-1
```
