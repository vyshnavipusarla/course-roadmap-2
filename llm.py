"""One place for every structured LLM call.

Why: with plain function calling the model writes the JSON itself and can break it
(missing quote) or skip a required field. Groq's strict structured output uses
constrained decoding, so the reply is always valid JSON that matches the schema.
It only works for openai/gpt-oss-* models and only for strict-friendly schemas,
so if Groq rejects a request we fall back to function calling.
"""
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def _run(schema, messages, temperature: float, **kw):
    llm = ChatGroq(model=MODEL, temperature=temperature).with_structured_output(schema, **kw)
    return llm.invoke(messages)


def structured_invoke(schema, messages, temperature: float = 0.3):
    """Strict JSON-schema mode first, function calling as a fallback."""
    try:
        return _run(schema, messages, temperature, method="json_schema", strict=True)
    except Exception as strict_err:
        try:
            return _run(schema, messages, temperature)          # function_calling
        except Exception as fallback_err:
            raise RuntimeError(
                f"strict mode failed ({str(strict_err)[:200]}); "
                f"fallback failed ({str(fallback_err)[:200]})"
            ) from fallback_err
