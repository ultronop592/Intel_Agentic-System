import markdown
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect

from briefings.models import Briefing, SwotReport
from competitors.models import Competitor
from agent.swot import generate_swot_analysis


@login_required
def briefings_list(request: HttpRequest) -> HttpResponse:
    """List the authenticated user's briefings with optional competitor filtering."""
    competitor_id = request.GET.get("competitor")
    briefings = Briefing.objects.filter(user=request.user).select_related("competitor", "snapshot")
    if competitor_id:
        briefings = briefings.filter(competitor_id=competitor_id)

    paginator = Paginator(briefings.order_by("-created_at"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    competitors = Competitor.objects.filter(user=request.user).only("id", "name").order_by("name")
    return render(
        request,
        "briefings/list.html",
        {
            "page_obj": page_obj,
            "competitors": competitors,
            "selected_competitor": competitor_id,
            "total_count": briefings.count(),
        },
    )


@login_required
def briefing_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render one owned briefing with markdown converted to HTML."""
    briefing = get_object_or_404(
        Briefing.objects.select_related("competitor", "snapshot").filter(user=request.user),
        pk=pk,
    )
    rendered_content = markdown.markdown(briefing.content, extensions=["extra"])
    previous_snapshot = None
    if briefing.snapshot:
        previous_snapshot = briefing.competitor.snapshots.filter(scraped_at__lt=briefing.snapshot.scraped_at).order_by("-scraped_at").first()

    return render(
        request,
        "briefings/detail.html",
        {
            "briefing": briefing,
            "rendered_content": rendered_content,
            "previous_snapshot": previous_snapshot,
        },
    )


@login_required
def swot_view(request: HttpRequest) -> HttpResponse:
    """Show the latest SWOT analysis or generate a new one."""
    if request.method == "POST":
        generate_swot_analysis(request.user)
        return redirect("briefings:swot")
        
    latest_swot = SwotReport.objects.filter(user=request.user).first()
    
    # Auto-generate if none exists
    if not latest_swot:
        latest_swot = generate_swot_analysis(request.user)
        
    return render(
        request, 
        "briefings/swot.html", 
        {"swot": latest_swot}
    )

