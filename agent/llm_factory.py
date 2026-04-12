from django.conf import settings
from langchain_groq import ChatGroq


def get_llm():
    return ChatGroq(
        model=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=getattr(settings, "GROQ_API_KEY", ""),
        temperature=0.3,
    )
