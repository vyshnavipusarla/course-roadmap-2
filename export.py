"""Part 6: export a roadmap (with progress) as Markdown."""
import re

from schemas import Roadmap
from storage import item_keys


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "roadmap"


def roadmap_to_markdown(rm: Roadmap, done: set[str] | None = None) -> str:
    done = done or set()
    box = lambda key: "[x]" if key in done else "[ ]"
    weeks = sum(s.duration_weeks for s in rm.stages)
    out = [f"# {rm.course} Roadmap", "", f"About {weeks} weeks across {len(rm.stages)} stages.", ""]

    for i, st in enumerate(rm.stages):
        keys = item_keys(i, st)
        pct = f" ({round(100 * len(done & set(keys)) / len(keys))}% done)" if keys else ""
        out += [f"## Stage {i + 1}: {st.title}{pct}",
                f"*{st.level} · {st.duration_weeks} week(s)*", "", "**You will be able to:**"]
        out += [f"- {o}" for o in st.objectives]

        if st.videos:
            out += ["", "### Videos"]
            for j, v in enumerate(st.videos):
                out.append(f"- {box(f's{i}:v{j}')} [{v.title}]({v.url}) — {v.channel} · {v.views:,} views · {v.duration_minutes:g} min")
        if st.exercises:
            out += ["", "### Exercises"]
            for j, ex in enumerate(st.exercises):
                out.append(f"- {box(f's{i}:e{j}')} **{ex.title}** ({ex.difficulty}): {ex.task} *Expected: {ex.expected_outcome}*")
        if st.project:
            p = st.project
            out += ["", f"### Project: {p.title} (~{p.estimated_hours}h)", p.description, ""]
            out += [f"- {box(f's{i}:d{j}')} {d}" for j, d in enumerate(p.deliverables)]
            if p.stretch_goal:
                out.append(f"\nStretch goal: {p.stretch_goal}")
        out.append("")

    if rm.certifications:
        out += ["## Certifications"]
        for c in rm.certifications:
            extra = " · ".join(x for x in (c.provider, c.level, c.cost) if x)
            out.append(f"- [{c.name}]({c.url}) — {extra}" + (f"\n  {c.why}" if c.why else ""))
        out += ["", "*Exam details and fees change; confirm on the provider's site.*"]
    return "\n".join(out) + "\n"
