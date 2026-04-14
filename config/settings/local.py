import os
from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "intel-agent-cache",
    }
}
