from django.contrib.auth.models import User
from langchain_core.messages import SystemMessage, HumanMessage
from competitors.models import CompetitorSnapshot
from agent.llm_factory import get_llm


def ask_intelligence_agent(user: User, query: str) -> str:
    """
    Retrieves the latest snapshots for the user's competitors and uses them
     as context to answer the user's intelligence query.
    """
    # 1. Gather context: Latest 5 snapshots across all competitors
    # We limit to keep the context window manageable for Groq
    snapshots = CompetitorSnapshot.objects.filter(
        competitor__user=user
    ).select_related("competitor").order_by("-scraped_at")[:10]

    if not snapshots:
        return "I don't have enough data yet. Please add competitors and run the agent first."

    # 2. Build context string
    context_blocks = []
    for snap in snapshots:
        block = (
            f"--- Competitor: {snap.competitor.name} ({snap.scraped_at.strftime('%Y-%m-%d')}) ---\n"
            f"URL: {snap.competitor.url}\n"
            f"Content excerpt: {snap.raw_text[:800]}..."
        )
        context_blocks.append(block)
    
    context_str = "\n\n".join(context_blocks)

    # 3. Prepare the LLM call
    system_prompt = (
        "You are the IntelAgent - a strategic competitive intelligence AI assistant. "
        "You have access to the following recent snapshots of competitor websites. "
        "Use this data to answer the user's question accurately and strategically. "
        "If the data doesn't contain the answer, say you don't know but suggest what to track next. "
        "Format your response in professional markdown.\n\n"
        "DATABASE CONTEXT:\n"
        f"{context_str}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query)
    ]

    llm = get_llm()
    response = llm.invoke(messages)
    
    return response.content
