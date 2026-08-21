"""Tolerant parsing of JSON objects out of LLM text responses."""
import json


def extract_json_object(raw: str) -> dict:
    """Parse a JSON object from an LLM response, tolerating markdown fences
    and surrounding prose. Raises json.JSONDecodeError if none is found."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[-1] if raw.lower().startswith("json") else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start : end + 1])
        raise
