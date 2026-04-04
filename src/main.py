"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from recommender import load_songs, recommend_songs


def main() -> None:
    songs = load_songs("data/songs.csv") 

    # Starter example profile
    user_prefs = {"genre": "lofi", "mood": "chill", "energy": 0.4, "likes_acoustic": True}

    recommendations = recommend_songs(user_prefs, songs, k=5)

    print("\nTop recommendations:\n")
    for rec in recommendations:
        # You decide the structure of each returned item.
        # A common pattern is: (song, score, explanation)
        song, score, explanation = rec
        print(f"{song['title']} - Score: {score:.2f}")
        print(f"Because: {explanation}")
        print()

score = (
    (user_prefs["genre"] == song["genre"])  * 3.0  +  # rank 1 — categorical gate
    (user_prefs["mood"]  == song["mood"])   * 2.0  +  # rank 2 — categorical gate
    closeness(user_prefs["energy"],      song["energy"])       * 1.5 +  # rank 3
    closeness(user_prefs["acousticness"], song["acousticness"]) * 1.0 +  # rank 4
    closeness(user_prefs["danceability"], song["danceability"]) * 0.5 +  # rank 5
    closeness(normalize(user_prefs["tempo_bpm"]), normalize(song["tempo_bpm"])) * 0.25  # rank 6
)


if __name__ == "__main__":
    main()
