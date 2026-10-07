"""Part 3: generate exercises and a hands-on project for one roadmap stage."""
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from llm import structured_invoke
from schemas import Exercise, Project, Stage

load_dotenv()


# ---- what the LLM must return: every field required, no defaults (strict-mode friendly) ----
class ExerciseOut(BaseModel):
    title: str
    task: str = Field(description="2-4 sentences, max ~80 words: what exactly to do")
    difficulty: Literal["easy", "medium", "hard"]
    expected_outcome: str = Field(description="One sentence: how the learner knows it worked")


class ProjectOut(BaseModel):
    title: str
    description: str = Field(description="Max 3 sentences. Do NOT put steps or deliverables here")
    deliverables: list[str] = Field(description="3-6 short, separate, checkable results; no numbering")
    stretch_goal: str = Field(description="One sentence")
    estimated_hours: int


class PracticeOutput(BaseModel):
    exercises: list[ExerciseOut] = Field(description="4-6 exercises ordered easy to hard")
    project: ProjectOut


class Practice(BaseModel):
    """Result handed to the pipeline (the domain models)."""
    exercises: list[Exercise]
    project: Project


SYSTEM_PROMPT = """You design hands-on practice for a learning roadmap.

For the given stage, produce:
1. 4-6 exercises, ordered easy -> medium -> hard, that together cover the stage objectives.
   - Every exercise is something the learner DOES (write, build, run, debug, configure),
     never 'read about' or 'watch'.
   - Keep each task short (2-4 sentences) with a one-sentence expected outcome.
2. ONE project that ties the stage objectives together.
   - description: at most 3 sentences. Steps and deliverables do NOT go in the description.
   - deliverables: 3-6 short, separate, verifiable results (a list, no numbering).
   - Include a one-sentence stretch goal.
   - estimated_hours must fit within the stage's time budget.

Constraints: free tools only, no paid services, everything specific to the topic.
Fill in every field."""


def generate_practice(course: str, stage: Stage, stage_titles: list[str],
                      hours_per_week: int = 5) -> Practice:
    budget = stage.duration_weeks * hours_per_week
    user_msg = (
        f"Course: {course}\n"
        f"All stages in order: {' -> '.join(stage_titles)}\n\n"
        f"Current stage: {stage.title} ({stage.level})\n"
        f"Objectives:\n" + "\n".join(f"- {o}" for o in stage.objectives) + "\n"
        f"Time budget for this stage: about {budget} hours\n"
    )
    out: PracticeOutput = structured_invoke(
        PracticeOutput, [("system", SYSTEM_PROMPT), ("human", user_msg)], temperature=0.3
    )
    return Practice(
        exercises=[Exercise(**e.model_dump()) for e in out.exercises],
        project=Project(**out.project.model_dump()),
    )