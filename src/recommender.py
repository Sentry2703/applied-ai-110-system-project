from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Tempo range drawn from the full catalog (60 bpm = Spacewalk Thoughts, 168 bpm = Iron Throne)
TEMPO_MIN = 60.0
TEMPO_MAX = 168.0

def normalizeTempo(bpm: float) -> float:
    """Squish a raw BPM value into the 0.0–1.0 range so it can be
    compared directly with other 0–1 features inside score_song.
    Values outside TEMPO_MIN/TEMPO_MAX are clamped to 0.0 or 1.0
    so an out-of-range BPM never breaks the closeness calculation."""
    normalized = (bpm - TEMPO_MIN) / (TEMPO_MAX - TEMPO_MIN)
    return max(0.0, min(1.0, normalized))

def closeness(user_val: float, song_val: float) -> float:
    """Return how close a song's feature value is to the user's preference.
    Both values must already be on a 0.0–1.0 scale.
    Perfect match  → 1.0
    Furthest apart → 0.0"""
    return 1.0 - abs(user_val - song_val)

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    danceability: float = 0.5
    target_tempo: float = 100.0

def dict_to_profile(user_prefs: Dict) -> UserProfile:
    """Convert a user_prefs dictionary into a typed UserProfile object."""
    return UserProfile(
        favorite_genre = user_prefs.get("genre", ""),
        favorite_mood  = user_prefs.get("mood", ""),
        target_energy  = float(user_prefs.get("energy", 0.5)),
        likes_acoustic = bool(user_prefs.get("likes_acoustic", False)),
        danceability   = float(user_prefs.get("danceability", 0.5)),
        target_tempo   = float(user_prefs.get("tempo_bpm", 100.0)),
    )

def dicts_to_songs(song_dicts: List[Dict]) -> List[Song]:
    """Convert a list of song dictionaries (from load_songs) into typed Song objects."""
    return [
        Song(
            id           = song["id"],
            title        = song["title"],
            artist       = song["artist"],
            genre        = song["genre"],
            mood         = song["mood"],
            energy       = song["energy"],
            tempo_bpm    = song["tempo_bpm"],
            valence      = song["valence"],
            danceability = song["danceability"],
            acousticness = song["acousticness"],
        )
        for song in song_dicts
    ]

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def score_song(user_prefs: UserProfile, song: Song) -> int:
        score = (
            (user_prefs.favorite_genre == song.genre)  * 3.0  +  # rank 1 — categorical gate
            (user_prefs.favorite_mood == song.mood)   * 2.0  +  # rank 2 — categorical gate
            closeness(user_prefs.target_energy,  song.energy)       * 1.5 +  # rank 3
            closeness(user_prefs.likes_acoustic, song.acousticness) * 1.0 +  # rank 4
            closeness(user_prefs.danceability, song.danceability) * 0.5 +  # rank 5
            closeness(normalizeTempo(user_prefs.target_tempo), normalizeTempo(song.tempo_bpm)) * 0.25  # rank 6
        )
        
        return score

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        # TODO: Implement explanation logic
        return "Explanation placeholder"

def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file.
    Required by src/main.py
    """
    import csv
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # csv.DictReader reads every value as a string.
            # Numeric fields are explicitly cast so math works later.
            songs.append({
                "id":           int(row["id"]),
                "title":        row["title"],
                "artist":       row["artist"],
                "genre":        row["genre"],
                "mood":         row["mood"],
                "energy":       float(row["energy"]),       # 0.0 – 1.0
                "tempo_bpm":    float(row["tempo_bpm"]),    # raw BPM, normalize before scoring
                "valence":      float(row["valence"]),      # 0.0 – 1.0
                "danceability": float(row["danceability"]), # 0.0 – 1.0
                "acousticness": float(row["acousticness"]), # 0.0 – 1.0
            })
    print(f"Loaded {len(songs)} songs from {csv_path}")
    return songs

def recommend_songs(user_prefs: UserProfile, songs: List[Song], k: int = 5) -> List[Tuple[Song, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    """
    # likes_acoustic is bool on UserProfile; convert to float so closeness() can do math
    acoustic_pref = float(user_prefs.likes_acoustic)

    scored = []
    for song in songs:
        # --- Scoring Rule: judge this one song ---
        genre_score    = (user_prefs.favorite_genre == song.genre) * 3.0
        mood_score     = (user_prefs.favorite_mood  == song.mood)  * 2.0
        energy_score   = closeness(user_prefs.target_energy,  song.energy)       * 1.5
        acoustic_score = closeness(acoustic_pref,             song.acousticness) * 1.0
        dance_score    = closeness(user_prefs.danceability,   song.danceability) * 0.5
        tempo_score    = closeness(
                             normalizeTempo(user_prefs.target_tempo),
                             normalizeTempo(song.tempo_bpm)
                         ) * 0.25

        score = genre_score + mood_score + energy_score + acoustic_score + dance_score + tempo_score

        # --- Explanation: describe the strongest reasons ---
        reasons = []
        if genre_score > 0:
            reasons.append(f"genre matches ({song.genre})")
        if mood_score > 0:
            reasons.append(f"mood matches ({song.mood})")
        if energy_score >= 1.2:
            reasons.append(f"energy is close ({song.energy})")
        if acoustic_score >= 0.8:
            reasons.append(f"acousticness fits ({song.acousticness})")
        explanation = "Recommended because: " + ", ".join(reasons) if reasons else "Partial match on numeric features"

        scored.append((song, round(score, 2), explanation))

    # --- Ranking Rule: sort all scores, return top k ---
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
