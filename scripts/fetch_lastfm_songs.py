"""
fetch_lastfm_songs.py

Fetches real song titles and artists from the Last.fm API, then fills in
audio features (energy, tempo, etc.) using genre-based estimates.

Why Last.fm: free, no approval process, and the tag.getTopTracks endpoint
returns real songs organised by genre tag — perfect for our catalog.

Setup:
    1. Create a free API key at https://www.last.fm/api/account/create
    2. Add it to your .env file:
         LASTFM_API_KEY=your_key_here

Usage:
    python scripts/fetch_lastfm_songs.py              # appends 75 songs
    python scripts/fetch_lastfm_songs.py --count 50   # custom number
    python scripts/fetch_lastfm_songs.py --replace    # overwrite songs.csv
"""

import os
import csv
import time
import random
import argparse
from pathlib import Path

import requests

API_BASE = "https://ws.audioscrobbler.com/2.0/"

# ─── Genre tags → our genre labels ────────────────────────────────────────────
# Left side  = our internal genre name (matches recommender.py)
# Right side = Last.fm tag to query (https://www.last.fm/tag/<tag>)

GENRE_TAGS = {
    "lofi":        "lo-fi",
    "pop":         "pop",
    "rock":        "rock",
    "ambient":     "ambient",
    "jazz":        "jazz",
    "synthwave":   "synthwave",
    "indie pop":   "indie pop",
    "hip-hop":     "hip-hop",
    "classical":   "classical",
    "r&b":         "rnb",
    "country":     "country",
    "edm":         "edm",
    "metal":       "metal",
    "folk":        "folk",
    "reggae":      "reggae",
    "blues":       "blues",
    "funk":        "funk",
    "soul":        "soul",
    "trap":        "trap",
    "bossa nova":  "bossa nova",
    "indie rock":  "indie rock",
    "k-pop":       "k-pop",
    "afrobeats":   "afrobeats",
    "latin":       "latin",
    "house":       "house",
    "gospel":      "gospel",
    "neo-soul":    "neo soul",
}

# ─── Genre-based audio feature ranges ─────────────────────────────────────────
# (energy_min, energy_max, tempo_min, tempo_max)
GENRE_RANGES = {
    "lofi":       (0.25, 0.55,  60,  95),
    "ambient":    (0.10, 0.45,  55,  90),
    "classical":  (0.10, 0.50,  55, 120),
    "jazz":       (0.30, 0.70,  75, 130),
    "blues":      (0.25, 0.60,  60, 110),
    "folk":       (0.20, 0.55,  65, 110),
    "bossa nova": (0.25, 0.55,  70, 105),
    "country":    (0.35, 0.70,  75, 125),
    "pop":        (0.60, 0.92, 100, 140),
    "k-pop":      (0.65, 0.95, 110, 145),
    "indie pop":  (0.55, 0.85,  95, 135),
    "rock":       (0.65, 0.95, 110, 165),
    "indie rock": (0.55, 0.88, 100, 155),
    "metal":      (0.85, 0.99, 140, 200),
    "hip-hop":    (0.55, 0.90,  80, 115),
    "trap":       (0.60, 0.90, 120, 160),
    "r&b":        (0.45, 0.80,  75, 115),
    "soul":       (0.40, 0.78,  70, 115),
    "neo-soul":   (0.40, 0.75,  70, 110),
    "gospel":     (0.50, 0.85,  75, 125),
    "funk":       (0.70, 0.95,  95, 135),
    "afrobeats":  (0.65, 0.93,  95, 135),
    "latin":      (0.60, 0.92,  95, 145),
    "reggae":     (0.45, 0.75,  75, 105),
    "synthwave":  (0.55, 0.88,  95, 135),
    "house":      (0.70, 0.97, 118, 135),
    "edm":        (0.80, 0.99, 128, 155),
}

# Acousticness bias per genre (high for acoustic genres, low for electronic)
ACOUSTIC_BIAS = {
    "lofi":       (0.55, 0.95),
    "ambient":    (0.60, 0.97),
    "classical":  (0.80, 0.99),
    "jazz":       (0.55, 0.92),
    "blues":      (0.55, 0.92),
    "folk":       (0.65, 0.97),
    "bossa nova": (0.60, 0.95),
    "country":    (0.45, 0.88),
    "gospel":     (0.40, 0.85),
    "edm":        (0.01, 0.12),
    "house":      (0.01, 0.12),
    "trap":       (0.01, 0.15),
    "synthwave":  (0.05, 0.25),
    "metal":      (0.03, 0.18),
}

MOODS = [
    "chill", "happy", "intense", "relaxed", "focused", "moody", "energetic",
    "peaceful", "romantic", "nostalgic", "euphoric", "angry", "melancholic",
    "uplifting", "sad", "dreamy", "hopeful", "bittersweet", "playful", "tense",
]

# Moods that make sense per genre
GENRE_MOODS = {
    "lofi":       ["chill", "focused", "dreamy", "relaxed"],
    "ambient":    ["peaceful", "dreamy", "relaxed", "focused"],
    "classical":  ["peaceful", "melancholic", "hopeful", "nostalgic"],
    "jazz":       ["relaxed", "nostalgic", "moody", "romantic"],
    "blues":      ["sad", "melancholic", "moody", "nostalgic"],
    "folk":       ["nostalgic", "melancholic", "hopeful", "relaxed"],
    "bossa nova": ["romantic", "dreamy", "relaxed", "happy"],
    "country":    ["nostalgic", "happy", "sad", "hopeful"],
    "pop":        ["happy", "uplifting", "energetic", "romantic"],
    "k-pop":      ["happy", "energetic", "uplifting", "playful"],
    "indie pop":  ["happy", "dreamy", "bittersweet", "uplifting"],
    "rock":       ["intense", "energetic", "angry", "moody"],
    "indie rock": ["moody", "nostalgic", "energetic", "bittersweet"],
    "metal":      ["angry", "intense", "tense", "euphoric"],
    "hip-hop":    ["energetic", "moody", "focused", "uplifting"],
    "trap":       ["moody", "tense", "energetic", "intense"],
    "r&b":        ["romantic", "moody", "chill", "uplifting"],
    "soul":       ["romantic", "uplifting", "melancholic", "hopeful"],
    "neo-soul":   ["romantic", "chill", "dreamy", "moody"],
    "gospel":     ["uplifting", "hopeful", "peaceful", "energetic"],
    "funk":       ["energetic", "happy", "playful", "euphoric"],
    "afrobeats":  ["energetic", "happy", "uplifting", "playful"],
    "latin":      ["energetic", "romantic", "happy", "playful"],
    "reggae":     ["relaxed", "uplifting", "peaceful", "happy"],
    "synthwave":  ["nostalgic", "moody", "dreamy", "tense"],
    "house":      ["euphoric", "energetic", "uplifting", "happy"],
    "edm":        ["euphoric", "energetic", "intense", "uplifting"],
}

FIELDNAMES = ["id", "title", "artist", "genre", "mood",
              "energy", "tempo_bpm", "valence", "danceability", "acousticness"]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())


def _r(lo: float, hi: float) -> float:
    return round(random.uniform(lo, hi), 2)


def estimate_features(genre: str) -> dict:
    """Generate genre-realistic audio features for a real song title."""
    e_lo, e_hi, t_lo, t_hi = GENRE_RANGES.get(genre, (0.30, 0.90, 75, 150))
    a_lo, a_hi             = ACOUSTIC_BIAS.get(genre, (0.10, 0.70))
    mood_pool              = GENRE_MOODS.get(genre, MOODS)

    energy       = _r(e_lo, e_hi)
    valence      = _r(0.10, 0.95)
    danceability = _r(0.20, 0.98)

    return {
        "mood":         random.choice(mood_pool),
        "energy":       energy,
        "tempo_bpm":    random.randint(t_lo, t_hi),
        "valence":      valence,
        "danceability": danceability,
        "acousticness": _r(a_lo, a_hi),
    }

# ─── Last.fm API ───────────────────────────────────────────────────────────────

def get_top_tracks(api_key: str, tag: str, page: int = 1, limit: int = 50) -> list[dict]:
    """
    Calls tag.getTopTracks — returns real songs tagged with that genre on Last.fm.
    https://www.last.fm/api/show/tag.getTopTracks
    """
    resp = requests.get(
        API_BASE,
        params={
            "method":  "tag.getTopTracks",
            "tag":     tag,
            "api_key": api_key,
            "format":  "json",
            "page":    page,
            "limit":   limit,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    tracks = data.get("tracks", {}).get("track", [])
    return tracks if isinstance(tracks, list) else []

# ─── CSV helpers ───────────────────────────────────────────────────────────────

def load_existing(csv_path: Path) -> tuple[list[dict], int]:
    if not csv_path.exists():
        return [], 1
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    next_id = max((int(r["id"]) for r in rows), default=0) + 1
    return rows, next_id


def write_rows(csv_path: Path, rows: list[dict], write_header: bool):
    mode = "w" if write_header else "a"
    with open(csv_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

# ─── Main fetch logic ──────────────────────────────────────────────────────────

def fetch_songs(api_key: str, target: int) -> list[dict]:
    genres    = list(GENRE_TAGS.items())
    per_genre = max(1, -(-target // len(genres)))  # ceiling division
    collected = []
    seen: set = set()  # "artist|title" dedup keys

    for our_genre, tag in genres:
        if len(collected) >= target:
            break

        genre_collected = 0
        page = 1
        while genre_collected < per_genre and len(collected) < target:
            try:
                tracks = get_top_tracks(api_key, tag, page=page, limit=50)
            except requests.HTTPError as e:
                print(f"  Last.fm error for tag '{tag}': {e}")
                break

            if not tracks:
                break

            for track in tracks:
                title  = track.get("name", "").strip()
                artist = track.get("artist", {}).get("name", "").strip()
                key    = f"{artist.lower()}|{title.lower()}"

                if not title or not artist or key in seen:
                    continue

                seen.add(key)
                features = estimate_features(our_genre)

                collected.append({
                    "title":  title,
                    "artist": artist,
                    "genre":  our_genre,
                    **features,
                })
                genre_collected += 1

                if genre_collected >= per_genre or len(collected) >= target:
                    break

            page += 1
            time.sleep(0.15)  # stay within rate limits (~5 req/s allowed)

        print(f"  [{our_genre}] {genre_collected} songs  (total: {len(collected)})")

    return collected[:target]

# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    _load_env()

    parser = argparse.ArgumentParser(description="Fetch real songs from Last.fm into songs.csv")
    parser.add_argument("--count",   type=int,  default=75,
                        help="Number of songs to add (default: 75)")
    parser.add_argument("--replace", action="store_true",
                        help="Overwrite songs.csv instead of appending")
    args = parser.parse_args()

    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        print(
            "\nError: LASTFM_API_KEY not found.\n"
            "Get a free key at https://www.last.fm/api/account/create\n"
            "Then add it to your .env file:\n"
            "  LASTFM_API_KEY=your_key_here\n"
        )
        raise SystemExit(1)

    csv_path = Path(__file__).parent.parent / "data" / "new_songs.csv"

    existing, next_id = load_existing(csv_path)
    if args.replace:
        existing = []
        next_id  = 1

    print(f"Fetching {args.count} songs from Last.fm...\n")
    songs = fetch_songs(api_key, args.count)

    output_rows = []
    for i, song in enumerate(songs):
        row = {"id": next_id + i}
        row.update({f: song[f] for f in FIELDNAMES if f != "id"})
        output_rows.append(row)

    write_header = args.replace or not existing
    write_rows(csv_path, output_rows, write_header=write_header)

    total = (0 if args.replace else len(existing)) + len(output_rows)
    print(f"\nDone. {csv_path.name} now has {total} songs ({len(output_rows)} added).")


if __name__ == "__main__":
    main()
