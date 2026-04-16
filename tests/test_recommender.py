import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recommender import Song, UserProfile, Recommender, recommend_songs, dict_to_profile

# ─── Shared fixtures ──────────────────────────────────────────────────────────

def _two_songs():
    return [
        Song(
            id=1, title="Test Pop Track", artist="Test Artist",
            genre="pop", mood="happy",
            energy=0.8, tempo_bpm=120, valence=0.9,
            danceability=0.8, acousticness=0.2,
        ),
        Song(
            id=2, title="Chill Lofi Loop", artist="Test Artist",
            genre="lofi", mood="chill",
            energy=0.4, tempo_bpm=80, valence=0.6,
            danceability=0.5, acousticness=0.9,
        ),
    ]


def make_small_recommender() -> Recommender:
    return Recommender(_two_songs())


def _pop_user() -> UserProfile:
    return UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )


# ─── Existing tests (unchanged) ───────────────────────────────────────────────

def test_recommend_returns_songs_sorted_by_score():
    user = _pop_user()
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = _pop_user()
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


# ─── RAG retriever tests ──────────────────────────────────────────────────────

def test_vector_store_returns_k_results():
    from rag_retriever import SongVectorStore, encode_profile

    songs = _two_songs()
    store = SongVectorStore()
    store.build(songs)

    user = _pop_user()
    query_vec  = encode_profile(user)
    candidates = store.search(query_vec, k=2)

    assert len(candidates) == 2
    assert all(isinstance(s, Song) for s in candidates)


def test_vector_store_top_result_matches_profile():
    from rag_retriever import SongVectorStore, encode_profile

    songs = _two_songs()
    store = SongVectorStore()
    store.build(songs)

    user = _pop_user()
    query_vec  = encode_profile(user)
    candidates = store.search(query_vec, k=2)

    # Pop song has high energy (0.8) matching user target_energy (0.8)
    # and low acousticness (0.2) matching likes_acoustic=False (0.0)
    # so it should rank first on numeric similarity
    assert candidates[0].genre == "pop"


def test_vector_store_save_load_roundtrip(tmp_path):
    from rag_retriever import SongVectorStore, encode_profile
    import numpy as np

    songs = _two_songs()
    store = SongVectorStore()
    store.build(songs)

    path = tmp_path / "store.json"
    store.save(path)

    loaded = SongVectorStore.load(path)
    assert len(loaded.songs) == len(songs)
    assert np.allclose(store._matrix, loaded._matrix)


def test_encode_profile_returns_unit_vector():
    from rag_retriever import encode_profile
    import numpy as np

    user = _pop_user()
    vec  = encode_profile(user)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-6


# ─── Feedback tests ───────────────────────────────────────────────────────────

def test_feedback_like_persists(tmp_path):
    from feedback import FeedbackStore

    store = FeedbackStore(path=tmp_path / "feedback.json")
    song  = _two_songs()[0]

    store.like(song)
    assert len(store.liked_songs()) == 1
    assert store.liked_songs()[0]["title"] == song.title


def test_feedback_adapt_profile_nudges_energy(tmp_path):
    from feedback import FeedbackStore, adapt_profile

    store = FeedbackStore(path=tmp_path / "feedback.json")
    high_energy_song = _two_songs()[0]  # energy=0.8
    store.like(high_energy_song)

    base = UserProfile(
        favorite_genre="lofi", favorite_mood="chill",
        target_energy=0.4, likes_acoustic=True,
    )
    adapted = adapt_profile(base, store)

    # Energy should have nudged upward toward 0.8
    assert adapted.target_energy > base.target_energy


def test_feedback_no_ratings_returns_same_profile(tmp_path):
    from feedback import FeedbackStore, adapt_profile

    store = FeedbackStore(path=tmp_path / "feedback.json")
    user  = _pop_user()
    adapted = adapt_profile(user, store)

    assert adapted.target_energy  == user.target_energy
    assert adapted.favorite_genre == user.favorite_genre


# ─── LLM evaluator fallback test (no API key needed) ─────────────────────────

def test_llm_evaluator_fallback_returns_k_results():
    from llm_evaluator import evaluate_and_rerank

    songs = _two_songs()
    # Pass scored candidates without an API key — should fall back gracefully
    candidates = [(songs[0], 7.5), (songs[1], 4.2)]

    import os
    os.environ.pop("GEMINI_API_KEY", None)   # ensure no key

    results = evaluate_and_rerank(_pop_user(), candidates, k=2)

    assert len(results) == 2
    assert all(isinstance(s, Song) for s, _ in results)
    assert all(isinstance(e, str) and e.strip() for _, e in results)
