"""
llm_evaluator.py

Uses Google Gemini (gemini-2.0-flash, free tier) to re-rank the top-10 scored
candidates and generate plain-English explanations tailored to the user's profile.

Requires GEMINI_API_KEY in the environment or a .env file in the project root.
Get a free key at https://aistudio.google.com/app/apikey

Gracefully falls back to rule-based explanations if the key is missing.
"""

import os
import json
from pathlib import Path
from typing import List, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent))

from recommender import Song, UserProfile


def _load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())


def _format_candidates(candidates: List[Tuple[Song, float]]) -> str:
    lines = []
    for i, (song, score) in enumerate(candidates, 1):
        lines.append(
            f'{i}. "{song.title}" by {song.artist} '
            f"[genre={song.genre}, mood={song.mood}, "
            f"energy={song.energy}, valence={song.valence}, "
            f"danceability={song.danceability}, acousticness={song.acousticness}, "
            f"tempo={song.tempo_bpm}bpm] numeric_score={score:.2f}"
        )
    return "\n".join(lines)


def explanation_fallback(user: UserProfile, song: Song) -> str:
    """Rule-based explanation used when the LLM is unavailable."""
    reasons = []
    if song.genre == user.favorite_genre:
        reasons.append(f"matches your {song.genre} genre preference")
    if song.mood == user.favorite_mood:
        reasons.append(f"has the {song.mood} mood you're after")
    if abs(song.energy - user.target_energy) < 0.2:
        reasons.append("energy level is a close match")
    if abs(song.danceability - user.danceability) < 0.2:
        reasons.append("danceability fits your profile")
    if reasons:
        return "Recommended because it " + ", ".join(reasons) + "."
    return "Solid match across your numeric preferences."


def evaluate_and_rerank(
    user: UserProfile,
    candidates: List[Tuple[Song, float]],
    k: int = 5,
) -> List[Tuple[Song, str]]:
    """
    Re-ranks candidates with Gemini and returns (song, explanation) pairs.
    Falls back to rule-based explanations if the key is missing or the call fails.
    """
    _load_env()

    try:
        from google import genai
    except ImportError:
        return [(song, explanation_fallback(user, song)) for song, _ in candidates[:k]]

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return [(song, explanation_fallback(user, song)) for song, _ in candidates[:k]]

    client = genai.Client(api_key=api_key)

    profile_desc = (
        f"Genre: {user.favorite_genre}, Mood: {user.favorite_mood}, "
        f"Energy: {user.target_energy}, Likes acoustic: {user.likes_acoustic}, "
        f"Danceability: {user.danceability}, Tempo: {user.target_tempo} bpm"
    )

    prompt = f"""You are a music recommendation expert. A user has the following taste profile:
{profile_desc}

A numeric scoring algorithm pre-ranked these candidate songs:
{_format_candidates(candidates)}

Your task:
1. Re-rank these songs so the best fit for this user comes first. Consider genre energy conventions, how mood pairs with valence, and whether the tempo matches the described vibe — not just the numeric score.
2. Return ONLY a valid JSON array of exactly {k} objects, each with:
   - "rank": integer starting at 1
   - "title": exact song title as shown above
   - "explanation": 1-2 sentence plain-English reason this song fits the user

Output only the JSON array with no markdown fences, no explanation outside the JSON."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        raw = response.text.strip()

        # Strip markdown fences if Gemini adds them anyway
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        ranked = json.loads(raw)

        title_to_song = {song.title: song for song, _ in candidates}
        results: List[Tuple[Song, str]] = []

        for item in sorted(ranked, key=lambda x: x["rank"]):
            song = title_to_song.get(item["title"])
            if song:
                results.append((song, item["explanation"]))
            if len(results) >= k:
                break

        # Pad with fallback if Gemini returned fewer than k
        seen = {s.title for s, _ in results}
        for song, _ in candidates:
            if song.title not in seen and len(results) < k:
                results.append((song, explanation_fallback(user, song)))

        return results

    except Exception:
        return [(song, explanation_fallback(user, song)) for song, _ in candidates[:k]]
