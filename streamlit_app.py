"""
streamlit_app.py

Interactive Streamlit UI for the Music Recommender system.

Modes:
  Basic  — uses the existing weighted scorer (recommender.py)
  RAG+AI — narrows candidates via cosine similarity, then re-ranks with Claude

Run:
    streamlit run streamlit_app.py
"""

import sys
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

from recommender import load_songs, recommend_songs, dict_to_profile, dicts_to_songs, Song, UserProfile
from rag_retriever import SongVectorStore, encode_profile
from llm_evaluator import evaluate_and_rerank
from feedback import FeedbackStore, adapt_profile

# Make scripts/ importable for the Last.fm fetcher
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Music Recommender",
    page_icon="🎵",
    layout="wide",
)

CSV_PATH = Path(__file__).parent / "data" / "songs.csv"

# ─── Last.fm import dialog ────────────────────────────────────────────────────

@st.dialog("Import songs from Last.fm")
def lastfm_import_dialog():
    import os

    # Check for API key
    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        st.warning(
            "**LASTFM_API_KEY not found.**\n\n"
            "Add it to your `.env` file:\n```\nLASTFM_API_KEY=your_key_here\n```\n"
            "Get a free key at https://www.last.fm/api/account/create"
        )
        return

    current_count = len(load_catalog()) if CSV_PATH.exists() else 0
    st.caption(f"Current catalog: **{current_count} songs**")

    n       = st.number_input("Songs to fetch", min_value=1, max_value=500, value=50, step=10)
    replace = st.radio("Mode", ["Append to existing", "Overwrite catalog"], index=0) == "Overwrite catalog"

    if replace:
        st.warning(f"This will delete all {current_count} existing songs and replace them with {n} new ones.")
    else:
        st.info(f"This will add {n} songs → new total: ~{current_count + n}")

    col_fetch, col_cancel = st.columns(2)
    fetch  = col_fetch.button("Fetch",  type="primary",   use_container_width=True)
    cancel = col_cancel.button("Cancel", use_container_width=True)

    if cancel:
        st.rerun()

    if fetch:
        from fetch_lastfm_songs import fetch_songs, load_existing, write_rows, FIELDNAMES

        status = st.status(f"Fetching {n} songs from Last.fm...", expanded=True)
        with status:
            try:
                songs_data = fetch_songs(api_key, n)
                existing, next_id = load_existing(CSV_PATH)
                if replace:
                    existing = []
                    next_id  = 1

                output_rows = []
                for i, song in enumerate(songs_data):
                    row = {"id": next_id + i}
                    row.update({f: song[f] for f in FIELDNAMES if f != "id"})
                    output_rows.append(row)

                write_rows(CSV_PATH, output_rows, write_header=(replace or not existing))

                total = (0 if replace else len(existing)) + len(output_rows)
                status.update(label=f"Done! Added {len(output_rows)} songs — catalog now has {total}.", state="complete")

                load_catalog.clear()   # bust the cache so new songs appear immediately
                st.rerun()

            except Exception as e:
                status.update(label=f"Error: {e}", state="error")


# ─── Nudge profile dialog ─────────────────────────────────────────────────────

@st.dialog("Update your profile?")
def nudge_profile_dialog(current: dict, adapted):
    st.caption("Based on your feedback, here's how your profile would change:")

    rows = [
        ("Genre",        current["genre"],       adapted.favorite_genre),
        ("Energy",       current["energy"],       adapted.target_energy),
        ("Danceability", current["danceability"], adapted.danceability),
        ("Acoustic",     current["acoustic"],     adapted.likes_acoustic),
    ]

    col_field, col_before, col_after = st.columns([2, 2, 2])
    col_field.markdown("**Setting**")
    col_before.markdown("**Current**")
    col_after.markdown("**Nudged**")

    for label, before, after in rows:
        changed = str(before) != str(after)
        col_field.markdown(label)
        col_before.markdown(str(before))
        col_after.markdown(f"**{after}**" if changed else str(after))

    st.write("")
    col_yes, col_no = st.columns(2)

    if col_yes.button("Yes, update my profile", type="primary", use_container_width=True):
        songs_list = load_catalog()
        all_genres = sorted({s.genre for s in songs_list})
        all_moods  = sorted({s.mood  for s in songs_list})

        # Write adapted values into sidebar widget keys
        if adapted.favorite_genre in all_genres:
            st.session_state.sb_genre = adapted.favorite_genre
        if adapted.favorite_mood in all_moods:
            st.session_state.sb_mood = adapted.favorite_mood
        st.session_state.sb_energy        = round(round(adapted.target_energy  / 0.05) * 0.05, 2)
        st.session_state.sb_danceability  = round(round(adapted.danceability   / 0.05) * 0.05, 2)
        st.session_state.sb_acoustic      = adapted.likes_acoustic
        st.session_state.show_nudge_dialog = False
        st.session_state.adapted_profile   = None
        st.rerun()

    if col_no.button("No, keep current", use_container_width=True):
        st.session_state.show_nudge_dialog = False
        st.session_state.adapted_profile   = None
        st.rerun()


# ─── Session state ────────────────────────────────────────────────────────────

if "feedback" not in st.session_state:
    st.session_state.feedback = FeedbackStore()

if "results" not in st.session_state:
    st.session_state.results = []          # list of (Song, score_or_explanation)

if "profile_adapted" not in st.session_state:
    st.session_state.profile_adapted = False

# pending_feedback: {song.id: {"vote": "like"|"dislike", "song": Song}}
# Held here until "Apply feedback" is pressed — not yet written to FeedbackStore.
if "pending_feedback" not in st.session_state:
    st.session_state.pending_feedback = {}

# Sidebar widget defaults (written here so the nudge dialog can overwrite them)
if "sb_genre"       not in st.session_state: st.session_state.sb_genre       = "lofi"
if "sb_mood"        not in st.session_state: st.session_state.sb_mood        = "chill"
if "sb_energy"      not in st.session_state: st.session_state.sb_energy      = 0.5
if "sb_danceability"not in st.session_state: st.session_state.sb_danceability= 0.5
if "sb_tempo"       not in st.session_state: st.session_state.sb_tempo       = 100
if "sb_acoustic"    not in st.session_state: st.session_state.sb_acoustic    = False

# Set by Apply button, consumed by nudge dialog
if "adapted_profile"    not in st.session_state: st.session_state.adapted_profile    = None
if "show_nudge_dialog"  not in st.session_state: st.session_state.show_nudge_dialog  = False

# ─── Data loading (cached) ────────────────────────────────────────────────────

@st.cache_data
def load_catalog():
    song_dicts = load_songs(str(CSV_PATH))
    return dicts_to_songs(song_dicts)

@st.cache_resource
def build_vector_store(songs):
    store = SongVectorStore()
    store.build(songs)
    return store

# ─── Sidebar — Profile Builder ────────────────────────────────────────────────

with st.sidebar:
    st.title("Your Taste Profile")
    st.caption("Tune your preferences, then hit **Get Recommendations**.")

    songs = load_catalog()
    all_genres = sorted({s.genre for s in songs})
    all_moods  = sorted({s.mood  for s in songs})

    # Ensure saved genre/mood are still valid for the current catalog
    safe_genre = st.session_state.sb_genre if st.session_state.sb_genre in all_genres else all_genres[0]
    safe_mood  = st.session_state.sb_mood  if st.session_state.sb_mood  in all_moods  else all_moods[0]

    genre = st.selectbox("Favourite genre", all_genres, index=all_genres.index(safe_genre), key="sb_genre")
    mood  = st.selectbox("Favourite mood",  all_moods,  index=all_moods.index(safe_mood),   key="sb_mood")

    st.divider()
    energy       = st.slider("Energy",       0.0, 1.0, step=0.05, key="sb_energy")
    danceability = st.slider("Danceability", 0.0, 1.0, step=0.05, key="sb_danceability")
    tempo        = st.slider("Tempo (BPM)",  60,  200, step=5,    key="sb_tempo")
    acoustic     = st.checkbox("Prefers acoustic", key="sb_acoustic")

    st.divider()
    mode = st.radio("Recommendation mode", ["Basic", "RAG + AI"], index=0)
    k    = st.slider("Number of results", 3, 10, 5)

    run_btn = st.button("Get Recommendations", type="primary", use_container_width=True)

    st.divider()
    if st.button("Expand catalog (Last.fm)", use_container_width=True):
        lastfm_import_dialog()

    st.divider()
    pending_count = len(st.session_state.pending_feedback)
    apply_label   = f"Apply feedback & refresh ({pending_count} pending)" if pending_count else "Apply feedback & refresh"

    if st.button(apply_label, use_container_width=True, disabled=pending_count == 0):
        store = st.session_state.feedback
        for entry in st.session_state.pending_feedback.values():
            if entry["vote"] == "like":
                store.like(entry["song"])
            else:
                store.dislike(entry["song"])
        st.session_state.pending_feedback.clear()

        base_profile = dict_to_profile({
            "genre": genre, "mood": mood, "energy": energy,
            "likes_acoustic": acoustic, "danceability": danceability, "tempo_bpm": tempo,
        })
        adapted = adapt_profile(base_profile, store)
        st.session_state.adapted_profile   = adapted
        st.session_state.show_nudge_dialog = True
        st.rerun()

    if st.button("Clear feedback", use_container_width=True):
        st.session_state.feedback.clear()
        st.success("Feedback cleared.")

# ─── Main area ────────────────────────────────────────────────────────────────

st.title("🎵 Music Recommender")

# Open nudge dialog if Apply was just pressed
if st.session_state.show_nudge_dialog and st.session_state.adapted_profile is not None:
    nudge_profile_dialog(
        current={"genre": genre, "mood": mood, "energy": energy,
                 "danceability": danceability, "acoustic": acoustic},
        adapted=st.session_state.adapted_profile,
    )

col_info, col_mode = st.columns([3, 1])
with col_info:
    st.caption(f"Catalog: **{len(load_catalog())} songs** | Mode: **{mode}**")
with col_mode:
    liked_count    = len(st.session_state.feedback.liked_songs())
    disliked_count = len(st.session_state.feedback.disliked_songs())
    st.caption(f"Feedback: 👍 {liked_count}  👎 {disliked_count}")

st.divider()

# ─── Run recommendations ──────────────────────────────────────────────────────

if run_btn:
    songs = load_catalog()

    user = dict_to_profile({
        "genre": genre, "mood": mood, "energy": energy,
        "likes_acoustic": acoustic, "danceability": danceability, "tempo_bpm": tempo,
    })

    with st.spinner("Finding your songs..."):
        if mode == "RAG + AI":
            # Step 1 — RAG retrieval (top-20 by cosine similarity)
            vector_store = build_vector_store(tuple(songs))
            query_vec    = encode_profile(user)
            candidates   = vector_store.search(query_vec, k=20)

            # Step 2 — Weighted scoring on candidates
            scored = recommend_songs(user, candidates, k=10)

            # Step 3 — LLM re-ranking
            llm_input = [(song, score) for song, score, _ in scored]
            reranked  = evaluate_and_rerank(user, llm_input, k=k)
            st.session_state.results = [
                (song, expl, None) for song, expl in reranked
            ]

        else:
            # Basic weighted scoring over full catalog
            scored = recommend_songs(user, songs, k=k)
            st.session_state.results = [(song, expl, score) for song, score, expl in scored]

# ─── Display results ──────────────────────────────────────────────────────────

if st.session_state.results:
    for i, (song, expl_or_score, score) in enumerate(st.session_state.results):
        with st.container(border=True):
            col_song, col_actions = st.columns([5, 1])

            with col_song:
                st.markdown(f"### {i+1}. {song.title}")
                st.caption(f"*{song.artist}*")

                tag_col1, tag_col2, tag_col3 = st.columns(3)
                tag_col1.markdown(f"**Genre:** {song.genre}")
                tag_col2.markdown(f"**Mood:** {song.mood}")
                if score is not None:
                    tag_col3.markdown(f"**Score:** {score:.2f} / 8.25")
                else:
                    tag_col3.markdown("**Mode:** AI ranked")

                feat_c1, feat_c2, feat_c3, feat_c4 = st.columns(4)
                feat_c1.metric("Energy",       song.energy)
                feat_c2.metric("Danceability", song.danceability)
                feat_c3.metric("Valence",      song.valence)
                feat_c4.metric("Tempo",        f"{int(song.tempo_bpm)} bpm")

                st.info(expl_or_score if isinstance(expl_or_score, str) else expl_or_score)

            with col_actions:
                st.write("")
                st.write("")
                pending = st.session_state.pending_feedback.get(song.id, {}).get("vote")

                like_label    = "👍 ✓" if pending == "like"    else "👍"
                dislike_label = "👎 ✓" if pending == "dislike" else "👎"

                if st.button(like_label,    key=f"like_{i}_{song.id}",    use_container_width=True):
                    if pending == "like":
                        # Toggle off
                        st.session_state.pending_feedback.pop(song.id, None)
                    else:
                        st.session_state.pending_feedback[song.id] = {"vote": "like", "song": song}
                    st.rerun()

                if st.button(dislike_label, key=f"dislike_{i}_{song.id}", use_container_width=True):
                    if pending == "dislike":
                        # Toggle off
                        st.session_state.pending_feedback.pop(song.id, None)
                    else:
                        st.session_state.pending_feedback[song.id] = {"vote": "dislike", "song": song}
                    st.rerun()

else:
    st.info("Set your preferences in the sidebar and click **Get Recommendations**.")

# ─── Feedback history expander ────────────────────────────────────────────────

with st.expander("Feedback history"):
    liked    = st.session_state.feedback.liked_songs()
    disliked = st.session_state.feedback.disliked_songs()
    pending  = st.session_state.pending_feedback

    # Pending (not yet committed)
    if pending:
        st.caption("**Pending** (press Apply to save)")
        p_like    = [e["song"].title for e in pending.values() if e["vote"] == "like"]
        p_dislike = [e["song"].title for e in pending.values() if e["vote"] == "dislike"]
        pc1, pc2 = st.columns(2)
        pc1.markdown("👍 " + ", ".join(p_like)    if p_like    else "👍 —")
        pc2.markdown("👎 " + ", ".join(p_dislike) if p_dislike else "👎 —")
        st.divider()

    # Committed
    lc, dc = st.columns(2)
    with lc:
        st.markdown("**Liked**")
        if liked:
            for s in liked:
                st.markdown(f"- {s['title']} ({s['genre']})")
        else:
            st.caption("None yet")
    with dc:
        st.markdown("**Disliked**")
        if disliked:
            for s in disliked:
                st.markdown(f"- {s['title']} ({s['genre']})")
        else:
            st.caption("None yet")
