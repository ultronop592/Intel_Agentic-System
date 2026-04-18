import logging
import traceback

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from agent.graph import build_graph
from briefings.models import Briefing
from competitors.models import Competitor, CompetitorSnapshot, DiscoveredPage

logger = logging.getLogger(__name__)


def _safe_cache_op(func, *args, **kwargs):
    """Run a cache operation, but never let it crash the task."""
    try:
        from django.core.cache import cache
        return func(cache, *args, **kwargs)
    except Exception as e:
        logger.warning("Cache operation failed (non-fatal): %s", e)
        return None


def _lock_key(competitor_id: int) -> str:
    return f"competitor-agent-lock:{competitor_id}"


def _is_eager():
    return getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)


def _mark_failed(competitor_id):
    """Mark a competitor as failed — used in multiple except blocks."""
    try:
        comp = Competitor.objects.get(pk=competitor_id)
        comp.last_status = Competitor.STATUS_FAILED
        comp.last_scraped = timezone.now()
        comp.current_task_id = ""
        comp.current_task_started_at = None
        comp.save(update_fields=["last_status", "last_scraped", "current_task_id", "current_task_started_at"])
    except Competitor.DoesNotExist:
        pass


@shared_task(bind=True, max_retries=2, soft_time_limit=120, time_limit=180)
def run_agent_for_competitor(self, competitor_id: int) -> dict:
    logger.info("=== Agent run START for competitor %s ===", competitor_id)

    lock_key = _lock_key(competitor_id)

    # Advisory lock — non-fatal if Redis is unreachable
    lock_val = _safe_cache_op(lambda c: c.get(lock_key))
    if lock_val and lock_val != "queued":
        logger.info("Lock already held for competitor %s, skipping.", competitor_id)
        return {"status": "already_running", "briefing_id": None}
    _safe_cache_op(lambda c: c.set(lock_key, "running", timeout=900))

    try:
        competitor = Competitor.objects.select_related("user").get(pk=competitor_id)
        logger.info("Competitor loaded: %s (%s)", competitor.name, competitor.url)

        latest_snapshot = competitor.snapshots.only("id", "raw_text", "content_hash").first()
        state = {
            "competitor_id": competitor.id,
            "competitor_name": competitor.name,
            "url": competitor.url,
            "scraped_data": {},
            "previous_text": latest_snapshot.raw_text if latest_snapshot else "",
            "diff_text": "",
            "briefing_content": "",
            "has_changes": False,
            "content_hash": "",
            "error": None,
        }

        logger.info("Invoking agent graph...")
        result = build_graph().invoke(state)
        logger.info("Graph finished. error=%s, has_changes=%s", result.get("error"), result.get("has_changes"))

        if result.get("error"):
            logger.error("Graph returned error: %s", result["error"])
            _mark_failed(competitor_id)
            return {"status": "failed", "briefing_id": None}

        clean_text = result["scraped_data"].get("clean_text", "")
        content_hash = result.get("content_hash", "")
        snapshot = latest_snapshot

        if clean_text and (not latest_snapshot or latest_snapshot.content_hash != content_hash):
            with transaction.atomic():
                snapshot = CompetitorSnapshot.objects.create(
                    competitor=competitor,
                    raw_text=clean_text,
                    content_hash=content_hash,
                    screenshot=result["scraped_data"].get("screenshot_path", ""),
                )
            logger.info("New snapshot created for competitor %s", competitor_id)

        briefing_id = None
        # Save Briefing even if has_changes is None (treat None as True)
        if result.get("has_changes") is not False:
            briefing = Briefing.objects.create(
                user=competitor.user,
                competitor=competitor,
                snapshot=snapshot,
                content=result.get("briefing_content", ""),
                changes_detected=result.get("diff_text", ""),
                status=Briefing.STATUS_COMPLETED,
            )
            briefing_id = briefing.id
            logger.info("Saved briefing pk=%s for competitor %s", briefing.pk, competitor_id)

        # Save discovered pages
        discovered_data = result.get("discovered_pages", [])
        for page in discovered_data:
            DiscoveredPage.objects.get_or_create(
                competitor=competitor,
                url=page["url"],
                defaults={"page_type": page["type"]}
            )

        competitor.last_scraped = timezone.now()
        competitor.last_status = Competitor.STATUS_SUCCESS
        competitor.current_task_id = ""
        competitor.current_task_started_at = None
        competitor.save(
            update_fields=["last_scraped", "last_status", "current_task_id", "current_task_started_at"]
        )
        logger.info("=== Agent run SUCCESS for competitor %s (briefing=%s) ===", competitor_id, briefing_id)
        return {"status": "success" if briefing_id else "no_changes", "briefing_id": briefing_id}

    except Competitor.DoesNotExist:
        logger.warning("Competitor %s does not exist.", competitor_id)
        return {"status": "failed", "briefing_id": None}

    except SoftTimeLimitExceeded:
        logger.error("Agent run TIMED OUT for competitor %s", competitor_id)
        _mark_failed(competitor_id)
        return {"status": "failed", "briefing_id": None}

    except Exception as exc:
        logger.exception("=== Agent run FAILED for competitor %s ===\n%s", competitor_id, traceback.format_exc())
        _mark_failed(competitor_id)

        # In eager mode, never retry — just return the failure gracefully
        if _is_eager():
            return {"status": "failed", "briefing_id": None}

        if self.request.retries >= self.max_retries:
            return {"status": "failed", "briefing_id": None}
        raise self.retry(exc=exc, countdown=30)

    finally:
        _safe_cache_op(lambda c: c.delete(lock_key))


@shared_task
def run_all_agents() -> int:
    count = 0
    competitors = Competitor.objects.select_related("user").filter(is_active=True)
    for competitor in competitors:
        run_agent_for_competitor.delay(competitor.id)
        count += 1
    return count
