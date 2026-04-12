from typing import Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.differ import compute_diff, compute_hash
from agent.llm_factory import get_llm
from agent.parser import extract_text
from agent.scraper import scrape_page


class AgentState(TypedDict):
    competitor_id: int
    competitor_name: str
    url: str
    scraped_data: dict
    previous_text: str
    diff_text: str
    briefing_content: str
    has_changes: bool
    content_hash: str
    error: Optional[str]


def scrape_node(state: AgentState) -> AgentState:
    scraped_data = scrape_page(state["url"])
    state["scraped_data"] = scraped_data
    state["error"] = scraped_data.get("error")
    return state


def diff_node(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    html = state["scraped_data"].get("html", "")
    extracted = extract_text(html) if html else state["scraped_data"].get("body_text", "")
    previous_text = state.get("previous_text", "")
    state["scraped_data"]["clean_text"] = extracted
    state["content_hash"] = compute_hash(extracted)

    if not previous_text:
        state["has_changes"] = True
        state["diff_text"] = "First scan - baseline established."
        return state

    diff_text = compute_diff(previous_text, extracted)
    state["diff_text"] = diff_text
    state["has_changes"] = diff_text != "No significant changes detected."
    return state


def analyse_node(state: AgentState) -> AgentState:
    if not state.get("has_changes") or state.get("error"):
        return state

    system_prompt = (
        "You are a strategic competitive intelligence analyst. "
        "Analyze the following competitor website content and write a professional briefing "
        "for a startup founder.\n\n"
        "Structure your briefing EXACTLY as:\n\n"
        "## What They Do\n"
        "[2-3 sentences about the company]\n\n"
        "## Key Products & Pricing\n"
        "[bullet points of products/pricing found]\n\n"
        "## What Changed\n"
        "[specific changes detected, or 'First scan - baseline established']\n\n"
        "## Strategic Insights\n"
        "[2-3 actionable insights for the founder]\n\n"
        "## Recommended Actions\n"
        "[2-3 specific things the founder should do this week]"
    )
    user_prompt = (
        f"Competitor: {state['competitor_name']}\n"
        f"URL: {state['url']}\n\n"
        f"Scraped text:\n{state['scraped_data'].get('clean_text', '')[:3000]}\n\n"
        f"Diff:\n{state.get('diff_text', '')[:1000]}"
    )
    response = get_llm().invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    state["briefing_content"] = response.content if isinstance(response.content, str) else str(response.content)
    return state


def skip_node(state: AgentState) -> AgentState:
    state["briefing_content"] = "No changes detected since last scan."
    return state


def should_continue(state: AgentState) -> str:
    if state.get("error"):
        return "end"
    return "analyse" if state.get("has_changes") else "skip"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("scrape_node", scrape_node)
    graph.add_node("diff_node", diff_node)
    graph.add_node("analyse_node", analyse_node)
    graph.add_node("skip_node", skip_node)
    graph.add_edge(START, "scrape_node")
    graph.add_edge("scrape_node", "diff_node")
    graph.add_conditional_edges(
        "diff_node",
        should_continue,
        {
            "analyse": "analyse_node",
            "skip": "skip_node",
            "end": END,
        },
    )
    graph.add_edge("analyse_node", END)
    graph.add_edge("skip_node", END)
    return graph.compile()
