from typing import Literal, Optional
from pydantic import BaseModel, Field

Level = Literal["beginner", "intermediate", "advanced"]


# ---------- What the planner LLM must return (Part 1) ----------
class PlannedStage(BaseModel):
    title: str = Field(description="Short stage name, e.g. 'Python Fundamentals'")
    level: Level
    duration_weeks: int = Field(ge=1, le=12)
    objectives: list[str] = Field(description="3-6 concrete things the learner can do after this stage")
    search_queries: list[str] = Field(
        description="2-3 specific YouTube search queries for this stage, e.g. 'python decorators tutorial'"
    )


class PlannedRoadmap(BaseModel):
    course: str
    stages: list[PlannedStage]


# ---------- Full roadmap (filled in by later parts) ----------
class Video(BaseModel):
    title: str
    url: str
    channel: str
    views: int
    score: float = 0.0
    duration_minutes: float = 0.0
    published: str = ""      # YYYY-MM-DD
    thumbnail: str = ""


class Project(BaseModel):
    title: str
    description: str
    deliverables: list[str] = Field(description="Checkable outcomes that show the project is done")
    stretch_goal: str = ""
    estimated_hours: int = 0


class Certification(BaseModel):
    name: str
    provider: str
    url: str
    cost: Optional[str] = None
    verified: bool = False


class Exercise(BaseModel):
    title: str
    task: str = Field(description="What exactly to do, concrete and hands-on")
    difficulty: Literal["easy", "medium", "hard"]
    expected_outcome: str = Field(description="How the learner knows they got it right")


class Stage(PlannedStage):
    videos: list[Video] = []             # Part 2
    exercises: list[Exercise] = []       # Part 3
    project: Optional[Project] = None    # Part 3


class Roadmap(BaseModel):
    course: str
    stages: list[Stage]
    certifications: list[Certification] = []  # Part 4