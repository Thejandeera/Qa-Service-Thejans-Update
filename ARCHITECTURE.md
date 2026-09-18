# System Architecture & Technical Specifications

This document provides a comprehensive, exhaustive technical specification of the **Gemma QA Analysis System**. It details the end-to-end execution lifecycle, decoupled microservices topology, deterministic timing algorithms, LLM prompting strategies, and mathematical scoring formulas down to the exact decimal.

## Master Blueprint Cascade Pipeline
This system evaluates call center transcripts using a highly optimized, hybrid architectural approach designed to maximize the reliability of the local Llama 3.1 (8B) model while minimizing hallucinations. 

The evaluation process flows through 4 distinct phases:

### Phase 1: Deterministic Python Rule Engine (Zero-Latency)
Instead of relying on the LLM to count words or timestamps, strict technical rules are evaluated via pure Python logic in `src/services/rule_engine.py`:
- **Hold Time & Dead Air**: Scans timestamps for periods of silence >30s.
- **Branding & Intro/Outro**: Checks the first/last few turns for mandatory scripts (e.g., "Thank you for calling").
- **Empathy & Acknowledgment (3-Tier)**: Calculates word counts of empathy phrases versus customer frustration.
- **Verified Customer**: Scans the first 4 minutes (240s) for verification keywords. *(NOTE: Currently hardcoded to PIN/Address/Security Question. MUST be moved to a tenant-configurable DB table in the future).*

### Phase 2: Vector Context Engine (Embeddings)
To avoid the LLM failing on complex paraphrasing checks, we use Ollama Embeddings:
1. Extract the "Ground Truth Problem" from the Full Transcript.
2. Extract the "Agent Understood Problem" from an Agent-Only Transcript.
3. Calculate Cosine Similarity. A score >= 0.52 triggers an automatic PASS for Paraphrasing.

### Phase 3: Cascading LLM Pipeline (Micro-Batches)
The LLM evaluates the remaining subjective criteria using micro-batches (max 3 items) and targeted contexts:
- **Batch 1 (Soft Skills)**: Uses an *Agent-Only Transcript* to prevent the LLM from being confused by hostile customer dialogue.
- **Batch 2 (Probing/Expectations)**: If Paraphrasing passed in Phase 2, Probing is automatically passed without wasting LLM tokens. The Ground Truth Problem is injected into the context.
- **Batch 3 (Solution)**: The Ground Truth Problem is injected into the context to ensure the agent solved the actual issue.
- **Batch 4 (Vibe Check)**: Ownership and Active Listening are evaluated on the full transcript, with specifically down-weighted deduction values (5 pts) to protect against hallucination.

### Phase 4: Mathematical Scoring Engine
The pipeline intercepts the LLM's raw output, filters out items handled by the Rule Engine, dynamically requests 1-2 sentence coaching tips for failed items, checks Auto-Fail triggers, and calculates the blended weighted score.

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

The evaluation pipeline is built as a non-blocking, asynchronous pipeline. Below is the sequential execution flow from ingress to final scorecard retrieval, strictly designed to minimize LLM token usage and KV cache flushes via 6 hyper-optimized phases:

```
[Client / Postman]
       |
       |  1. HTTP POST /api/evaluate (JSON Payload with RoBERTa Scores)
       v
[API Gateway (FastAPI)] -> [Redis Queue] -> [Orchestrator Worker]
       |
       |  Phase 1: Deterministic Engine & Searchlights (Zero LLM)
       |  - Python evaluates Branding, Dead Air, Personalized Call, Verified Customer
       |  - Empathy Searchlight: Extract <Empathy Snippet> if RoBERTa flags Negative
       |  - Active Listening Searchlight: Extract <Repeated Snippet> via TF-IDF
       |
       v
       |  Phase 2: Vector Paraphrasing & Context
       |  - Extract First 10 Turns for Agent/Customer -> Embed & Cosine Sim
       |  - Save First 10 Customer Turns as <CUSTOMER_PROBLEM_CONTEXT>
       |
       v
       |  Phase 3: Micro-Snippet LLM Verifications (Sub-second LLM calls)
       |  - Verify Empathy on 3-turn snippet (Output exactly 1 word)
       |  - Verify Active Listening on 2-turn snippet (Output exactly 1 word)
       |
       v
       |  Phase 4: Agent-Only LLM Batch
       |  - Context: Agent-Only Transcript + <CUSTOMER_PROBLEM_CONTEXT>
       |  - Evaluate: Rapport, Probing, Ownership
       |
       v
       |  Phase 5: Wrap-Up LLM Batch
       |  - Context: ONLY Last 30% of Transcript
       |  - Evaluate: Confirmed Issue is Resolved
       |
       v
       |  Phase 6: Full-Context LLM Batch
       |  - Context: Full 100% Transcript
       |  - Evaluate: Escalation, Hostility (Auto-Fails)
       |
       v
       |  Phase 7: Batched Coaching Loop
       |  - Gather all FAILs from Phases 1-6 -> Request single JSON dictionary of tips
       |
       v
[Redis Result Backend] -> [Client Polling GET /api/status]
```

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

Complex behavioral metrics are evaluated by querying Llama 3.1 via the `OllamaAdapter`.
To prevent token explosion and 9-minute generation times, the prompts aggressively mandate that all internal reasoning (`<thinking>`) must be restricted to a MAXIMUM of 2 sentences per item.

### 5.1 The Standard Evaluation Criteria

The system grades transcripts against distinct line items organized into three categories:

#### Category 1: Soft Skills (Category Weight: 33.3% / 0.333)
1. **`Branding and Survey Check`** *(Evaluated by Rule Engine)*: Verbatim open and close script matching.
2. **`Hold time and Dead Air`** *(Evaluated by Rule Engine)*: Strict threshold check on silence intervals.
3. **`Personalized the call/ticket appropriately`** *(Evaluated by Rule Engine)*: Checks if the verified `customer_name` appears in the Agent's transcript.
4. **`Empathy & Acknowledgment Statement`** *(Hybrid: RoBERTa + Snippet LLM)*: 
   * Python tracks RoBERTa sentiment trajectories turn-by-turn. If any turn drops by 6.0 points or more compared to the previous turn (indicating sudden friction), an isolated 3-turn snippet is immediately extracted and sent to the LLM to verify if the agent was rude or empathetic.
5. **`Build rapport and observed professionalism`** *(Agent-Only LLM)*:
   * Checked against the Agent's dialogue only to avoid confusion from hostile customer phrasing.

#### Category 2: Technical Knowledge (Category Weight: 66.7% / 0.667)
6. **`Paraphrasing`** *(Evaluated by Vector Embeddings)*:
   * Compares the first 10 Customer turns against the first 10 Agent turns using cosine similarity (threshold 0.30).
7. **`Verified customer`** *(Evaluated by Rule Engine)*:
   * Regex verification checking for explicit word boundaries (`\b(pin|address)\b`) in the first 4 minutes.
8. **`Probing`** *(Agent-Only LLM)*:
   * Injected with `<CUSTOMER_PROBLEM_CONTEXT>` to verify the agent asked clarifying questions specific to the core issue.
9. **`Took ownership of the problem`** *(Agent-Only LLM)*:
   * Checks if the agent actively troubleshot the `<CUSTOMER_PROBLEM_CONTEXT>` instead of blindly transferring.
10. **`Active listening`** *(Hybrid: Python + Snippet LLM)*:
    * Python searches for repeated agent questions using a strict hybrid check: difflib (ratio > 0.60) AND Vector Embeddings (Cosine Similarity > 0.70). If both pass, a 2-turn snippet is sent to the LLM to verify.
11. **`Confirmed the issue is resolved`** *(Sliced LLM)*:
    * Evaluated *exclusively* on the last 30% of the transcript context to save tokens and prevent mid-call hallucination.

#### Category 3: Auto Fail Category (Circuit Breakers)
12. **`Escalation`** *(Full-Context LLM)*: Evaluates if the customer asked for a manager and the agent refused.
13. **`Hostility`** *(Full-Context LLM)*: Evaluates extreme hostility from the agent.

*(Note: `Set Proper Expectations`, `Provided the Appropriate Solution`, and `Non-First Call Resolution` have been permanently deleted from the architecture).*

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
U p d a t i n g   A R C H I T E C T U R E . m d 
 
 -   V e r i f i e d   C u s t o m e r   i s   h a r d c o d e d   t o   P I N / A d d r e s s .   M U S T   m o v e   t o   t e n a n t   D B . 
 
 
