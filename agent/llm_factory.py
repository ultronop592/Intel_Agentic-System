import logging

from django.conf import settings
from langchain_groq import ChatGroq
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from agent.rate_limiter import check_rate_limit, increment_rate_limit

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    pass


def get_llm(user_id=None):
    if user_id and not check_rate_limit(user_id):
        raise RateLimitExceeded("Daily API limit exceeded")

    return ChatGroq(
        model=getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant"),
        api_key=getattr(settings, "GROQ_API_KEY", ""),
        temperature=0.3,
        stop_sequences=[],
        max_retries=2,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "LLM call failed (attempt %d), retrying in %ds...",
        retry_state.attempt_number,
        retry_state.next_action.sleep,
    ),
)
def invoke_llm(llm, messages, user_id=None):
    if user_id:
        if not check_rate_limit(user_id):
            raise RateLimitExceeded("Daily API limit exceeded")
        increment_rate_limit(user_id)
    return llm.invoke(messages)
