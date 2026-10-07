import streamlit as st
from pipeline import stream_roadmap

st.set_page_config(page_title="Course Roadmap Generator", page_icon="🗺️", layout="wide")
st.title("🗺️ Course Roadmap Generator")

BADGE = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}

with st.sidebar:
    level = st.selectbox("Your current level", ["beginner", "intermediate", "advanced"])
    hours = st.slider("Hours per week", 1, 30, 5)
    with_videos = st.checkbox("Fetch YouTube videos", value=True,
                              help="Each new topic uses roughly 1,200 units of YouTube API quota. Results are cached.")
    with_practice = st.checkbox("Generate exercises & projects", value=True)
    with_certs = st.checkbox("Find certifications", value=True)

course = st.text_input("What do you want to learn?", placeholder="e.g. Docker, Machine Learning, React")

if st.button("Generate roadmap", type="primary") and course.strip():
    bar = st.progress(0.0, text="Planning your roadmap...")
    total, done, final = 0, 0, None
    try:
        for node, update in stream_roadmap(course.strip(), level, hours, with_videos, with_practice, with_certs):
            if node == "plan":
                n = len(update["plan"].stages)
                total = n * (int(with_videos) + int(with_practice)) + int(with_certs)
                bar.progress(0.05, text=f"Planned {n} stages. Gathering videos, practice and certifications...")
            elif node in ("videos", "practice", "certs"):
                done += 1
                bar.progress(min(0.05 + 0.9 * done / max(total, 1), 0.95), text=f"{done}/{total} tasks finished")
            elif node == "assemble":
                final = update["roadmap"]
    except Exception as e:
        bar.empty()
        st.error(f"Could not build the roadmap: {e}")
    else:
        bar.empty()
        st.session_state["roadmap"] = final

roadmap = st.session_state.get("roadmap")
if roadmap:
    total_weeks = sum(s.duration_weeks for s in roadmap.stages)
    st.subheader(f"{roadmap.course}  ·  ~{total_weeks} weeks")
    for w in roadmap.warnings:
        st.warning(w)

    for i, stage in enumerate(roadmap.stages, 1):
        with st.expander(f"Stage {i}: {stage.title}  ({stage.level}, {stage.duration_weeks} wk)", expanded=(i == 1)):
            st.markdown("**You will be able to:**")
            for obj in stage.objectives:
                st.markdown(f"- {obj}")

            st.markdown("**🎥 Recommended videos**")
            if not stage.videos:
                st.caption("No videos loaded for this stage.")
            for v in stage.videos:
                c1, c2 = st.columns([1, 3])
                with c1:
                    if v.thumbnail:
                        st.image(v.thumbnail)
                with c2:
                    st.markdown(f"[{v.title}]({v.url})")
                    st.caption(f"{v.channel} · {v.views:,} views · {v.duration_minutes:g} min · {v.published} · score {v.score:.2f}")

            st.markdown("**✍️ Exercises**")
            if not stage.exercises:
                st.caption("No exercises generated for this stage.")
            for n, ex in enumerate(stage.exercises, 1):
                st.markdown(f"{BADGE.get(ex.difficulty, '')} **{n}. {ex.title}** ({ex.difficulty})")
                st.markdown(ex.task)
                st.caption(f"✅ Expected outcome: {ex.expected_outcome}")

            if stage.project:
                p = stage.project
                st.markdown("**🛠️ Hands-on project**")
                st.info(f"**{p.title}**  ·  ~{p.estimated_hours}h\n\n{p.description}")
                st.markdown("Deliverables:")
                for d in p.deliverables:
                    st.checkbox(d, key=f"s{i}-{p.title}-{d}")
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