import streamlit as st

from export import roadmap_to_markdown, slugify
from pipeline import stream_roadmap
from storage import (delete_roadmap, get_progress, item_keys, list_roadmaps,
                     load_roadmap, save_roadmap, set_progress)

st.set_page_config(page_title="Course Roadmap Generator", page_icon="🗺️", layout="wide")
st.title("🗺️ Course Roadmap Generator")

BADGE = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}


def _toggle(rid: int, key: str, widget_key: str) -> None:
    set_progress(rid, key, st.session_state[widget_key])


def tracked_checkbox(rid: int, key: str, label: str, done: set[str]) -> None:
    """A checkbox whose state is saved to the database the moment it changes."""
    wkey = f"{rid}:{key}"
    st.checkbox(label, value=key in done, key=wkey, on_change=_toggle, args=(rid, key, wkey))


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("New roadmap")
    level = st.selectbox("Your current level", ["beginner", "intermediate", "advanced"])
    hours = st.slider("Hours per week", 1, 30, 5)
    with_videos = st.checkbox("Fetch YouTube videos", value=True,
                              help="Each new topic uses roughly 1,200 units of YouTube API quota. Results are cached.")
    with_practice = st.checkbox("Generate exercises & projects", value=True)
    with_certs = st.checkbox("Find certifications", value=True)

    st.divider()
    st.header("📚 My roadmaps")
    saved = list_roadmaps()
    if not saved:
        st.caption("Generated roadmaps are saved here automatically.")
    else:
        labels = {r["id"]: f"{r['course']} · {r['level']} · {r['created_at'][:10]}" for r in saved}
        choice = st.selectbox("Saved roadmaps", list(labels), format_func=labels.get, label_visibility="collapsed")
        c1, c2 = st.columns(2)
        if c1.button("Open", use_container_width=True):
            st.session_state["roadmap"] = load_roadmap(choice)
            st.session_state["roadmap_id"] = choice
        if c2.button("Delete", use_container_width=True):
            delete_roadmap(choice)
            if st.session_state.get("roadmap_id") == choice:
                st.session_state.pop("roadmap", None)
                st.session_state.pop("roadmap_id", None)
            st.rerun()

# ------------------------------------------------------------------ generate
course = st.text_input("What do you want to learn?", placeholder="e.g. Docker, Machine Learning, React")

if st.button("Generate roadmap", type="primary") and course.strip():
    bar = st.progress(0.0, text="Planning your roadmap...")
    total, finished, final = 0, 0, None
    try:
        for node, update in stream_roadmap(course.strip(), level, hours, with_videos, with_practice, with_certs):
            if node == "plan":
                n = len(update["plan"].stages)
                total = n * (int(with_videos) + int(with_practice)) + int(with_certs)
                bar.progress(0.05, text=f"Planned {n} stages. Gathering videos, practice and certifications...")
            elif node in ("videos", "practice", "certs"):
                finished += 1
                bar.progress(min(0.05 + 0.9 * finished / max(total, 1), 0.95), text=f"{finished}/{total} tasks finished")
            elif node == "assemble":
                final = update["roadmap"]
    except Exception as e:
        bar.empty()
        st.error(f"Could not build the roadmap: {e}")
    else:
        bar.empty()
        if final:
            st.session_state["roadmap"] = final
            st.session_state["roadmap_id"] = save_roadmap(final, level, hours)
            st.rerun()          # refresh the sidebar list

# ------------------------------------------------------------------ show roadmap
roadmap = st.session_state.get("roadmap")
rid = st.session_state.get("roadmap_id")

if roadmap and rid:
    done = get_progress(rid)
    all_keys = [k for i, s in enumerate(roadmap.stages) for k in item_keys(i, s)]
    overall = len(done & set(all_keys)) / len(all_keys) if all_keys else 0.0
    total_weeks = sum(s.duration_weeks for s in roadmap.stages)

    head, dl = st.columns([4, 1])
    head.subheader(f"{roadmap.course}  ·  ~{total_weeks} weeks")
    dl.download_button("⬇️ Export Markdown", roadmap_to_markdown(roadmap, done),
                       file_name=f"{slugify(roadmap.course)}-roadmap.md", mime="text/markdown",
                       use_container_width=True)
    if all_keys:
        st.progress(overall, text=f"Overall progress: {overall:.0%}")
    for w in roadmap.warnings:
        st.warning(w)

    for i, stage in enumerate(roadmap.stages):
        keys = item_keys(i, stage)
        pct = len(done & set(keys)) / len(keys) if keys else None
        suffix = "" if pct is None else ("  ·  ✅ done" if pct == 1 else f"  ·  {pct:.0%}")
        title = f"Stage {i + 1}: {stage.title}  ({stage.level}, {stage.duration_weeks} wk){suffix}"

        with st.expander(title, expanded=(i == 0)):
            st.markdown("**You will be able to:**")
            for obj in stage.objectives:
                st.markdown(f"- {obj}")

            st.markdown("**🎥 Recommended videos**")
            if not stage.videos:
                st.caption("No videos loaded for this stage.")
            for j, v in enumerate(stage.videos):
                c1, c2 = st.columns([1, 3])
                with c1:
                    if v.thumbnail:
                        st.image(v.thumbnail)
                with c2:
                    st.markdown(f"[{v.title}]({v.url})")
                    st.caption(f"{v.channel} · {v.views:,} views · {v.duration_minutes:g} min · {v.published} · score {v.score:.2f}")
                    tracked_checkbox(rid, f"s{i}:v{j}", "Watched", done)

            st.markdown("**✍️ Exercises**")
            if not stage.exercises:
                st.caption("No exercises generated for this stage.")
            for j, ex in enumerate(stage.exercises):
                st.markdown(f"{BADGE.get(ex.difficulty, '')} **{j + 1}. {ex.title}** ({ex.difficulty})")
                st.markdown(ex.task)
                st.caption(f"✅ Expected outcome: {ex.expected_outcome}")
                tracked_checkbox(rid, f"s{i}:e{j}", "Done", done)

            if stage.project:
                p = stage.project
                st.markdown("**🛠️ Hands-on project**")
                st.info(f"**{p.title}**  ·  ~{p.estimated_hours}h\n\n{p.description}")
                st.markdown("Deliverables:")
                for j, d in enumerate(p.deliverables):
                    tracked_checkbox(rid, f"s{i}:d{j}", d, done)
                if p.stretch_goal:
                    st.caption(f"🚀 Stretch goal: {p.stretch_goal}")

    if roadmap.certifications:
        st.divider()
        st.subheader("🎓 Certifications to aim for")
        for c in roadmap.certifications:
            if c.is_search_link:
                st.markdown(f"🔎 [{c.name}]({c.url})")
                st.caption(c.why)
                continue
            badge = "✅ link checked" if c.verified else "⚠️ couldn't auto-check the link, open it to confirm"
            st.markdown(f"**[{c.name}]({c.url})**  ·  {c.provider}")
            st.caption(f"{c.level} · {c.cost} · {badge}")
            st.markdown(c.why)
        st.caption("Exam details and fees change; always confirm on the provider's site.")