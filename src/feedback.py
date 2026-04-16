"""
feedback.py

Collects thumbs-up / thumbs-down ratings per song and nudges the UserProfile
toward what the user actually liked.
"""

import json
from collections import Counter
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, str(Path(__file__).parent))

from recommender import Song, UserProfile

FEEDBACK_PATH = Path(__file__).parent.parent / "data" / "feedback.json"


class FeedbackStore:
    """Persists like/dislike ratings to data/feedback.json."""

    def __init__(self, path: Path = FEEDBACK_PATH):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return {"liked": [], "disliked": []}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def _song_entry(self, song: Song) -> dict:
        return {
            "title": song.title, "genre": song.genre, "mood": song.mood,
            "energy": song.energy, "danceability": song.danceability,
            "acousticness": song.acousticness, "tempo_bpm": song.tempo_bpm,
        }

    def like(self, song: Song) -> None:
        entry = self._song_entry(song)
        if entry not in self._data["liked"]:
            self._data["liked"].append(entry)
        self._save()

    def dislike(self, song: Song) -> None:
        entry = self._song_entry(song)
        if entry not in self._data["disliked"]:
            self._data["disliked"].append(entry)
        self._save()

    def liked_songs(self) -> List[dict]:
        return self._data["liked"]

    def disliked_songs(self) -> List[dict]:
        return self._data["disliked"]

    def clear(self) -> None:
        self._data = {"liked": [], "disliked": []}
        self._save()


def adapt_profile(user: UserProfile, store: FeedbackStore) -> UserProfile:
    """
    Nudge the user's numeric preferences toward liked songs and away from disliked ones.
    Uses a simple 15% weighted-average adjustment per cycle.
    """
    liked    = store.liked_songs()
    disliked = store.disliked_songs()

    if not liked and not disliked:
        return user

    def _avg(songs: List[dict], key: str):
        vals = [s[key] for s in songs if key in s]
        return sum(vals) / len(vals) if vals else None

    def _nudge(current: float, toward, away, strength: float = 0.15) -> float:
        result = current
        if toward is not None:
            result += (toward - result) * strength
        if away is not None:
            result -= (away - result) * strength * 0.5
        return round(max(0.0, min(1.0, result)), 3)

    new_energy = _nudge(
        user.target_energy,
        _avg(liked, "energy"),
        _avg(disliked, "energy"),
    )
    new_dance = _nudge(
        user.danceability,
        _avg(liked, "danceability"),
        _avg(disliked, "danceability"),
    )
    liked_acoustic = _avg(liked, "acousticness")
    new_acoustic = (liked_acoustic > 0.5) if liked_acoustic is not None else user.likes_acoustic

    # Genre: favour the most frequently liked genre
    top_genre = user.favorite_genre
    if liked:
        top_genre = Counter(s["genre"] for s in liked).most_common(1)[0][0]

    return UserProfile(
        favorite_genre=top_genre,
        favorite_mood=user.favorite_mood,
        target_energy=new_energy,
        likes_acoustic=new_acoustic,
        danceability=new_dance,
        target_tempo=user.target_tempo,
    )
