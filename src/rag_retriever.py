"""
rag_retriever.py

RAG retrieval layer: encodes songs and user profiles as numeric feature vectors,
then finds the top-N most similar songs using cosine similarity.

Narrows the candidate pool (100 songs → top-20) before the weighted scorer runs.
No external vector DB needed at this scale — pure numpy.
"""

import json
import numpy as np
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, str(Path(__file__).parent))

from recommender import Song, UserProfile, normalizeTempo


def encode_song(song: Song) -> np.ndarray:
    """5-dimensional numeric feature vector for a song, unit-normalised."""
    vec = np.array([
        song.energy,
        song.valence,
        song.danceability,
        song.acousticness,
        normalizeTempo(song.tempo_bpm),
    ], dtype=float)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def encode_profile(user: UserProfile) -> np.ndarray:
    """Map a UserProfile onto the same 5-d feature space."""
    acoustic_val = 1.0 if user.likes_acoustic else 0.0
    vec = np.array([
        user.target_energy,
        0.6,               # neutral default — UserProfile has no valence field
        user.danceability,
        acoustic_val,
        normalizeTempo(user.target_tempo),
    ], dtype=float)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


class SongVectorStore:
    """
    Lightweight in-memory vector store for ~100 songs.
    Cosine similarity over pre-normalised vectors via a single matrix multiply.
    """

    def __init__(self):
        self.songs: List[Song] = []
        self._matrix: np.ndarray | None = None   # shape (N, 5)

    def build(self, songs: List[Song]) -> None:
        """Build the store from a list of Song objects."""
        self.songs = list(songs)
        self._matrix = np.stack([encode_song(s) for s in self.songs])

    def search(self, query_vec: np.ndarray, k: int = 20) -> List[Song]:
        """Return the top-k songs most similar to query_vec."""
        if self._matrix is None or len(self.songs) == 0:
            return []
        q = query_vec / (np.linalg.norm(query_vec) or 1.0)
        similarities = self._matrix @ q        # dot product of unit vectors = cosine sim
        top_indices  = np.argsort(similarities)[::-1][:k]
        return [self.songs[int(i)] for i in top_indices]

    def save(self, path: str | Path) -> None:
        path = Path(path)
        data = {
            "songs": [
                {
                    "id": s.id, "title": s.title, "artist": s.artist,
                    "genre": s.genre, "mood": s.mood,
                    "energy": s.energy, "tempo_bpm": s.tempo_bpm,
                    "valence": s.valence, "danceability": s.danceability,
                    "acousticness": s.acousticness,
                }
                for s in self.songs
            ],
            "matrix": self._matrix.tolist() if self._matrix is not None else [],
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "SongVectorStore":
        path = Path(path)
        data = json.loads(path.read_text())
        store = cls()
        store.songs = [
            Song(
                id=s["id"], title=s["title"], artist=s["artist"],
                genre=s["genre"], mood=s["mood"],
                energy=s["energy"], tempo_bpm=s["tempo_bpm"],
                valence=s["valence"], danceability=s["danceability"],
                acousticness=s["acousticness"],
            )
            for s in data["songs"]
        ]
        store._matrix = np.array(data["matrix"]) if data["matrix"] else None
        return store
