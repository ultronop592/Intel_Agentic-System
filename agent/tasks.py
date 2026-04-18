import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from agent.graph import build_graph
from briefings.models import Briefing
from competitors.models import Competitor, CompetitorSnapshot, DiscoveredPage

logger = logging.getLogger(__name__)


def _lock_key(competitor_id: int) -> str:
    return f"competitor-agent-lock:{competitor_id}"


@shared_task(bind=True, max_retries=2, soft_time_limit=120, time_limit=180)
def run_agent_for_competitor(self, competitor_id: int) -> dict:
    logger.info(f"Agent started for competitor {competitor_id}")
    
    lock_key = _lock_key(competitor_id)
    lock_acquired = cache.add(lock_key, "1", timeout=900)
    if not lock_acquired:
        if cache.get(lock_key) == "queued":
            cache.set(lock_key, "running", timeout=900)
        else:
            return {"status": "already_running", "briefing_id": None}
    else:
        cache.set(lock_key, "running", timeout=900)

    try:
        competitor = Competitor.objects.select_related("user").get(pk=competitor_id)
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
        result = build_graph().invoke(state)
        logger.info(f"Graph result: {result}")

        if result.get("error"):
            competitor.last_status = Competitor.STATUS_FAILED
            competitor.last_scraped = timezone.now()
            competitor.current_task_id = ""
            competitor.current_task_started_at = None
            competitor.save(update_fields=["last_status", "last_scraped", "current_task_id", "current_task_started_at"])
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
            print(f"Saved briefing with pk: {briefing.pk}")

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
        return {"status": "success" if briefing_id else "no_changes", "briefing_id": briefing_id}
    except Competitor.DoesNotExist:
        logger.warning("Competitor %s does not exist for agent run.", competitor_id)
        return {"status": "failed", "briefing_id": None}
    except SoftTimeLimitExceeded:
        logger.error("Agent run timed out for competitor %s", competitor_id)
        try:
            competitor = Competitor.objects.get(pk=competitor_id)
            competitor.last_status = Competitor.STATUS_FAILED
            competitor.last_scraped = timezone.now()
            competitor.current_task_id = ""
            competitor.current_task_started_at = None
            competitor.save(
                update_fields=["last_status", "last_scraped", "current_task_id", "current_task_started_at"]
            )
        except Competitor.DoesNotExist:
            pass
        return {"status": "failed", "briefing_id": None}
    except Exception as exc:
        logger.exception("Agent run failed for competitor %s", competitor_id)
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False) or self.request.is_eager:
            try:
                competitor = Competitor.objects.get(pk=competitor_id)
                competitor.last_status = Competitor.STATUS_FAILED
                competitor.last_scraped = timezone.now()
                competitor.current_task_id = ""
                competitor.current_task_started_at = None
                competitor.save(
                    update_fields=["last_status", "last_scraped", "current_task_id", "current_task_started_at"]
                )
            except Competitor.DoesNotExist:
                pass
            return {"status": "failed", "briefing_id": None}

        if self.request.retries >= self.max_retries:
            try:
                competitor = Competitor.objects.get(pk=competitor_id)
                competitor.last_status = Competitor.STATUS_FAILED
                competitor.last_scraped = timezone.now()
                competitor.current_task_id = ""
                competitor.current_task_started_at = None
                competitor.save(
                    update_fields=["last_status", "last_scraped", "current_task_id", "current_task_started_at"]
                )
            except Competitor.DoesNotExist:
                logger.warning("Competitor %s disappeared while updating failure state.", competitor_id)
        raise self.retry(exc=exc, countdown=30)

    finally:
        cache.delete(lock_key)


@shared_task
def run_all_agents() -> int:
    count = 0
    competitors = Competitor.objects.select_related("user").filter(is_active=True)
    for competitor in competitors:
        if cache.add(_lock_key(competitor.id), "queued", timeout=30):
            cache.delete(_lock_key(competitor.id))
            run_agent_for_competitor.delay(competitor.id)
            count += 1
    return count
