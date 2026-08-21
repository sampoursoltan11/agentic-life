"""Thin multi-provider LLM router built on litellm.

Each agent persona specifies a `model` string like:
  - "openai/gpt-4o-mini"
  - "anthropic/claude-3-5-haiku-20241022"
  - "ollama/llama3.1"

litellm understands the provider prefix and routes accordingly, so this
module just centralises retries/timeouts and gives us one place to add
logging or caching later.
"""
import litellm

from app.config import get_settings
from app.llm.parsing import extract_json_object

litellm.suppress_debug_info = True


async def chat(model: str, system: str, user: str, *, temperature: float = 0.7, max_tokens: int = 400) -> str:
    """Single chat completion call, returns the text content."""
    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=30,
        num_retries=2,  # ride out transient provider errors/throttles
    )
    return response.choices[0].message["content"].strip()


async def chat_json(model: str, system: str, user: str, *, temperature: float = 0.3) -> dict:
    """Chat completion that asks for and parses a JSON object response."""
    raw = await chat(
        model,
        system + "\nRespond with a single valid JSON object only, no prose, no markdown fences.",
        user,
        temperature=temperature,
    )
    return extract_json_object(raw)


async def embed(text: str) -> list[float]:
    settings = get_settings()
    response = await litellm.aembedding(
        model=settings.embedding_model, input=[text], num_retries=2
    )
    return response.data[0]["embedding"]
