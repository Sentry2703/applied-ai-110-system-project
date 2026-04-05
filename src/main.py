"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from recommender import load_songs, recommend_songs, dict_to_profile, dicts_to_songs


def main() -> None:
    song_dicts = load_songs("data/songs.csv")
    songs = dicts_to_songs(song_dicts)

    profiles = {
        # Clear, consistent preferences — should produce obvious top matches
        "Late Night Coder": dict_to_profile({
            "genre": "lofi", "mood": "chill", "energy": 0.4,
            "likes_acoustic": True, "danceability": 0.6, "tempo_bpm": 78
        }),
        # High-energy gym session — opposite end of the spectrum from lofi
        "Gym Session": dict_to_profile({
            "genre": "edm", "mood": "euphoric", "energy": 0.95,
            "likes_acoustic": False, "danceability": 0.92, "tempo_bpm": 140
        }),
        # Chill but wants danceable beats — moderate mixed signal
        "Sunday Morning": dict_to_profile({
            "genre": "r&b", "mood": "romantic", "energy": 0.55,
            "likes_acoustic": False, "danceability": 0.75, "tempo_bpm": 90
        }),
        # EDGE CASE: every feature contradicts the others —
        # genre=metal implies angry/high-energy/fast, but mood=peaceful,
        # energy=0.1 (near-silent), likes_acoustic=True, and slow tempo.
        # No song in the catalog satisfies more than 1-2 features at once.
        "Contradictory": dict_to_profile({
            "genre": "metal", "mood": "peaceful", "energy": 0.1,
            "likes_acoustic": True, "danceability": 0.2, "tempo_bpm": 62
        }),
    }

    for name, profile in profiles.items():
        print(f"\n{'='*50}")
        print(f"Profile: {name}")
        print(f"  Genre: {profile.favorite_genre} | Mood: {profile.favorite_mood}")
        print(f"  Energy: {profile.target_energy} | Acoustic: {profile.likes_acoustic} | Danceability: {profile.danceability} | Tempo: {profile.target_tempo} bpm")
        print(f"{'='*50}")
        recommendations = recommend_songs(profile, songs, k=5)
        for song, score, explanation in recommendations:
            print(f"  {song.title} ({song.genre} / {song.mood}) - Score: {score:.2f}")
            print(f"  {explanation}")
            print()

if __name__ == "__main__":
    main()
