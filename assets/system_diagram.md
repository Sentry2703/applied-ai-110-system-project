# RAG-Enhanced Music Recommendation System — Architecture Diagram

## Overview

This diagram shows how a RAG retrieval layer and a specialized LLM evaluator extend the
existing content-based filtering engine (`src/recommender.py`) to operate over a
100-song catalog instead of the original 25-song CSV.

---

## System Diagram

```mermaid
flowchart TD
    %% ─────────────────────────────────────────
    %% INPUT
    %% ─────────────────────────────────────────
    A([User Input\ngenre · mood · energy\ndanceability · tempo · acoustic])
    A --> B[Profile Builder\n──────────────\nUserProfile dataclass\nsrc/recommender.py]

    %% ─────────────────────────────────────────
    %% RAG RETRIEVAL LAYER  ← NEW
    %% ─────────────────────────────────────────
    B --> C[Query Encoder\n──────────────\nEmbed user profile\ninto feature vector]
    C --> D[(Song Vector Store\n──────────────\n~100 songs\npre-embedded features\ndata/songs.csv + expansions)]
    D --> E[RAG Retriever\n──────────────\nCosine similarity search\nreturns top-20 candidates]

    %% ─────────────────────────────────────────
    %% EXISTING SCORING LAYER  ← EXISTING
    %% ─────────────────────────────────────────
    E --> F[Weighted Scorer\n──────────────\nrecommender.py\nscore_song\(\)\ngenre ×3 · mood ×2\nenergy ×1.5 · acoustic ×1\ndance ×0.5 · tempo ×0.25]
    F --> G[Ranked Candidates\n──────────────\nscored 0.0 – 8.25\ntop-10 pass through]

    %% ─────────────────────────────────────────
    %% LLM EVALUATOR  ← NEW
    %% ─────────────────────────────────────────
    G --> H[LLM Evaluator\n──────────────\nSpecialized model\nclaude-sonnet-4-6\nre-ranks by nuance:\nlyrics · era · vibe fit\nexplain_recommendation\(\)]
    H --> I[Final Recommendations\n──────────────\nTop-5 songs\n+ plain-English explanations]

    %% ─────────────────────────────────────────
    %% OUTPUT LAYER  ← EXISTING + NEW
    %% ─────────────────────────────────────────
    I --> J{Output Channel}
    J -- "CLI" --> K[Terminal Output\n──────────────\nsrc/main.py\n4 test profiles]
    J -- "UI" --> L[Streamlit Dashboard\n──────────────\nInteractive profile builder\nvisual score breakdown]

    %% ─────────────────────────────────────────
    %% HUMAN-IN-THE-LOOP
    %% ─────────────────────────────────────────
    K --> M{Human Review}
    L --> M
    M -- "Rate / skip songs" --> N[Feedback Collector\n──────────────\nCaptures thumbs-up/down\nper recommendation]
    N --> O[Profile Adapter\n──────────────\nAdjusts UserProfile weights\nbased on feedback history]
    O --> B

    %% ─────────────────────────────────────────
    %% TESTING LAYER  ← EXISTING + NEW
    %% ─────────────────────────────────────────
    M -- "Automated checks" --> P[Test Suite\n──────────────\ntests/test_recommender.py\npytest]
    P --> Q{Pass / Fail?}
    Q -- "FAIL → inspect" --> R[Debug & Tune\n──────────────\nAdjust scorer weights\nRevise LLM prompt\nExpand catalog]
    R --> F
    Q -- "PASS" --> S([Approved Output\nReady for production])

    %% ─────────────────────────────────────────
    %% STYLES
    %% ─────────────────────────────────────────
    style A fill:#4A90D9,color:#fff,stroke:#2c5f8a
    style D fill:#7B5EA7,color:#fff,stroke:#4a3666
    style E fill:#7B5EA7,color:#fff,stroke:#4a3666
    style C fill:#7B5EA7,color:#fff,stroke:#4a3666
    style F fill:#2E8B57,color:#fff,stroke:#1a5e38
    style G fill:#2E8B57,color:#fff,stroke:#1a5e38
    style H fill:#D4873A,color:#fff,stroke:#9a5f26
    style I fill:#D4873A,color:#fff,stroke:#9a5f26
    style M fill:#E84545,color:#fff,stroke:#a82d2d
    style P fill:#E84545,color:#fff,stroke:#a82d2d
    style Q fill:#E84545,color:#fff,stroke:#a82d2d
    style S fill:#2E8B57,color:#fff,stroke:#1a5e38
```

---

## Component Glossary

| Color | Layer | Components |
|---|---|---|
| Blue | **Input** | User Input, Profile Builder |
| Purple | **RAG Retrieval** *(new)* | Query Encoder, Song Vector Store, RAG Retriever |
| Green | **Scoring** *(existing)* | Weighted Scorer, Ranked Candidates |
| Orange | **LLM Evaluation** *(new)* | LLM Evaluator, Final Recommendations |
| Red | **Human / QA** | Human Review, Test Suite, Pass/Fail gate |

---

## Data Flow — Step by Step

```
1. INPUT
   User fills in: genre="lofi", mood="chill", energy=0.4, acoustic=True, tempo=78

2. PROFILE BUILDER  [existing: src/recommender.py → UserProfile]
   Converts raw input into a structured UserProfile dataclass.

3. QUERY ENCODER  [new]
   Converts the UserProfile into a numeric feature vector for similarity search.

4. RAG RETRIEVER  [new]
   Runs cosine-similarity search over ~100 pre-embedded songs.
   Returns top-20 candidate songs — far faster than scoring all 100.

5. WEIGHTED SCORER  [existing: recommender.py → score_song()]
   Applies the 6-feature weighted formula to all 20 candidates.
   Produces a numeric score (0.0–8.25) per song.

6. LLM EVALUATOR  [new: claude-sonnet-4-6]
   Receives the top-10 scored candidates + user profile as context.
   Re-ranks by nuanced fit (era, lyrical mood, vibe beyond numeric features).
   Calls explain_recommendation() to produce a plain-English rationale.

7. OUTPUT
   CLI  → main.py prints top-5 + explanations (existing behavior preserved).
   UI   → Streamlit dashboard shows visual breakdown (planned; listed in requirements.txt).

8. HUMAN REVIEW
   User rates recommendations (thumbs up/down).
   Feedback is fed back to the Profile Adapter, which tunes UserProfile weights.

9. TEST SUITE  [existing: tests/test_recommender.py]
   pytest runs on every change.
   Checks: sorted scores, non-empty explanations, no regressions.
   Failed tests block the pipeline and surface the component to debug.
```

---

## Integration Map — What Changes vs. What Stays

| File / Component | Status | Change |
|---|---|---|
| `src/recommender.py` | **Keep as-is** | Score logic untouched; called by RAG pipeline |
| `src/main.py` | **Extend** | Add CLI flag `--rag` to route through new pipeline |
| `data/songs.csv` | **Expand** | Grow from 25 → 100 songs; add embedding column |
| `tests/test_recommender.py` | **Keep + add** | Existing tests stay; add RAG retrieval tests |
| `src/rag_retriever.py` | **New** | Encodes songs, builds vector store, runs retrieval |
| `src/llm_evaluator.py` | **New** | Claude API call for nuanced re-ranking |
| `src/feedback.py` | **New** | Collects ratings and updates UserProfile weights |
| `streamlit_app.py` | **New** | Visual dashboard (requirements.txt already lists streamlit) |
