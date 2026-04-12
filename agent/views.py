from celery.result import EagerResult
from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from agent.tasks import run_agent_for_competitor
from competitors.models import Competitor


def _lock_key(competitor_id: int) -> str:
    return f"competitor-agent-lock:{competitor_id}"


def _task_owner_key(task_id: str) -> str:
    return f"agent-task-owner:{task_id}"


def _eager_result_key(task_id: str) -> str:
    return f"agent-eager-result:{task_id}"


@login_required
@require_POST
def run_agent_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Dispatch a manual agent run for one owned competitor."""
    competitor = get_object_or_404(Competitor, pk=pk, user=request.user)
    if cache.get(_lock_key(competitor.id)):
        messages.warning(request, "An agent run is already in progress for this competitor.")
        return redirect("competitors:dashboard")

    cache.set(_lock_key(competitor.id), "queued", timeout=900)
    task = run_agent_for_competitor.delay(competitor.id)
    cache.set(_task_owner_key(task.id), request.user.id, timeout=3600)

    if settings.CELERY_TASK_ALWAYS_EAGER or isinstance(task, EagerResult):
        result_payload = task.result if isinstance(task.result, dict) else {"status": "completed", "briefing_id": None}
        cache.set(_eager_result_key(task.id), result_payload, timeout=3600)
        competitor.current_task_id = ""
        competitor.current_task_started_at = None
        competitor.save(update_fields=["current_task_id", "current_task_started_at", "last_status", "last_scraped"])
        status = result_payload.get("status")
        if status == "success":
            messages.success(request, f"Agent completed for {competitor.name}. A new briefing is ready.")
        elif status == "no_changes":
            messages.info(request, f"Agent completed for {competitor.name}. No significant changes were detected.")
        else:
            messages.error(request, f"Agent failed for {competitor.name}. Please try again.")
        return redirect("competitors:dashboard")

    competitor.last_status = Competitor.STATUS_PENDING
    competitor.current_task_id = task.id
    competitor.current_task_started_at = timezone.now()
    competitor.save(update_fields=["last_status", "current_task_id", "current_task_started_at"])
    messages.success(request, f"Agent started for {competitor.name}.")
    return redirect(f"{reverse('competitors:dashboard')}?task={task.id}&competitor={competitor.id}")


@login_required
def agent_status_view(request: HttpRequest, task_id: str) -> JsonResponse:
    """Return Celery task status for a previously dispatched agent run."""
    if cache.get(_task_owner_key(task_id)) != request.user.id:
        return JsonResponse({"status": "unknown", "briefing_id": None}, status=404)

    cached_eager_result = cache.get(_eager_result_key(task_id))
    if cached_eager_result:
        return JsonResponse(
            {
                "status": cached_eager_result.get("status", "completed"),
                "briefing_id": cached_eager_result.get("briefing_id"),
            }
        )

    task_result = AsyncResult(task_id)
    payload = {"status": task_result.status.lower(), "briefing_id": None}
    if isinstance(task_result.result, dict):
        payload["status"] = task_result.result.get("status", payload["status"])
        payload["briefing_id"] = task_result.result.get("briefing_id")
    return JsonResponse(payload)
