# RAG-Enhanced Music Recommender

## TITLE & SUMMARY

**Music Recommender Simulation — RAG + AI Edition**

A content-based music recommendation system that combines a RAG retrieval layer, a weighted scoring engine, and a Claude LLM evaluator to surface the best-fit songs for a user's taste profile. Built on top of the original weighted-scoring prototype, extended with a full Streamlit UI, feedback loop, and CLI pipeline.

---

## ARCHITECTURE OVERVIEW

```
User Input (genre, mood, energy, tempo, danceability, acoustic)
        ↓
  Profile Builder  [src/recommender.py → UserProfile]
        ↓
  Query Encoder  [src/rag_retriever.py → encode_profile()]
        ↓
  RAG Retriever  [src/rag_retriever.py → SongVectorStore.search()]
  ~100-song vector store  →  top-20 candidates
        ↓
  Weighted Scorer  [src/recommender.py → recommend_songs()]
  genre ×3 · mood ×2 · energy ×1.5 · acoustic ×1 · dance ×0.5 · tempo ×0.25
        ↓
  LLM Evaluator  [src/llm_evaluator.py → claude-sonnet-4-6]
  re-ranks top-10 by nuanced vibe fit  →  top-5 with explanations
        ↓
  Output: CLI (src/main.py) or Streamlit UI (streamlit_app.py)
        ↓
  Human Review: thumbs up / down  →  Feedback Adapter  →  updated profile
```

See [assets/system_diagram.md](assets/system_diagram.md) for the full Mermaid diagram.

---

## SETUP INSTRUCTIONS

### 1. Prerequisites

- Python 3.12+
- A terminal open at the project root

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` includes: `pandas`, `pytest`, `streamlit`, `requests`, `numpy`, `anthropic`

### 3. Environment variables

Create a `.env` file in the project root (never commit this):

```
# Required for LLM re-ranking (RAG + AI mode)
GEMINI_API_KEY=your_key_here

# Optional — only needed if using fetch_lastfm_songs.py
LASTFM_API_KEY=your_key_here
```

Get a free Gemini API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — no credit card required.

> Without `GEMINI_API_KEY`, the system still works — RAG + AI mode falls back to rule-based explanations automatically.

### 4. (Optional) Expand the song catalog to ~100 songs

The default catalog has 25 songs. To add real songs from Last.fm:

```bash
# Get a free API key at https://www.last.fm/api/account/create
# Add LASTFM_API_KEY to your .env, then:
python scripts/fetch_lastfm_songs.py --count 75
```

Or generate synthetic songs instantly (no API key needed):

```bash
python scripts/generate_songs.py --count 75
```

Both scripts append to `data/songs.csv`.

---

## SAMPLE INTERACTIONS

### Streamlit UI

```bash
streamlit run streamlit_app.py
```

- Select genre, mood, energy, danceability, tempo, and acoustic preference in the sidebar
- Choose **Basic** mode (weighted scorer only) or **RAG + AI** mode (full pipeline)
- Click **Get Recommendations** to see top-5 results with scores and explanations
- Hit 👍 / 👎 on any song, then **Apply feedback & refresh** to nudge your profile

### CLI — basic mode

```bash
python src/main.py
```

Runs all 4 test profiles (Late Night Coder, Gym Session, Sunday Morning, Contradictory).

```bash
python src/main.py --profile "Late Night Coder" --k 3
```

### CLI — RAG + AI mode

```bash
python src/main.py --rag
python src/main.py --rag --profile "Gym Session"
```

---

## DESIGN DECISIONS

**Why numpy cosine similarity instead of a vector DB?**
At 100 songs, a matrix multiply over a 100×5 matrix takes microseconds. A full vector DB (Chroma, Pinecone) would add setup complexity for no measurable gain. The `SongVectorStore` can be swapped for a real DB later by replacing `search()`.

**Why 5 numeric features for RAG, not genre/mood?**
Genre and mood are categorical — cosine similarity on one-hot vectors would dominate the distance metric. The existing weighted scorer already handles them with high weights (×3, ×2). RAG handles the continuous features; the scorer handles the categorical gates.

**Why does the LLM receive only the top-10, not all 100?**
Fewer tokens = faster response and lower cost. The weighted scorer already filters strongly off-profile songs; the LLM's job is nuanced re-ranking within the plausible set, not discovery.

**Why does the feedback loop adjust energy and danceability but not genre?**
Genre is updated to the most-liked genre, but energy and danceability are nudged gradually (15% per cycle) to avoid overcorrecting from a single session.

---

## TESTING SUMMARY

Run the test suite:

```bash
python -m pytest tests/ -v
```

**10 tests across 4 groups:**

| Group | Tests |
|---|---|
| Core recommender | sorted scores, non-empty explanations |
| RAG retriever | k results returned, correct top result, save/load roundtrip, unit vector encoding |
| Feedback | like persists, energy nudge, no-rating passthrough |
| LLM evaluator | graceful fallback without API key |

All 10 pass with no API key required.

---

## REFLECTION

The biggest challenge was connecting the RAG layer to the existing weighted scorer without changing `recommender.py`. The solution — treating RAG as a pre-filter that passes a `List[Song]` into the unchanged `recommend_songs()` — kept the original logic intact and made both modes (basic and RAG+AI) use the same scoring function.

The LLM evaluator adds the most value for edge cases: contradictory profiles (metal + peaceful) where numeric scores cluster tightly and a human-sounding explanation matters more than a 0.1-point score difference. It falls back gracefully, so the system is always usable regardless of API availability.
