import json
from collections import Counter, defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Prefetch, Subquery
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_POST

from briefings.models import Briefing
from competitors.forms import AddCompetitorForm
from competitors.models import Competitor, CompetitorSnapshot, DiscoveredPage
from celery.result import AsyncResult


def _change_highlights(diff_text: str, limit: int = 3) -> list[str]:
    if not diff_text:
        return []
    highlights = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            cleaned = line[1:].strip()
            if cleaned:
                highlights.append(cleaned[:140])
        if len(highlights) == limit:
            break
    return highlights


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """List the user's competitors and allow cleanup of stale tasks."""
    # Auto-cleanup genuinely stale tasks (check real Celery state first)
    stale_threshold = timezone.now() - timezone.timedelta(minutes=3)
    stale_candidates = Competitor.objects.filter(
        user=request.user, 
        current_task_started_at__lt=stale_threshold
    ).exclude(current_task_id="")
    
    for comp in stale_candidates:
        # Check if the Celery task is truly dead before marking failed
        try:
            result = AsyncResult(comp.current_task_id)
            celery_state = result.status
        except Exception:
            celery_state = "UNKNOWN"
        
        # Only mark as failed if Celery confirms the task is not actively running
        if celery_state not in ("STARTED", "RETRY"):
            # Task is dead/finished — if it succeeded, save the result
            if celery_state == "SUCCESS" and isinstance(result.result, dict):
                briefing_id = result.result.get("briefing_id")
                if briefing_id:
                    comp.last_status = Competitor.STATUS_SUCCESS
                else:
                    comp.last_status = Competitor.STATUS_SUCCESS
            else:
                comp.last_status = Competitor.STATUS_FAILED
            comp.current_task_id = ""
            comp.current_task_started_at = None
            comp.save(update_fields=["last_status", "current_task_id", "current_task_started_at"])

    last_briefing_preview = Briefing.objects.filter(competitor=OuterRef("pk")).order_by("-created_at").values("content")[:1]

    last_briefing_diff = (
        Briefing.objects.filter(competitor=OuterRef("pk")).order_by("-created_at").values("changes_detected")[:1]
    )
    competitors = (
        Competitor.objects.filter(user=request.user)
        .annotate(
            briefing_count=Count("briefings", distinct=True),
            snapshot_count=Count("snapshots", distinct=True),
            discovered_count=Count("discovered_pages", distinct=True),
            last_briefing_preview=Subquery(last_briefing_preview),
            last_briefing_diff=Subquery(last_briefing_diff),
        )
        .prefetch_related(
            Prefetch(
                "briefings",
                queryset=Briefing.objects.only("id", "competitor_id", "created_at", "content", "changes_detected").order_by(
                    "-created_at"
                ),
            )
        )
        .order_by("-created_at")
    )

    form = AddCompetitorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        competitor = form.save(commit=False)
        competitor.user = request.user
        try:
            with transaction.atomic():
                competitor.save()
            messages.success(request, "Competitor added successfully.")
            return redirect("competitors:dashboard")
        except IntegrityError:
            form.add_error(
                "url",
                "This URL is already in your competitor list.",
            )
            messages.warning(request, "That URL is already being tracked.")

    total_briefings_count = Briefing.objects.filter(user=request.user).count()
    total_competitors_count = competitors.count()
    total_snapshots_count = CompetitorSnapshot.objects.filter(competitor__user=request.user).count()
    last_run_time = competitors.exclude(last_scraped__isnull=True).order_by("-last_scraped").values_list("last_scraped", flat=True).first()
    status_counts = Counter(competitors.values_list("last_status", flat=True))
    briefing_trend = defaultdict(int)
    for briefing in Briefing.objects.filter(user=request.user, created_at__gte=timezone.now() - timedelta(days=6)).only(
        "created_at"
    ):
        briefing_trend[timezone.localtime(briefing.created_at).strftime("%d %b")] += 1
    trend_labels = []
    trend_values = []
    for offset in range(6, -1, -1):
        current_day = timezone.localdate() - timedelta(days=offset)
        label = current_day.strftime("%d %b")
        trend_labels.append(label)
        trend_values.append(briefing_trend.get(label, 0))

    competitor_rows = []
    for competitor in competitors:
        competitor_rows.append(
            {
                "instance": competitor,
                "change_highlights": _change_highlights(competitor.last_briefing_diff),
            }
        )

    context = {
        "competitors": competitor_rows,
        "form": form,
        "total_briefings_count": total_briefings_count,
        "total_competitors_count": total_competitors_count,
        "total_snapshots_count": total_snapshots_count,
        "last_run_time": last_run_time,
        "active_count": status_counts.get(Competitor.STATUS_SUCCESS, 0),
        "pending_count": status_counts.get(Competitor.STATUS_PENDING, 0),
        "failed_count": status_counts.get(Competitor.STATUS_FAILED, 0),
        "trend_labels": json.dumps(trend_labels),
        "trend_values": json.dumps(trend_values),
        "selected_task_id": request.GET.get("task", ""),
        "selected_competitor_id": request.GET.get("competitor", ""),
        "task_polling_enabled": not settings.CELERY_TASK_ALWAYS_EAGER,
    }
    return render(request, "competitors/dashboard.html", context)


@login_required
def competitor_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show one owned competitor with recent briefings and snapshot history."""
    competitor = get_object_or_404(
        Competitor.objects.filter(user=request.user).prefetch_related(
            Prefetch("briefings", queryset=Briefing.objects.filter(user=request.user).order_by("-created_at")),
            Prefetch("snapshots", queryset=CompetitorSnapshot.objects.order_by("-scraped_at")),
            Prefetch("discovered_pages", queryset=DiscoveredPage.objects.all().order_by("page_type")),
        ),
        pk=pk,
    )
    snapshots = list(competitor.snapshots.all()[:10])
    briefings = list(competitor.briefings.all()[:5])
    previous_snapshot = snapshots[1] if len(snapshots) > 1 else None
    latest_snapshot = snapshots[0] if snapshots else None
    duplicate_count = 0
    previous_hash = None
    for snapshot in reversed(snapshots):
        if previous_hash and snapshot.content_hash == previous_hash:
            duplicate_count += 1
        previous_hash = snapshot.content_hash
    snapshot_labels = [timezone.localtime(snapshot.scraped_at).strftime("%d %b") for snapshot in reversed(snapshots)]
    snapshot_values = list(range(1, len(snapshot_labels) + 1))
    recent_briefing = briefings[0] if briefings else None
    recent_changes = _change_highlights(recent_briefing.changes_detected if recent_briefing else "", limit=5)

    context = {
        "competitor": competitor,
        "snapshots": snapshots,
        "briefings": briefings,
        "discovered_pages": competitor.discovered_pages.all(),
        "latest_snapshot": latest_snapshot,
        "previous_snapshot": previous_snapshot,
        "recent_changes": recent_changes,
        "duplicate_count": duplicate_count,
        "unique_snapshot_count": max(len(snapshots) - duplicate_count, 0),
        "snapshot_labels": json.dumps(snapshot_labels),
        "snapshot_values": json.dumps(snapshot_values),
    }
    return render(request, "competitors/detail.html", context)


@login_required
@require_POST
def delete_competitor(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete one owned competitor via POST only."""
    competitor = get_object_or_404(Competitor, pk=pk, user=request.user)
    competitor.delete()
    messages.success(request, "Competitor deleted.")
    return redirect("competitors:dashboard")
