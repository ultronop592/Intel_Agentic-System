import logging

import httpx
from django.conf import settings
from langchain_core.messages import AIMessage

from agent.rate_limiter import check_rate_limit, increment_rate_limit

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class RateLimitExceeded(Exception):
    pass


def _messages_to_dicts(messages) -> list[dict]:
    """Convert LangChain message objects to plain dicts for the API."""
    result = []
    for msg in messages:
        if hasattr(msg, "type"):
            role = {"human": "user", "system": "system", "ai": "assistant"}.get(
                msg.type, "user"
            )
        else:
            role = "user"
        result.append({"role": role, "content": msg.content})
    return result


def get_llm(user_id=None):
    """Check rate limit and return a sentinel — actual call happens in invoke_llm."""
    if user_id and not check_rate_limit(user_id):
        raise RateLimitExceeded("Daily API limit exceeded")
    return None  # We no longer need a ChatGroq object


def invoke_llm(llm, messages, user_id=None):
    """Call the Groq API directly via httpx (proven to work on Render)."""
    if user_id:
        if not check_rate_limit(user_id):
            raise RateLimitExceeded("Daily API limit exceeded")
        increment_rate_limit(user_id)

    api_key = getattr(settings, "GROQ_API_KEY", "")
    model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": _messages_to_dicts(messages),
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    last_error = None
    for attempt in range(3):
        try:
            logger.info(
                "Groq API call attempt %d/%d (model=%s)", attempt + 1, 3, model
            )
            response = httpx.post(
                GROQ_API_URL,
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.info("Groq API call succeeded (%d chars)", len(content))
            return AIMessage(content=content)
        except httpx.HTTPStatusError as exc:
            last_error = exc
            logger.warning(
                "Groq API HTTP %s (attempt %d): %s",
                exc.response.status_code,
                attempt + 1,
                exc.response.text[:200],
            )
            # Don't retry on 4xx errors (bad request, auth, rate limit)
            if 400 <= exc.response.status_code < 500:
                raise
        except Exception as exc:
            last_error = exc
            logger.warning("Groq API connection error (attempt %d): %s", attempt + 1, exc)

    raise last_error or RuntimeError("Groq API call failed after 3 attempts")
