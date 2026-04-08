# Evaluation Pipeline — LLM-as-judge

**Type:** Flow (Mermaid `flowchart LR`)
**Purpose:** Show how the offline evaluation pipeline runs the Triage Agent against the golden dataset, scores it with the LLM-judge, logs the run as a Langfuse Dataset Experiment, and gates the CI build.

```mermaid
flowchart LR
    GD[("golden_dataset.jsonl<br/>curated cases<br/>+ adversarial")]:::data
    RUN["eval_runner.py<br/>(per-case loop)"]:::runner
    AG["Triage Agent<br/>(via ILLMProvider only)"]:::agent
    PR{{"PROMPT_REGISTRY<br/>versioned prompts<br/>(ARC-015)"}}:::registry
    JUDGE["TriageJudge<br/>LLM-as-judge"]:::judge
    SCORE["EvalScore per case<br/>severity / root_cause / components / overall"]:::score
    AGG["Aggregate<br/>avg_overall_score<br/>adversarial_recall"]:::score
    LF[("Langfuse<br/>Dataset Experiment<br/>(one run per CI build)")]:::store
    GATE{{"CI gate<br/>avg >= 0.70<br/>AND<br/>adversarial_recall == 1.0"}}:::gate
    PASS([PR mergeable]):::pass
    FAIL([PR blocked<br/>exit code != 0]):::fail

    GD --> RUN
    RUN --> AG
    PR --> AG
    AG --> JUDGE
    GD -- expected --> JUDGE
    JUDGE --> SCORE
    SCORE --> AGG
    SCORE --> LF
    AGG --> LF
    AGG --> GATE
    GATE -- yes --> PASS
    GATE -- no --> FAIL

    classDef data fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e;
    classDef runner fill:#fef9c3,stroke:#854d0e,color:#713f12;
    classDef agent fill:#dcfce7,stroke:#166534,color:#14532d;
    classDef registry fill:#ede9fe,stroke:#5b21b6,color:#4c1d95;
    classDef judge fill:#ffe4e6,stroke:#9f1239,color:#881337;
    classDef score fill:#fce7f3,stroke:#9d174d,color:#831843;
    classDef store fill:#f1f5f9,stroke:#334155,color:#0f172a;
    classDef gate fill:#fde68a,stroke:#a16207,color:#713f12;
    classDef pass fill:#bbf7d0,stroke:#166534,color:#14532d;
    classDef fail fill:#fecaca,stroke:#b91c1c,color:#7f1d1d;
```

## Legend

- **golden_dataset.jsonl** — Curated cases (normal + adversarial). Schema in `ARCHITECTURE.md` §4.5.
- **eval_runner.py** — Iterates the dataset, invokes the Triage Agent **only through `ILLMProvider`** (no shortcuts that bypass the agent under test).
- **PROMPT_REGISTRY (ARC-015)** — All prompts the agent uses are resolved here; the runner asserts no inline prompts leak through.
- **TriageJudge** — LLM-as-judge that compares the agent output against the expected fields and emits an `EvalScore`.
- **EvalScore** — Per-case score; aggregated across the dataset.
- **Langfuse Dataset Experiment** — Each CI build is a new run; trends over time live here.
- **CI gate (ARC-016)** — Hard gate. Fails the build if either threshold is breached.

See `ARCHITECTURE.md` §4.5 for the contract and §5 rules ARC-015 / ARC-016.
