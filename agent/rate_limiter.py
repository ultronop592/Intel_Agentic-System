from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta


def get_rate_limit_key(user_id):
    return f"api_requests:{user_id}:{datetime.now().date()}"


def check_rate_limit(user_id):
    key = get_rate_limit_key(user_id)
    limit = getattr(settings, "DAILY_API_LIMIT", 50)

    current_count = cache.get(key, 0)

    if current_count >= limit:
        return False

    return True


def increment_rate_limit(user_id):
    key = get_rate_limit_key(user_id)
    current_count = cache.get(key, 0)
    cache.set(key, current_count + 1, timeout=86400)


def get_remaining_requests(user_id):
    key = get_rate_limit_key(user_id)
    limit = getattr(settings, "DAILY_API_LIMIT", 50)
    current_count = cache.get(key, 0)
    return max(0, limit - current_count)
