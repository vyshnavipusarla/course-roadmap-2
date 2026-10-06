from concurrent.futures import ThreadPoolExecutor

from planner import plan_roadmap
from practice import generate_practice
from schemas import Roadmap, Stage, Video


def _safe_curate(stage: Stage) -> list[Video]:
    from youtube_curator import curate_stage_videos
    try:
        return curate_stage_videos(stage)
    except Exception as e:  # keep one failing stage from killing the roadmap
        print(f"[videos] '{stage.title}' failed: {e}")
        return []


def build_roadmap(course: str, level: str = "beginner", hours_per_week: int = 5,
                  with_videos: bool = True, with_practice: bool = True) -> Roadmap:
    roadmap = plan_roadmap(course, level, hours_per_week)
    titles = [s.title for s in roadmap.stages]

    def _safe_practice(stage: Stage):
        try:
            return generate_practice(course, stage, titles, hours_per_week)
        except Exception as e:
            print(f"[practice] '{stage.title}' failed: {e}")
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        if with_videos:
            for stage, vids in zip(roadmap.stages, pool.map(_safe_curate, roadmap.stages)):
                stage.videos = vids
        if with_practice:
            for stage, out in zip(roadmap.stages, pool.map(_safe_practice, roadmap.stages)):
                if out:
                    stage.exercises = out.exercises
                    stage.project = out.project
    return roadmap


if __name__ == "__main__":
    import sys

    topic = " ".join(sys.argv[1:]) or "Docker"
    rm = build_roadmap(topic)
    for i, st in enumerate(rm.stages, 1):
        print(f"\nStage {i}: {st.title}")
        for v in st.videos:
            print(f"  [{v.score:.2f}] {v.title}  |  {v.channel}  |  {v.views:,} views  |  {v.url}")
        for ex in st.exercises:
            print(f"  ({ex.difficulty}) {ex.title}")
        if st.project:
            print(f"  Project: {st.project.title}")