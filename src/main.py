"""
Command line runner for the Music Recommender Simulation.

Usage:
    python src/main.py                 # basic weighted scoring
    python src/main.py --rag           # RAG + LLM pipeline
    python src/main.py --rag --profile "Late Night Coder"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from recommender import load_songs, recommend_songs, dict_to_profile, dicts_to_songs

PROFILES = {
    "Late Night Coder": {
        "genre": "lofi", "mood": "chill", "energy": 0.4,
        "likes_acoustic": True, "danceability": 0.6, "tempo_bpm": 78,
    },
    "Gym Session": {
        "genre": "edm", "mood": "euphoric", "energy": 0.95,
        "likes_acoustic": False, "danceability": 0.92, "tempo_bpm": 140,
    },
    "Sunday Morning": {
        "genre": "r&b", "mood": "romantic", "energy": 0.55,
        "likes_acoustic": False, "danceability": 0.75, "tempo_bpm": 90,
    },
    "Contradictory": {
        "genre": "metal", "mood": "peaceful", "energy": 0.1,
        "likes_acoustic": True, "danceability": 0.2, "tempo_bpm": 62,
    },
}

CSV_PATH = Path(__file__).parent.parent / "data" / "songs.csv"


def run_basic(profile_name: str, profile: dict, songs, k: int = 5) -> None:
    user = dict_to_profile(profile)
    print(f"\n{'='*55}")
    print(f"Profile : {profile_name}  [basic mode]")
    print(f"  Genre: {user.favorite_genre} | Mood: {user.favorite_mood}")
    print(f"  Energy: {user.target_energy} | Acoustic: {user.likes_acoustic} | Dance: {user.danceability} | Tempo: {user.target_tempo}")
    print(f"{'='*55}")
    results = recommend_songs(user, songs, k=k)
    for song, score, explanation in results:
        print(f"  {song.title} ({song.genre}/{song.mood}) — Score: {score:.2f}")
        print(f"    {explanation}\n")


def run_rag(profile_name: str, profile: dict, songs, k: int = 5) -> None:
    from rag_retriever import SongVectorStore, encode_profile
    from llm_evaluator import evaluate_and_rerank

    user = dict_to_profile(profile)
    print(f"\n{'='*55}")
    print(f"Profile : {profile_name}  [RAG + AI mode]")
    print(f"  Genre: {user.favorite_genre} | Mood: {user.favorite_mood}")
    print(f"{'='*55}")

    # Step 1 — RAG retrieval
    store = SongVectorStore()
    store.build(songs)
    query_vec  = encode_profile(user)
    candidates = store.search(query_vec, k=20)
    print(f"  RAG retrieved {len(candidates)} candidates")

    # Step 2 — Weighted scoring
    scored = recommend_songs(user, candidates, k=10)
    print(f"  Weighted scorer produced {len(scored)} ranked results")

    # Step 3 — LLM re-ranking
    llm_input = [(song, score) for song, score, _ in scored]
    reranked  = evaluate_and_rerank(user, llm_input, k=k)

    for i, (song, explanation) in enumerate(reranked, 1):
        print(f"  {i}. {song.title} ({song.genre}/{song.mood})")
        print(f"     {explanation}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Music Recommender CLI")
    parser.add_argument("--rag",     action="store_true", help="Use RAG + LLM pipeline")
    parser.add_argument("--profile", type=str, default=None,
                        help=f"Run a single profile. Choices: {list(PROFILES.keys())}")
    parser.add_argument("--k",       type=int, default=5, help="Number of recommendations")
    args = parser.parse_args()

    song_dicts = load_songs(str(CSV_PATH))
    songs = dicts_to_songs(song_dicts)

    profiles_to_run = (
        {args.profile: PROFILES[args.profile]}
        if args.profile and args.profile in PROFILES
        else PROFILES
    )

    for name, prefs in profiles_to_run.items():
        if args.rag:
            run_rag(name, prefs, songs, k=args.k)
        else:
            run_basic(name, prefs, songs, k=args.k)


if __name__ == "__main__":
    main()
