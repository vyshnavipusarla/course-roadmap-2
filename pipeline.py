import time
from concurrent.futures import ThreadPoolExecutor

from cert_finder import find_certifications
from planner import plan_roadmap
from practice import generate_practice
from schemas import Roadmap, Stage
from youtube_curator import curate_stage_videos


def _retry(fn, attempts: int = 2, delay: float = 3.0):
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def _enrich_stage(stage: Stage, course: str, titles: list[str], hours: int,
                  with_videos: bool, with_practice: bool) -> None:
    """Fills videos / exercises / project on one stage. Failures are logged, not fatal."""
    if with_videos:
        try:
            stage.videos = curate_stage_videos(stage)
        except Exception as e:
            print(f"[videos] '{stage.title}' failed: {e}")
    if with_practice:
        try:
            practice = _retry(lambda: generate_practice(course, stage, titles, hours))
            stage.exercises = practice.exercises
            stage.project = practice.project
        except Exception as e:
            print(f"[practice] '{stage.title}' failed: {e}")


def _certs(course: str, titles: list[str], level: str):
    try:
        return _retry(lambda: find_certifications(course, titles, level))
    except Exception as e:
        print(f"[certs] failed: {e}")
        return []


def build_roadmap(course: str, level: str = "beginner", hours_per_week: int = 5,
                  with_videos: bool = True, with_practice: bool = True,
                  with_certs: bool = True) -> Roadmap:
    roadmap = plan_roadmap(course, level, hours_per_week)
    titles = [s.title for s in roadmap.stages]

    with ThreadPoolExecutor(max_workers=4) as pool:
        stage_futures = [
            pool.submit(_enrich_stage, s, roadmap.course, titles, hours_per_week,
                        with_videos, with_practice)
            for s in roadmap.stages
        ]
        cert_future = pool.submit(_certs, roadmap.course, titles, level) if with_certs else None

        for f in stage_futures:
            f.result()
        if cert_future:
            roadmap.certifications = cert_future.result()
    return roadmap


if __name__ == "__main__":
    import sys

    topic = " ".join(sys.argv[1:]) or "Docker"
    rm = build_roadmap(topic)
    for i, st in enumerate(rm.stages, 1):
        print(f"\nStage {i}: {st.title}")
        for v in st.videos:
            print(f"  [video {v.score:.2f}] {v.title} | {v.views:,} views | {v.url}")
        for ex in st.exercises:
            print(f"  [{ex.difficulty}] {ex.title}")
        if st.project:
            print(f"  [project] {st.project.title} (~{st.project.estimated_hours}h)")
    print("\nCertifications:")
    for c in rm.certifications:
        print(f"  {'OK' if c.verified else '??'} {c.name} | {c.provider} | {c.url}")