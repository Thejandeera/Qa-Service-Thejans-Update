# System Architecture & Technical Specifications

This document provides a comprehensive, exhaustive technical specification of the **Gemma QA Analysis System**. It details the end-to-end execution lifecycle, decoupled microservices topology, deterministic timing algorithms, LLM prompting strategies, and mathematical scoring formulas down to the exact decimal.

---

## Table of Contents
1. [End-to-End System Execution Lifecycle](#1-end-to-end-system-execution-lifecycle)
2. [Microservices Topology & Container Ecosystem](#2-microservices-topology--container-ecosystem)
3. [Data Ingestion & Sanitization Engine](#3-data-ingestion--sanitization-engine)
4. [Deterministic Rule Engine (Timing & SLAs)](#4-deterministic-rule-engine-timing--slas)
5. [LLM Evaluation Pipeline & Prompt Engineering](#5-llm-evaluation-pipeline--prompt-engineering)
6. [Dynamic Coaching Generation Subsystem](#6-dynamic-coaching-generation-subsystem)
7. [Mathematical Scoring Engine & Circuit Breakers](#7-mathematical-scoring-engine--circuit-breakers)
8. [Asynchronous Polling & State Persistence](#8-asynchronous-polling--state-persistence)
9. [Codebase Map & Module Reference](#9-codebase-map--module-reference)

---

## 1. End-to-End System Execution Lifecycle

The evaluation pipeline is built as a non-blocking, asynchronous pipeline. Below is the sequential execution flow from ingress to final scorecard retrieval:

```
[Client / Postman]
       │
       │  1. HTTP POST /api/evaluate (JSON Payload)
       ▼
[API Gateway (FastAPI)]
       │
       │  2. Validate Pydantic Schema (List[Turn] or raw string)
       │  3. Celery.send_task('orchestrate_evaluation', args=[...])
       │  4. Return HTTP 200 { "job_id": UUID, "status": "processing" }
       ▼
[Redis Message Broker (Queue: 'celery')]
       │
       │  5. Dequeue Task
       ▼
[Orchestrator Worker (Celery / Python 3.11)]
       │
       ├─────────────────────────────────────────┐
       │ Step A: Data Sanitization               │ Step B: Parallel Deterministic Engine
       │ • Extract timestamps into seconds       │ • Run evaluate_branding(turns)
       │ • Strip timestamps from text dialogue   │ • Run evaluate_hold_and_dead_air(parsed_times)
       ▼                                         ▼
[Clean Transcript Built]                   [Rule Results Generated]
       │                                         │
       ├─────────────────────────────────────────┘
       │
       │ Step C: Dynamic Criteria Extraction
       │ • Load 15 criteria across 3 categories
       │
       │ Step D: Map-Reduce LLM Evaluation
       ▼
[Ollama Service (Port 11434 / llama3.1:8b)]
       │ • Send Category Evaluation Prompt
       │ • Parse PASS / FAIL ratings via regex
       ▼
[Scorecard Ratings Extracted]
       │
       │ Step E: Check Auto-Fail Circuit Breakers
       │ • Check profanity blacklist
       │ • Check harsh lines threshold (>= 3)
       │ • Check Auto Fail Category failures (Escalation / Non-FCR)
       │
       │ Step F: Dynamic Coaching Phase (if any line item FAILED)
       ▼
[Ollama Service (Port 11434 / JSON Mode)]
       │ • Prompt LLM per failed item: 1-2 sentence coaching tip
       │ • Inject coaching into scorecard coaching field
       ▼
[Step G: Mathematical Scoring Engine]
       │ • Compute Category Means: sum(scores) / count
       │ • Apply Category Weights: Soft Skills (33.3%), Tech (66.7%), Auto-Fail (0.0%)
       │ • If Auto-Fail triggered: Override all category scores & final score to 0.0
       ▼
[Step H: Semantic Summary Generation]
       │ • Generate context-aware 60-70 char summary
       ▼
[Redis Result Backend]
       │ • Store final JSON scorecard under task ID
       ▼
[Client / Postman Polling]
       │  6. HTTP GET /api/status/{job_id}
       ▲  7. Return HTTP 200 { "status": "completed", "result": {...} }
```

---

## 2. Microservices Topology & Container Ecosystem

The application environment comprises 5 decoupled containerized services defined in `docker-compose.yml`:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Docker Network: default                       │
│                                                                         │
│  ┌────────────────────────┐                   ┌──────────────────────┐  │
│  │        gateway         │◄─(HTTP :8000)─────┤    Host / Client     │  │
│  └───────────┬────────────┘                   └──────────────────────┘  │
│              │                                                          │
│              ▼ (Redis Protocol :6379)                                   │
│  ┌────────────────────────┐                   ┌──────────────────────┐  │
│  │         redis          │◄─────────────────►│      config-db       │  │
│  └───────────▲────────────┘                   └──────────────────────┘  │
│              │                                                          │
│              ▼                                                          │
│  ┌────────────────────────┐                   ┌──────────────────────┐  │
│  │  orchestrator-worker   ├────(HTTP :11434)─►│        ollama        │  │
│  └────────────────────────┘                   └──────────┬───────────┘  │
│                                                          │              │
│                                                          ▼              │
│                                                 ┌──────────────────┐    │
│                                                 │   ollama_data    │    │
│                                                 │ (Docker Volume)  │    │
│                                                 └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Detailed Service Specifications

| Service Name | Base Image | Internal Port | Host Port | Primary Responsibilities |
|---|---|---|---|---|
| **`gateway`** | `python:3.11-slim` | `8000` | `8000` | FastAPI ASGI web server running via Uvicorn. Handles ingestion, payload validation, Redis task dispatching, and status polling. |
| **`redis`** | `redis:alpine` | `6379` | `6379` | In-memory message broker (Celery default queue) and Celery result persistence backend (database `0`). |
| **`config-db`** | `python:3.11-slim` | N/A | N/A | Provides criteria logic and configuration (e.g., hybrid evidence-based grading rules). |
| **`ollama`** | `ollama/ollama:latest` | `11434` | `11434` | Local LLM inference server. Mounts persistent volume `ollama_data` at `/root/.ollama` where model weights (`llama3.1:latest`, ~4.7 GB) reside. |
| **`orchestrator-worker`** | `python:3.11-slim` | N/A | N/A | Celery worker listening on queue `celery`. Executes `evaluate_interaction`, executes logic synchronously, dispatches Ollama calls, generates coaching tips, and computes blended scores. |

---

## 3. Data Ingestion & Sanitization Engine

### 3.1 Pydantic Request Models (`src/api/web_app.py`)
Incoming payloads are validated against the `EvaluateRequest` model:

```python
class Turn(BaseModel):
    speaker: str
    text: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_time_sec: Optional[int] = 0
    end_time_sec: Optional[int] = 0

class EvaluateRequest(BaseModel):
    transcript: Union[List[Turn], str]
    channel: Optional[str] = "Call"
    agent_name: Optional[str] = "Agent"
    custom_prompt: Optional[str] = None
```

### 3.2 Timestamp Normalization Algorithm (`src/services/response_time.py`)
Timestamps can be submitted in two interchangeable formats:
1. **String representation:** `"[MM:SS]"` or `"[HH:MM:SS]"` (e.g., `"[15:30]"`).
2. **Integer seconds:** Direct epoch or relative second offsets (e.g., `start_time_sec: 930`).

The `leading_time_seconds()` regex method dynamically converts string timestamps into integer seconds:
$$\text{Regex: } \verb|^[\[\(]\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*[\]\)]|$$

$$\text{Calculation: } \text{Total Seconds} = (\text{Hours} \times 3600) + (\text{Minutes} \times 60) + \text{Seconds}$$

### 3.3 Token-Saving Sanitization
The raw transcript payload is parsed into two distinct representations:
* **`parsed_times` (`List[Tuple[int, int]]`):** An array of integer second intervals `[(start, end), ...]` routed exclusively to the deterministic Python rule engine.
* **`clean_transcript` (`str`):** A sanitized, plain-text dialogue formatted as `"{Speaker}: {Text}\n..."`. Timestamps and JSON metadata are stripped. This reduces LLM token consumption by **35–50%** and completely prevents the model from hallucinating time calculations.

---

## 4. Deterministic Rule Engine (Timing & SLAs)

Deterministic rules are executed by pure Python logic in `src/services/rule_engine.py`. These metrics bypass the LLM entirely, guaranteeing zero hallucinations, instant evaluation, and deterministic accuracy.

### 4.1 Verbatim Branding Check (`evaluate_branding`)
Checks that the agent followed corporate scripting standards at call open and close:
* **Greeting Requirement:** Scans the concatenated string of the **first 4 agent utterances**:
  $$\text{Greeting Match} \iff \text{"thank you for calling s-net"} \in \text{first\_4}$$
* **Closing Requirement:** Scans the concatenated string of the **last 4 agent utterances**:
  $$\text{Closing Match} \iff \text{"thank you for choosing s-net"} \in \text{last\_4}$$
* **Scoring Logic:**
  * If both match $\to$ `PASS` (100 points, Reason: `"Standard compliant response"`).
  * If either fails $\to$ `FAIL` (0 points, Reason: `"Agent missed verbatim scripts for: [Greeting / Closing]"`).

### 4.2 Hold Time and Dead Air Check (`evaluate_hold_and_dead_air`)
Evaluates awkward silences and uncommunicated pauses between consecutive speaker turns.

#### Gap Calculation Formula:
For every adjacent pair of turns $i-1$ and $i$ where $i \in [1, N-1]$:
$$\text{gap}_i = \text{start\_time}_i - \text{end\_time}_{i-1}$$

#### Dead Air Breach Rules:
1. **Dead Air Threshold:** Any gap strictly greater than **20 seconds** is flagged as Dead Air:
   $$\text{is\_dead\_air} \iff \text{gap}_i > 20$$
2. **Exception Allowance:** Contact center operations allow up to **2 communicated holds** during long troubleshooting calls:
   $$\text{Allowed Exceptions} = 2$$
3. **Breach Condition:** If the total count of dead air intervals is **3 or greater**, the line item fails:
   $$\text{dead\_air\_count} \ge 3 \implies \text{FAIL (0 pts)}$$
   $$\text{dead\_air\_count} < 3 \implies \text{PASS (100 pts)}$$

---

## 5. LLM Evaluation Pipeline & Prompt Engineering

Complex behavioral metrics are evaluated by querying Llama 3.1 via the `OllamaAdapter` (`src/services/llm_adapter.py`).

### 5.1 The 15 Standard Evaluation Criteria

The system grades transcripts against 15 distinct line items organized into three categories:

#### Category 1: Soft Skills (Category Weight: 33.3% / 0.333)
1. **`Branding and Survey Check`** *(Evaluated by Rule Engine)*: Verbatim open and close script matching.
2. **`Hold time and Dead Air`** *(Evaluated by Rule Engine)*: Strict threshold check on silence intervals.
3. **`Personalized the call/ticket appropriately`** *(LLM)*:
   * *Strict Prompt Directive:* Rate PASS ONLY if the agent explicitly addressed the caller by their verified name (e.g., "John") at least once. Rate FAIL if the agent never used the caller's name.
4. **`Empathy & Acknowledgment Statement`** *(LLM)*:
   * *Prompt Directive:* Default to PASS. Rate FAIL ONLY if the agent is blunt or robotic instead of empathetically acknowledging customer frustration or urgency.
5. **`Build rapport and observed professionalism`** *(LLM)*:
   * *Prompt Directive:* Default to PASS. Rate FAIL ONLY if the agent is discourteous, disrespectful, interrupts, or makes unprofessional sounds.

#### Category 2: Technical Knowledge (Category Weight: 66.7% / 0.667)
6. **`Paraphrasing`** *(LLM)*:
   * *Prompt Directive:* Must paraphrase the customer's core technical issue at the onset of the call or upon statement of the request to reconfirm understanding.
7. **`Verified customer`** *(LLM)*:
   * *Strict Prompt Directive:* Rate PASS ONLY if the agent explicitly validated secure account details (e.g., an account PIN, full address, or security question). Asking for an account number alone triggers an automatic FAIL.
8. **`Probing`** *(LLM)*:
   * *Prompt Directive:* Default to PASS. Rate FAIL ONLY if the agent prescribes steps without asking logical, clarifying diagnostic questions to isolate the root cause.
9. **`Set proper expectations`** *(LLM)*:
   * *Prompt Directive:* Clearly communicate estimated resolution timeframes, hold durations, and next steps before initiating actions.
10. **`Provided the appropriate solution`** *(LLM)*:
    * *Strict Prompt Directive:* Rate PASS if the agent's actions eventually solved the core issue (confirmed by customer). ONLY rate FAIL if the agent gave completely incorrect instructions that left the issue broken.
11. **`Took ownership of the problem`** *(LLM)*:
    * *Prompt Directive:* Default to PASS. Rate FAIL ONLY if the agent deflects blame onto other departments (e.g., sales or external IT) instead of performing active troubleshooting.
12. **`Active listening`** *(LLM)*:
    * *Strict Prompt Directive:* Avoid asking the customer for information they already provided earlier in the call. Repeated requests for identical information (2+ times) triggers a FAIL.
13. **`Confirmed the issue is resolved`** *(LLM)*:
    * *Prompt Directive:* Gain explicit verbal confirmation that the issue is resolved, prompt the user to test the fix, and provide a wrap-up summary.

#### Category 3: Auto Fail Category (Category Weight: 0.0% / Circuit Breakers)
14. **`Escalation`** *(LLM)*:
    * *Strict Prompt Directive:* ONLY rate FAIL if the customer explicitly requested a supervisor/manager OR threatened to cancel AND the agent refused or failed to transfer them. Do NOT fail simply because the customer was upset or the call was lengthy.
15. **`Non-First Call Resolution`** *(LLM)*:
    * *Strict Prompt Directive:* Rate PASS if the customer's technical issue was resolved by the conclusion of the call. ONLY rate FAIL if the customer was hung up on, told to call back later, or left with an active outage.

### 5.2 Chunked 4-prompt System
To prevent context overflow and attention degradation across long transcripts (up to 30 minutes / ~4,000 words), we do not use a single strict CoT prompt anymore. `llm_adapter.py` breaks the transcript into a cached prefix and then queries the LLM in separate category chunks sequentially to avoid context fog. Each chunk loads the transcript alongside only its relevant category items, keeping inference focused and eliminating token cross-contamination.

### 5.3 Rating Parser Algorithm (`parse_dynamic_ratings`)
1. Strips any internal reasoning tokens (`<thinking>...</thinking>`).
2. Iterates over line output using end-of-line regex:
   $$\text{Regex: } \verb|\b(PASS|FAIL|PASSED|FAILED|YES|NO)\b\s*[^a-zA-Z0-9]*$|$$
3. Normalizes ratings (`PASSED` $\to$ `PASS`, `NO` $\to$ `FAIL`).
4. Maps string ratings to numerical values via lookup: `RATING_SCORES = {"PASS": 100, "FAIL": 0}`.

---

## 6. Dynamic Coaching Generation Subsystem

When an agent fails any LLM-evaluated criteria line item, the system automatically triggers a targeted coaching generation sub-routine.

### Execution Flow:
1. **Filter Failed Items:** Identifies all scorecard entries where $\text{rating} \in [\text{"FAIL"}, \text{"NO"}]$ (excluding both 'dead air' AND 'branding' failures because the Python Rule Engine automatically injects deterministic coaching text for them).
2. **Targeted Prompting:** Constructs an isolated, single-item coaching prompt:
   ```
   <TRANSCRIPT>
   {clean_transcript}
   </TRANSCRIPT>

   <INSTRUCTIONS>
   You are an expert QA Coach evaluating a {channel} interaction.
   The agent FAILED the following QA criteria: '{line_item_name}'

   Write a brief coaching tip (EXPLICITLY 1 to 2 sentences MAX) on how the agent can improve.
   CRITICAL: Output ONLY a valid JSON object.

   JSON FORMAT:
   {
     "coaching": "..."
   }
   </INSTRUCTIONS>
   ```
3. **Strict JSON Enforcement:** Queries Ollama with `format="json"` and `timeout=300`.
4. **Scorecard Augmentation:** Injects actionable feedback directly into the failed item:
   * `item["coaching"] = parsed_json["coaching"]`

---

## 7. Mathematical Scoring Engine & Circuit Breakers

The scoring engine executes a multi-stage mathematical aggregation with zero-tolerance circuit breaker overrides.

### 7.1 Category Score Calculation
For any category $C$ containing $K$ evaluated line items with individual scores $s_1, s_2, \dots, s_K \in \{0, 100\}$:
$$\text{Score}_C = \text{round}\left(\frac{\sum_{i=1}^{K} s_i}{K}, 1\right)$$

*Example (Soft Skills with 5 items, 1 Fail):*
$$\text{Score}_{\text{Soft Skills}} = \frac{100 + 100 + 100 + 100 + 0}{5} = \frac{400}{5} = 80.0\%$$

### 7.2 Blended Final Score Calculation
Given category scores $\text{Score}_C$ and normalized category weights $w_C$:

| Category | Configured Weight ($w_C$) | Percentage |
|---|---|---|
| **Soft Skills** | `0.333` | 33.3% |
| **Technical Knowledge** | `0.667` | 66.7% |
| **Auto Fail Category** | `0.000` | 0.0% |
| **Total Weight ($\sum w_C$)** | `1.000` | 100.0% |

$$\text{Final Score} = \text{round}\left( \sum_{C} \text{Score}_C \times \frac{w_C}{\sum w}, 1 \right)$$

$$\text{Final Score} = \text{round}\left( (\text{Score}_{\text{Soft Skills}} \times 0.333) + (\text{Score}_{\text{Tech Knowledge}} \times 0.667), 1 \right)$$

### 7.3 Zero-Tolerance Auto-Fail Circuit Breakers (`check_auto_fail`)
Before any score is published, the `check_auto_fail` function inspects the transcript and scorecard. An immediate Auto-Fail occurs if:

1. **Profanity Blacklist:** The transcript contains blacklisted abusive keywords:
   $$\verb|["fuck", "shut up", "idiot", "get lost", "stupid", "hang up"]|$$
2. **Hostile Utterances:** $\ge 3$ hostile agent lines detected.
3. **Scorecard Circuit Breaker:** Any line item belonging to the `"Auto Fail Category"` (e.g., **Escalation** or **Non-First Call Resolution**) is rated `FAIL` or `NO`.

#### Consequence of Auto-Fail:
* `is_auto_fail` is set to `true`.
* `auto_fail_reason` is set to the specific violation trigger.
* **All category scores and the final score are instantly overridden to `0.0`**:
  $$\text{Final Score} = 0.0$$
  $$\forall C, \quad \text{Score}_C = 0.0$$

---

## 8. Asynchronous Polling & State Persistence

Celery stores execution states and serialized scorecard payloads in Redis using key format `celery-task-meta-{job_id}`.

### State Transitions:
```
           POST /api/evaluate
                  │
                  ▼
              [PENDING]  ───► HTTP GET /api/status/{job_id} ──► { "status": "processing" }
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
    [SUCCESS]           [FAILURE]
        │                   │
        ▼                   ▼
  HTTP GET returns:   HTTP GET returns:
  {                   {
    "status":           "status": "failed",
    "completed",        "error": "..."
    "result": {...}   }
  }
```

---

## 9. Codebase Map & Module Reference

| Path | Primary Responsibilities |
|---|---|
| `docker-compose.yml` | Multi-container composition, network definitions, ports, volume bindings. |
| `Dockerfile.gateway` | Container recipe for FastAPI web service. |
| `Dockerfile.orchestrator`| Container recipe for primary Celery evaluation coordinator. |
| `src/api/web_app.py` | FastAPI application, endpoints (`/api/evaluate`, `/api/status`, `/api/preview-prompt`), Pydantic models. |
| `src/services/dynamic_evaluator.py` | Core evaluation orchestrator: sanitization, category looping, scoring aggregation, circuit breakers, dynamic coaching. |
| `src/services/rule_engine.py` | Pure Python deterministic algorithms for verbatim branding and mathematical Dead Air SLA checks. |
| `src/services/response_time.py` | Timestamp parser (`leading_time_seconds`) and delay interval calculators. |
| `src/services/llm_adapter.py` | HTTP adapter for local Ollama service (`/api/chat`), options, timeouts, JSON format parsing. |
| `src/services/qa_summary.py` | Semantic interaction summarizer enforcing length and failure context. |
| `src/services/orchestrator_worker.py` | Celery task entry point (`orchestrate_evaluation`). |
| `resources/prompts/` | Prompt templates for dynamic evaluation, coaching tips, and summaries. |
| `tests/payloads/` | Standardized 30-minute test datasets (`perfect_call_payload.json`, `mediocre_call_payload.json`, `catastrophic_call_payload.json`). |
