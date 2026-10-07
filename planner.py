from dotenv import load_dotenv

from llm import MODEL, structured_invoke  # noqa: F401  (MODEL re-exported)

from schemas import PlannedRoadmap, Roadmap, Stage

load_dotenv()

SYSTEM_PROMPT = """You are a curriculum designer. Given a course/topic, design a
complete learning roadmap as 5-8 ordered stages that go from the absolute basics
to job-ready skills.

Rules:
- Each stage builds on the previous one; no gaps, no big jumps.
- Stages must be concrete and specific to the topic (no generic filler like 'Introduction').
- Objectives are measurable skills ("Build a REST API with FastAPI"), not vague goals.
- search_queries must be specific phrases someone would type into YouTube.
- Respect the learner's level and weekly time: skip what they already know,
  and keep total duration realistic.
"""


def plan_roadmap(course: str, level: str = "beginner", hours_per_week: int = 5) -> Roadmap:
    user_msg = (
        f"Course/topic: {course}\n"
        f"Learner's current level: {level}\n"
        f"Time available: {hours_per_week} hours per week\n"
        "Design the roadmap."
    )
    planned: PlannedRoadmap = structured_invoke(
        PlannedRoadmap, [("system", SYSTEM_PROMPT), ("human", user_msg)], temperature=0.3
    )

    return Roadmap(
        course=planned.course,
        stages=[Stage(**s.model_dump()) for s in planned.stages],
    )


if __name__ == "__main__":
    import sys

    topic = " ".join(sys.argv[1:]) or "Python for Data Science"
    roadmap = plan_roadmap(topic)
    print(roadmap.model_dump_json(indent=2))