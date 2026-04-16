"""
generate_songs.py

Generates random songs and appends them to data/new_songs.csv.
All 9 required features are filled in for every song.

Usage:
    python scripts/generate_songs.py              # adds 75 songs (brings total to ~100)
    python scripts/generate_songs.py --count 50   # adds a custom number
    python scripts/generate_songs.py --replace     # overwrites the file with fresh songs only
"""

import csv
import random
import argparse
from pathlib import Path

# ─── Song pool data ───────────────────────────────────────────────────────────

GENRES = [
    "lofi", "pop", "rock", "ambient", "jazz", "synthwave", "indie pop",
    "hip-hop", "classical", "r&b", "country", "edm", "metal", "folk",
    "reggae", "blues", "funk", "soul", "trap", "bossa nova", "indie rock",
    "k-pop", "afrobeats", "latin", "house", "drum and bass", "gospel",
    "neo-soul", "shoegaze", "lo-country",
]

MOODS = [
    "chill", "happy", "intense", "relaxed", "focused", "moody", "energetic",
    "peaceful", "romantic", "nostalgic", "euphoric", "angry", "melancholic",
    "uplifting", "sad", "dreamy", "tense", "hopeful", "bittersweet", "playful",
]

# (title fragments, artist name fragments) keyed by genre for plausible names
TITLE_WORDS = {
    "lofi":         (["Rain", "Study", "Late", "Dusk", "Page", "Lamp", "Mist", "Quiet", "4AM", "Soft"],
                     ["Night", "Tape", "Loop", "Haze", "Room", "Drift", "Flow", "Glow", "Fog", "Beat"]),
    "pop":          (["Golden", "Summer", "Neon", "Bright", "Sweet", "City", "Wild", "New", "Shine", "Cool"],
                     ["Days", "Heart", "Wave", "Rush", "Lights", "Nights", "Eyes", "Fire", "Soul", "Dream"]),
    "rock":         (["Thunder", "Iron", "Broken", "Stone", "Dark", "Loud", "Raw", "Crash", "Edge", "Volt"],
                     ["Road", "Sky", "Fire", "Wall", "Storm", "Fist", "Chain", "Scar", "Wire", "Blade"]),
    "ambient":      (["Floating", "Infinite", "Pale", "Silent", "Deep", "Slow", "Echo", "Vast", "Open", "Still"],
                     ["Space", "Current", "Cloud", "Field", "Shore", "Tide", "Glass", "Air", "Drift", "Light"]),
    "jazz":         (["Velvet", "Smoke", "Blue", "After", "Late", "Long", "Sweet", "Dim", "Soft", "Warm"],
                     ["Miles", "Café", "Keys", "Brass", "Note", "Swing", "Set", "Hour", "Club", "Room"]),
    "default":      (["Broken", "Golden", "Lost", "New", "Dark", "Bright", "Cold", "Warm", "Far", "High"],
                     ["Sky", "Road", "Song", "Night", "Days", "Wave", "Fire", "Dream", "Heart", "Soul"]),
}

ARTIST_FIRST = [
    "Neon", "Velvet", "Ivory", "Drift", "Solar", "Paper", "Orbit",
    "Lunar", "Static", "Hollow", "Crimson", "Silver", "Fern", "Coastal",
    "Blind", "Slow", "Max", "Verse", "Void", "Axial", "Lua", "Clara",
    "The Pale", "The Slick", "The Pine", "LoRoom", "STΛR", "Sable",
    "Indigo", "Volt",
]
ARTIST_LAST = [
    "Echo", "Bloom", "Lane", "Theory", "Parade", "Lanterns", "Voss",
    "Pulse", "Hammer", "Collective", "Circuit", "Hollow", "June", "Rhythm",
    "River", "Stereo", "Kings", "Circuit", "Nova", "Crow", "Memory",
    "88", "Sound", "Light", "Wave", "Sky", "Ghost", "Signal", "Fire", "Ink",
]

FIELDNAMES = ["id", "title", "artist", "genre", "mood",
              "energy", "tempo_bpm", "valence", "danceability", "acousticness"]

# ─── Feature ranges per genre (energy_min, energy_max, tempo_min, tempo_max) ──
GENRE_RANGES = {
    "lofi":         (0.25, 0.55, 60,  95),
    "ambient":      (0.10, 0.45, 55,  90),
    "classical":    (0.10, 0.50, 55, 120),
    "jazz":         (0.30, 0.70, 75, 130),
    "blues":        (0.25, 0.60, 60, 110),
    "folk":         (0.20, 0.55, 65, 110),
    "bossa nova":   (0.25, 0.55, 70, 105),
    "country":      (0.35, 0.70, 75, 125),
    "pop":          (0.60, 0.92, 100, 140),
    "k-pop":        (0.65, 0.95, 110, 145),
    "indie pop":    (0.55, 0.85, 95, 135),
    "rock":         (0.65, 0.95, 110, 165),
    "indie rock":   (0.55, 0.88, 100, 155),
    "metal":        (0.85, 0.99, 140, 200),
    "hip-hop":      (0.55, 0.90, 80, 115),
    "trap":         (0.60, 0.90, 120, 160),
    "r&b":          (0.45, 0.80, 75, 115),
    "soul":         (0.40, 0.78, 70, 115),
    "neo-soul":     (0.40, 0.75, 70, 110),
    "gospel":       (0.50, 0.85, 75, 125),
    "funk":         (0.70, 0.95, 95, 135),
    "afrobeats":    (0.65, 0.93, 95, 135),
    "latin":        (0.60, 0.92, 95, 145),
    "reggae":       (0.45, 0.75, 75, 105),
    "synthwave":    (0.55, 0.88, 95, 135),
    "house":        (0.70, 0.97, 118, 135),
    "edm":          (0.80, 0.99, 128, 155),
    "drum and bass":(0.80, 0.98, 160, 185),
    "shoegaze":     (0.40, 0.78, 85, 130),
    "lo-country":   (0.20, 0.50, 60, 100),
}

# Acousticness tends to be high for acoustic genres, low for electronic
ACOUSTIC_BIAS = {
    "lofi": (0.55, 0.95), "ambient": (0.60, 0.97), "classical": (0.80, 0.99),
    "jazz": (0.55, 0.92), "blues": (0.55, 0.92), "folk": (0.65, 0.97),
    "bossa nova": (0.60, 0.95), "country": (0.45, 0.88), "gospel": (0.40, 0.85),
    "edm": (0.01, 0.12), "house": (0.01, 0.12), "drum and bass": (0.01, 0.10),
    "trap": (0.01, 0.15), "synthwave": (0.05, 0.25), "metal": (0.03, 0.18),
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _r(lo: float, hi: float, decimals: int = 2) -> float:
    return round(random.uniform(lo, hi), decimals)


def _genre_words(genre: str):
    return TITLE_WORDS.get(genre, TITLE_WORDS["default"])


def random_title(genre: str) -> str:
    words_a, words_b = _genre_words(genre)
    return f"{random.choice(words_a)} {random.choice(words_b)}"


def random_artist() -> str:
    return f"{random.choice(ARTIST_FIRST)} {random.choice(ARTIST_LAST)}"


def random_song(song_id: int) -> dict:
    genre = random.choice(GENRES)
    mood  = random.choice(MOODS)

    e_lo, e_hi, t_lo, t_hi = GENRE_RANGES.get(genre, (0.30, 0.90, 75, 150))
    a_lo, a_hi             = ACOUSTIC_BIAS.get(genre, (0.10, 0.70))

    energy       = _r(e_lo, e_hi)
    tempo_bpm    = random.randint(t_lo, t_hi)
    valence      = _r(0.10, 0.95)
    danceability = _r(0.20, 0.98)
    acousticness = _r(a_lo, a_hi)

    return {
        "id":           song_id,
        "title":        random_title(genre),
        "artist":       random_artist(),
        "genre":        genre,
        "mood":         mood,
        "energy":       energy,
        "tempo_bpm":    tempo_bpm,
        "valence":      valence,
        "danceability": danceability,
        "acousticness": acousticness,
    }

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate random songs for songs.csv")
    parser.add_argument("--count",   type=int, default=75,
                        help="Number of songs to generate (default: 75)")
    parser.add_argument("--replace", action="store_true",
                        help="Overwrite the CSV instead of appending")
    args = parser.parse_args()

    csv_path = Path(__file__).parent.parent / "data" / "new_songs.csv"

    existing_songs = []
    next_id = 1

    if not args.replace and csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_songs.append(row)
        if existing_songs:
            next_id = max(int(r["id"]) for r in existing_songs) + 1
        print(f"Found {len(existing_songs)} existing songs. Appending {args.count} new ones.")
    else:
        print(f"Generating {args.count} fresh songs (replace mode).")

    new_songs = [random_song(next_id + i) for i in range(args.count)]

    mode = "w" if args.replace else "a"
    with open(csv_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if args.replace or not existing_songs:
            writer.writeheader()
        writer.writerows(new_songs)

    total = (0 if args.replace else len(existing_songs)) + args.count
    print(f"Done. {csv_path} now has {total} songs.")


if __name__ == "__main__":
    main()
