"""Part 5: the whole pipeline as a LangGraph graph.

            +--> videos   (one per stage) --+
  plan -----+--> practice (one per stage) --+--> assemble
            +--> certs                    --+

`plan` decides how many parallel tasks to launch (LangGraph's Send API), the tasks run
concurrently, their results are collected by reducers, and `assemble` merges everything
into one Roadmap. A failing task adds a warning instead of killing the run.
"""
import operator
import os
import time
from typing import Annotated, Iterator, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from cert_finder import find_certifications
from planner import plan_roadmap
from practice import generate_practice
from schemas import Certification, Roadmap
from youtube_curator import curate_stage_videos

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "4"))


class State(TypedDict, total=False):
    # inputs
    course: str
    level: str
    hours_per_week: int
    with_videos: bool
    with_practice: bool
    with_certs: bool
    # working data
    plan: Roadmap
    stage_results: Annotated[list[dict], operator.add]   # parallel tasks append here
    certifications: list[Certification]
    warnings: Annotated[list[str], operator.add]
    # output
    roadmap: Roadmap


def _retry(fn, attempts: int = 2, delay: float = 3.0):
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(delay)


# ------------------------------------------------------------------ nodes
def plan(state: State) -> dict:
    return {"plan": plan_roadmap(state["course"], state["level"], state["hours_per_week"])}


def dispatch(state: State) -> list[Send]:
    """Fan out: one videos task and one practice task per stage, plus one certs task."""
    rm = state["plan"]
    titles = [s.title for s in rm.stages]
    sends: list[Send] = []
    for i, stage in enumerate(rm.stages):
        base = {"index": i, "stage": stage, "course": rm.course, "titles": titles,
                "hours_per_week": state["hours_per_week"]}
        if state["with_videos"]:
            sends.append(Send("videos", base))
        if state["with_practice"]:
            sends.append(Send("practice", base))
    if state["with_certs"]:
        sends.append(Send("certs", {"course": rm.course, "titles": titles, "level": state["level"]}))
    return sends or ["assemble"]


def videos(task: dict) -> dict:
    stage = task["stage"]
    try:
        vids = curate_stage_videos(stage)
        return {"stage_results": [{"index": task["index"], "videos": vids}]}
    except Exception as e:
        return {"warnings": [f"Videos for '{stage.title}' failed: {e}"]}


def practice(task: dict) -> dict:
    stage = task["stage"]
    try:
        out = _retry(lambda: generate_practice(task["course"], stage, task["titles"], task["hours_per_week"]))
        return {"stage_results": [{"index": task["index"], "exercises": out.exercises, "project": out.project}]}
    except Exception as e:
        return {"warnings": [f"Exercises for '{stage.title}' failed: {e}"]}


def certs(task: dict) -> dict:
    try:
        found = _retry(lambda: find_certifications(task["course"], task["titles"], task["level"]))
        return {"certifications": found}
    except Exception as e:
        return {"warnings": [f"Certifications failed: {e}"]}


def assemble(state: State) -> dict:
    rm = state["plan"].model_copy(deep=True)
    for r in state.get("stage_results", []):
        stage = rm.stages[r["index"]]
        if "videos" in r:
            stage.videos = r["videos"]
        if "exercises" in r:
            stage.exercises = r["exercises"]
            stage.project = r.get("project")
    rm.certifications = state.get("certifications", [])
    rm.warnings = state.get("warnings", [])
    return {"roadmap": rm}


# ------------------------------------------------------------------ graph
def build_graph():
    g = StateGraph(State)
    g.add_node("plan", plan)
    g.add_node("videos", videos)
    g.add_node("practice", practice)
    g.add_node("certs", certs)
    g.add_node("assemble", assemble)

    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", dispatch, ["videos", "practice", "certs", "assemble"])
    g.add_edge("videos", "assemble")
    g.add_edge("practice", "assemble")
    g.add_edge("certs", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


GRAPH = build_graph()


# ------------------------------------------------------------------ public API
def _inputs(course, level, hours_per_week, with_videos, with_practice, with_certs) -> dict:
    return {"course": course, "level": level, "hours_per_week": hours_per_week,
            "with_videos": with_videos, "with_practice": with_practice, "with_certs": with_certs}


def build_roadmap(course: str, level: str = "beginner", hours_per_week: int = 5,
                  with_videos: bool = True, with_practice: bool = True,
                  with_certs: bool = True) -> Roadmap:
    out = GRAPH.invoke(_inputs(course, level, hours_per_week, with_videos, with_practice, with_certs),
                       config={"max_concurrency": MAX_CONCURRENCY})
    return out["roadmap"]


def stream_roadmap(course: str, level: str = "beginner", hours_per_week: int = 5,
                   with_videos: bool = True, with_practice: bool = True,
                   with_certs: bool = True) -> Iterator[tuple[str, dict]]:
    """Yields (node_name, update) as the graph runs. The 'assemble' update holds the final roadmap."""
    inputs = _inputs(course, level, hours_per_week, with_videos, with_practice, with_certs)
    for chunk in GRAPH.stream(inputs, config={"max_concurrency": MAX_CONCURRENCY}, stream_mode="updates"):
        for node, update in chunk.items():
            yield node, (update or {})


if __name__ == "__main__":
    import sys

    if sys.argv[1:2] == ["--diagram"]:
        print(GRAPH.get_graph().draw_mermaid())
        raise SystemExit

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
    for w in rm.warnings:
        print("WARNING:", w)