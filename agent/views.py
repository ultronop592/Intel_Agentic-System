from celery.result import EagerResult
from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from agent.tasks import run_agent_for_competitor
from agent.chat import ask_intelligence_agent
from competitors.models import Competitor

import logging
import json

logger = logging.getLogger(__name__)


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

    # In eager mode, clear any stale locks before starting so the task is never blocked
    if settings.CELERY_TASK_ALWAYS_EAGER:
        cache.delete(_lock_key(competitor.id))
    elif cache.get(_lock_key(competitor.id)):
        messages.warning(request, "An agent run is already in progress for this competitor.")
        return redirect("competitors:dashboard")

    task = run_agent_for_competitor.delay(competitor.id)
    cache.set(_task_owner_key(task.id), request.user.id, timeout=3600)

    if settings.CELERY_TASK_ALWAYS_EAGER or isinstance(task, EagerResult):
        result_payload = task.result if isinstance(task.result, dict) else {"status": "completed", "briefing_id": None}
        cache.set(_eager_result_key(task.id), result_payload, timeout=3600)

        # Refresh competitor from DB since the eager task already updated it
        competitor.refresh_from_db()

        status = result_payload.get("status")
        logger.info(f"Eager agent result for {competitor.name}: {result_payload}")

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
    status = task_result.status.lower()
    
    # Map Celery terminal states to application terminal states
    if status in ["failure", "revoked", "rejected", "ignored"]:
        status = "failed"
    
    payload = {"status": status, "briefing_id": None}
    
    if isinstance(task_result.result, dict):
        # Override with specific result status if available
        payload["status"] = task_result.result.get("status", payload["status"])
        payload["briefing_id"] = task_result.result.get("briefing_id")
    
    return JsonResponse(payload)



@login_required
def chat_view(request: HttpRequest) -> HttpResponse:
    """Render the chat page or process a chat message via JSON."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            query = data.get("query", "").strip()
            if not query:
                return JsonResponse({"error": "Empty query"}, status=400)
            
            answer = ask_intelligence_agent(request.user, query)
            return JsonResponse({"answer": answer})
        except Exception as e:
            logger.exception("Chat failed")
            return JsonResponse({"error": str(e)}, status=500)
            
    return render(request, "agent/chat.html")

