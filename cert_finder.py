"""Part 4: pick real certifications for a roadmap.

The LLM only CHOOSES from certifications.json, so it cannot invent a certification.
Each chosen link is then checked live. If nothing in the catalog fits, we fall back
to 'browse' links on certificate platforms (clearly marked as search links).
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from planner import MODEL
from schemas import Certification

load_dotenv()

CATALOG_PATH = Path(__file__).with_name("certifications.json")
MAX_PICKS = 5
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


class CertPick(BaseModel):
    id: str = Field(description="An id copied exactly from the catalog")
    why: str = Field(description="One sentence on why this fits the roadmap")


class CertSelection(BaseModel):
    picks: list[CertPick] = Field(description="0-5 picks ordered entry-level to advanced; empty if none fit well")


SYSTEM_PROMPT = """You match a learning roadmap to professional certifications.

You are given a CATALOG of real certifications. Choose ONLY from it, using the exact id.
Rules:
- Pick up to 5 that directly relate to the course topic and skills.
- Order from entry-level to advanced.
- If nothing is a genuinely good match, return an empty list. Do not stretch for a weak match.
- Consider the learner's level; do not start an absolute beginner at an advanced exam."""


def load_catalog() -> list[dict]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def verify_url(url: str, timeout: float = 8.0) -> bool:
    """True only if the page answers with a 2xx/3xx status. Bot-blocking sites may give False."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, stream=True)
        r.close()
        return 200 <= r.status_code < 400
    except requests.RequestException:
        return False


def _select(course: str, stage_titles: list[str], level: str, catalog: list[dict]) -> CertSelection:
    llm = ChatGroq(model=MODEL, temperature=0).with_structured_output(CertSelection)
    lines = "\n".join(f"{c['id']} | {c['name']} | {c['level']} | {', '.join(c['tags'])}" for c in catalog)
    user_msg = (
        f"Course: {course}\n"
        f"Roadmap stages: {' -> '.join(stage_titles)}\n"
        f"Learner level: {level}\n\n"
        f"CATALOG (id | name | level | tags):\n{lines}"
    )
    return llm.invoke([("system", SYSTEM_PROMPT), ("human", user_msg)])


def _search_links(course: str) -> list[Certification]:
    q = quote_plus(f"{course} certificate")
    return [
        Certification(name=f"Browse '{course}' certificates on Coursera", provider="Coursera",
                      url=f"https://www.coursera.org/search?query={q}", cost="Varies",
                      why="No exact match in our curated list; browse options here.", is_search_link=True),
        Certification(name=f"Browse '{course}' certificates on edX", provider="edX",
                      url=f"https://www.edx.org/search?q={q}", cost="Varies",
                      why="No exact match in our curated list; browse options here.", is_search_link=True),
    ]


def find_certifications(course: str, stage_titles: list[str], level: str = "beginner",
                        verify: bool = True) -> list[Certification]:
    catalog = load_catalog()
    by_id = {c["id"]: c for c in catalog}

    selection = _select(course, stage_titles, level, catalog)

    certs: list[Certification] = []
    seen = set()
    for pick in selection.picks:
        entry = by_id.get(pick.id)          # drops any id the model made up
        if not entry or pick.id in seen:
            continue
        seen.add(pick.id)
        certs.append(Certification(
            name=entry["name"], provider=entry["provider"], url=entry["url"],
            cost=entry["cost"], level=entry["level"], why=pick.why,
        ))
        if len(certs) == MAX_PICKS:
            break

    if not certs:
        return _search_links(course)

    if verify:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for cert, ok in zip(certs, pool.map(lambda c: verify_url(c.url), certs)):
                cert.verified = ok
    return certs


if __name__ == "__main__":
    import sys

    topic = " ".join(sys.argv[1:]) or "Docker"
    for c in find_certifications(topic, [topic], "beginner"):
        mark = "OK " if c.verified else ("-- " if c.is_search_link else "?? ")
        print(f"{mark}{c.name} | {c.provider} | {c.cost} | {c.url}\n     {c.why}")
