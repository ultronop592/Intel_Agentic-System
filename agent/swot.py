from typing import Optional
from django.utils import timezone
from datetime import timedelta
from briefings.models import Briefing, SwotReport
from agent.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
import json


def generate_swot_analysis(user) -> Optional[SwotReport]:
    """
    Aggregates recent briefings and generates a SWOT report.
    """
    # 1. Gather all briefings from the last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    recent_briefings = Briefing.objects.filter(
        user=user,
        created_at__date__range=[start_date, end_date],
        status=Briefing.STATUS_COMPLETED
    ).select_related("competitor")
    
    if not recent_briefings.exists():
        return None
        
    # 2. Extract content for the LLM
    agg_text = []
    for b in recent_briefings:
        agg_text.append(f"Competitor: {b.competitor.name}\nBriefing: {b.content[:1000]}")
    
    context_str = "\n\n".join(agg_text)
    
    # 3. Request SWOT from LLM
    system_prompt = (
        "You are a strategic business consultant. Analyze the following competitive intelligence data "
        "and generate a high-level SWOT analysis (Strengths, Weaknesses, Opportunities, Threats) for the "
        "user's business relative to these competitors.\n\n"
        "Return the response as a JSON object with the following keys:\n"
        "- 'analysis': (overall summary text)\n"
        "- 'strengths': (bullet points as text)\n"
        "- 'weaknesses': (bullet points as text)\n"
        "- 'opportunities': (bullet points as text)\n"
        "- 'threats': (bullet points as text)\n\n"
        "Keep points concise and strategic."
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Competitive Data:\n{context_str[:12000]}")
    ]
    
    llm = get_llm()
    response = llm.invoke(messages)
    
    # Simple JSON extraction logic (handles markdown block if present)
    content = response.content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
         content = content.split("```")[1].split("```")[0].strip()
    
    try:
        data = json.loads(content)
        return SwotReport.objects.create(
            user=user,
            content=data.get("analysis", ""),
            strengths=data.get("strengths", ""),
            weaknesses=data.get("weaknesses", ""),
            opportunities=data.get("opportunities", ""),
            threats=data.get("threats", ""),
            period_start=start_date,
            period_end=end_date
        )
    except Exception:
        # Fallback if JSON parsing fails
        return SwotReport.objects.create(
            user=user,
            content=response.content,
            period_start=start_date,
            period_end=end_date
        )
