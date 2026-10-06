import streamlit as st
from pipeline import build_roadmap

st.set_page_config(page_title="Course Roadmap Generator", page_icon="🗺️", layout="wide")
st.title("🗺️ Course Roadmap Generator")

BADGE = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}

with st.sidebar:
    level = st.selectbox("Your current level", ["beginner", "intermediate", "advanced"])
    hours = st.slider("Hours per week", 1, 30, 5)
    with_videos = st.checkbox("Fetch YouTube videos", value=True,
                              help="Each new topic uses roughly 1,200 units of YouTube API quota. Results are cached.")
    with_practice = st.checkbox("Generate exercises & projects", value=True)

course = st.text_input("What do you want to learn?", placeholder="e.g. Docker, Machine Learning, React")

if st.button("Generate roadmap", type="primary") and course.strip():
    with st.spinner("Designing your roadmap, finding videos and building practice..."):
        st.session_state["roadmap"] = build_roadmap(course.strip(), level, hours, with_videos, with_practice)

roadmap = st.session_state.get("roadmap")
if roadmap:
    total_weeks = sum(s.duration_weeks for s in roadmap.stages)
    st.subheader(f"{roadmap.course}  ·  ~{total_weeks} weeks")

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