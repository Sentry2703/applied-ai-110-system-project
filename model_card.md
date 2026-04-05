# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

MusicTings 1.0
Example: **VibeFinder 1.0**  

---

## 2. Intended Use  

The item is intended to recommend viable songs based on a user's denoted preferred vibes, and show the most similar songs based on our catalogue of songs.
---

## 3. How the Model Works  

MusicTings 1.0 works by comparing what a user says they like to the features of every song in the catalog, then giving each song a numeric score. Songs with higher scores get recommended first.

The user tells the system their preferred genre, mood, energy level, whether they like acoustic music, how danceable they want the music to be, and their preferred tempo (speed). Each song in the catalog has those same properties stored as data.

For each song, the system asks six questions: Does the genre match? Does the mood match? How close is the song's energy to what the user wants? How close is the acousticness? How close is the danceability? How close is the tempo? Each answer produces a small number, and those numbers are added together to form the song's total score. Genre and mood are weighted the most heavily because getting those wrong feels the most jarring — a user who wants lofi should never get metal just because the tempo happened to be close. Energy and acousticness carry the next most weight, followed by danceability and tempo as fine-grained tiebreakers.

The key addition beyond the starter logic was expanding the `UserProfile` to include danceability and target tempo as explicit preferences, and adding a tempo normalization step so that raw BPM values (which go from 60 to 168) could be compared fairly against the other features that all sit on a 0–1 scale.

---

## 4. Data  

The catalog contains 25 songs. The original starter file included 10 songs, and 15 additional songs were added to improve genre and mood diversity.

**Genres represented:** lofi, pop, rock, ambient, jazz, synthwave, indie pop, hip-hop, classical, r&b, country, edm, metal, folk, reggae, blues, funk, soul, trap, bossa nova, indie rock, k-pop — 22 genres in total.

**Moods represented:** chill, happy, intense, relaxed, focused, moody, energetic, peaceful, romantic, nostalgic, euphoric, angry, melancholic, uplifting, sad, dreamy — 16 moods in total.

The original 10 songs skewed heavily toward electronic and lofi genres and were missing entire emotional categories like sad, angry, romantic, and nostalgic. The 15 added songs were designed to fill those gaps, with each new entry targeting a genre and mood combination not already present.

What is still missing: the dataset reflects a mostly Western, English-language perspective on genre. Styles like Afrobeats, Latin pop, Bollywood, or classical Indian music are absent entirely. The data also has no songs with explicit lyrical themes, language tags, or release era — so the system cannot distinguish a 1970s soul record from a modern one, or recommend based on lyrical mood versus musical mood.

---

## 5. Strengths  

The system works best when a user's preferences are internally consistent — meaning all their chosen features point toward the same type of listening experience. For example, the "Late Night Coder" profile (lofi, chill, low energy, acoustic) produces a clear and intuitive top-3 with scores well separated from the rest of the catalog. The weighted scoring correctly surfaces Midnight Coding, Library Rain, and Focus Flow above everything else, which matches exactly what a human would expect.

The scoring also handles cross-genre discovery reasonably well when genre and mood match but numeric features diverge slightly. A user with a perfect genre/mood match still gets differentiated results based on energy and acousticness, rather than all matching songs receiving the same score. This mirrors real-world behavior where two lofi songs can still feel very different from each other.

The halving weight strategy (3.0 → 2.0 → 1.5 → 1.0 → 0.5 → 0.25) ensures that categorical preferences always dominate, which prevents absurd results like a jazz song beating a lofi song for a lofi-preferring user just because its tempo was slightly closer.

---

## 6. Limitations and Bias 

**Features the system ignores entirely:** lyrics, vocal style, language, instrumentation detail, release era, artist popularity, and listening history. Two songs can score identically even if one has screamed vocals and one has soft piano — the numbers don't capture that.

**The cold start problem for genres not in the catalog:** if a user prefers a genre that does not appear in the 25-song catalog (e.g., Afrobeats), genre score will be zero for every song and the recommendations will be driven entirely by numeric features. The user will receive results that technically match their energy or tempo preference but feel tonally wrong.

**The contradictory profile exposes a structural weakness:** when a user's own preferences conflict (e.g., metal genre but peaceful mood and low energy), the system still returns five results — it has no way to say "these preferences don't make sense together." The top-ranked song in that case wins almost by accident, scoring just slightly less badly than everything else.

**Bias toward well-represented genres:** lofi has 3 songs in the catalog (Midnight Coding, Library Rain, Focus Flow), while most other genres have only one. A lofi-preferring user benefits from more candidates competing for the top spots, giving the system more chances to find a close numeric match. A blues or bossa nova fan only has one possible genre match, so the rest of their recommendations rely entirely on numeric similarity to songs from other genres.

**The `likes_acoustic` boolean is a rough approximation:** converting `True` to `1.0` and `False` to `0.0` means the system treats acoustic preference as binary, even though a user might want "somewhat acoustic" rather than fully acoustic or fully electronic. A continuous preference value (e.g., 0.6) would be more expressive.

---

## 7. Evaluation  

Four user profiles were tested to evaluate the system across a range of expected behaviors, from clear-cut cases to adversarial edge cases.

**Late Night Coder** (lofi / chill / energy 0.4 / acoustic) was the sanity check. The expectation was that the three lofi songs in the catalog — Midnight Coding, Library Rain, and Focus Flow — would occupy the top three slots with noticeably higher scores than everything else. This held as expected. The score gap between rank 3 and rank 4 was large enough to confirm that genre and mood weights are doing their job as hard filters, not just soft preferences.

**Gym Session** (edm / euphoric / energy 0.95 / not acoustic / danceability 0.92 / tempo 140) tested the high-energy end of the catalog. Drop Zone scored highest, followed by Gym Hero and Crown Heights Cipher. What was interesting here is that Gym Hero (genre: pop, not edm) still ranked second — its energy, danceability, and tempo were close enough to push it above most edm-adjacent candidates. This revealed that a one-song genre can be beaten by multi-feature numeric alignment, which is a reasonable behavior but worth knowing.

**Sunday Morning** (r&b / romantic / energy 0.55) tested a middle-of-the-road profile where no genre is overrepresented. Velvet Kiss and Silk & Smoke ranked first and second as expected, since they are the only r&b and soul entries with a romantic mood. The third slot rotated between songs depending on danceability weighting, which confirmed that the lower-weight features do influence tiebreaking when the top features are tied.

**Contradictory** (metal / peaceful / energy 0.1 / acoustic / danceability 0.2 / tempo 62) was the stress test. The expected outcome was that no song would score well and the top results would feel arbitrary. That is exactly what happened — Iron Throne (the only metal song) ranked first solely on genre match, despite its energy (0.95), tempo (168 bpm), and acousticness (0.06) being as far from the user's numeric preferences as possible in the entire catalog. The top-5 scores were all clustered within 0.5 points of each other, compared to a spread of over 3.0 points in the well-aligned profiles. This confirmed that the system has no mechanism to detect or flag self-contradictory input.

One comparison that was informative: running the Late Night Coder profile with genre weight reduced from 3.0 to 0.5 caused Spacewalk Thoughts (ambient / chill) to jump into the top spot over the lofi songs, because its acousticness and energy were numerically very close. This demonstrated that the weights are not cosmetic — changing them materially reshapes the output.

---

## 8. Future Work  

The most impactful next step would be adding a listening history log per user — tracking which recommended songs were played, skipped, or replayed — so the system could gradually adjust feature weights to reflect actual behavior rather than relying entirely on self-reported preferences. Beyond that, introducing a diversity constraint to the ranking step (e.g., no more than two songs from the same genre in the top 5) would prevent the current behavior where a well-matched genre monopolizes all recommendation slots, giving users more exposure to adjacent styles they might enjoy.
