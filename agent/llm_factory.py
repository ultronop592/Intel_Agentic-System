from django.conf import settings
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential
from agent.rate_limiter import check_rate_limit, increment_rate_limit


class RateLimitExceeded(Exception):
    pass


def get_llm(user_id=None):
    if user_id and not check_rate_limit(user_id):
        raise RateLimitExceeded("Daily API limit exceeded")

    return ChatGroq(
        model=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=getattr(settings, "GROQ_API_KEY", ""),
        temperature=0.3,
        stop_sequences=[],
    )


def invoke_llm(llm, messages, user_id=None):
    if user_id:
        if not check_rate_limit(user_id):
            raise RateLimitExceeded("Daily API limit exceeded")
        increment_rate_limit(user_id)
    return llm.invoke(messages)
