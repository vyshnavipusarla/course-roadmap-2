"""Part 3: generate exercises and a hands-on project for one roadmap stage."""
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from planner import MODEL
from schemas import Exercise, Project, Stage

load_dotenv()


class PracticeOutput(BaseModel):
    exercises: list[Exercise] = Field(description="4-6 exercises ordered from easy to hard")
    project: Project


SYSTEM_PROMPT = """You design hands-on practice for a learning roadmap.

For the given stage, produce:
1. 4-6 exercises, ordered easy -> medium -> hard, that together cover the stage objectives.
   - Every exercise is something the learner DOES (write, build, run, debug, configure),
     never 'read about' or 'watch'.
   - Each has a concrete task and an expected outcome the learner can check themselves.
2. ONE project that ties the stage objectives together.
   - Deliverables are a short checklist of verifiable results.
   - It may build on skills from earlier stages, but never needs later ones.
   - Include a stretch goal for learners who finish early.
   - estimated_hours must fit within the stage's time budget.

Constraints: use free tools only, no paid services, and keep everything specific to the topic."""


def generate_practice(course: str, stage: Stage, stage_titles: list[str],
                      hours_per_week: int = 5) -> PracticeOutput:
    llm = ChatGroq(model=MODEL, temperature=0.4).with_structured_output(PracticeOutput)

    budget = stage.duration_weeks * hours_per_week
    user_msg = (
        f"Course: {course}\n"
        f"All stages in order: {' -> '.join(stage_titles)}\n\n"
        f"Current stage: {stage.title} ({stage.level})\n"
        f"Objectives:\n" + "\n".join(f"- {o}" for o in stage.objectives) + "\n"
        f"Time budget for this stage: about {budget} hours\n"
    )
    return llm.invoke([("system", SYSTEM_PROMPT), ("human", user_msg)])