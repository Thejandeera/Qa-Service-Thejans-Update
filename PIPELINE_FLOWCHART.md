```mermaid
flowchart TD
    A[Start QA Evaluation] --> B[Phase 1: Deterministic Engine\n(Python Rules)]
    
    subgraph Phase 1
        B --> B1[Hold Time & Dead Air Check]
        B --> B2[Branding & Intro/Outro Check]
        B --> B3[Empathy & Acknowledgment\n3-Tier Scan]
        B --> B4[Verified Customer\nScan first 4 mins for PIN/Address]
    end
    
    B1 --> C[Phase 2: Vector Context Engine\n(Embeddings)]
    B2 --> C
    B3 --> C
    B4 --> C
    
    subgraph Phase 2
        C --> C1[LLM extracts Ground Truth Problem\nfrom Full Transcript]
        C --> C2[LLM extracts Agent Understood Problem\nfrom Agent-Only Transcript]
        C1 --> C3{Cosine Similarity >= 0.52?}
        C2 --> C3
        C3 -->|Yes| C4[Paraphrasing = PASS]
        C3 -->|No| C5[Paraphrasing = FAIL]
    end
    
    C4 --> D[Phase 3: Cascading LLM Pipeline\n(Micro-Batches)]
    C5 --> D
    
    subgraph Phase 3
        D --> D1{Paraphrasing Passed?}
        
        D1 -->|Yes| D2[Auto-PASS Probing\nSave LLM Tokens]
        D1 -->|No| D3[LLM Prompt 2A: Probing Check]
        
        D2 --> D4[LLM Prompt 2B: Set Proper Expectations]
        D3 --> D4
        
        D4 --> D5[LLM Prompt 3: Solution Alignment\nCompares Actions to Ground Truth Problem]
        
        D5 --> D6[LLM Prompt 4: Vibe Check\nActive Listening & Ownership on Full Transcript]
    end
    
    D6 --> E[Phase 4: Mathematical Scoring Engine]
    
    subgraph Phase 4
        E --> E1[Apply Deductions\nLower weights for Ownership/Listening]
        E1 --> E2{Check Auto-Fail Rules\ne.g., Profanity, Unresolved Escalation}
        E2 -->|Triggered| E3[Final Score = 0]
        E2 -->|Safe| E4[Calculate Blended Category Scores]
        E4 --> E5[Final JSON Payload Generation]
    end
    
    E3 --> F[End Evaluation]
    E5 --> F
```
